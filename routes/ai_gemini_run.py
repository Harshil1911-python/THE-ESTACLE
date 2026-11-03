"""Gemini runner for Estacle AI."""
from __future__ import annotations
import json
from routes.ai_tools import TOOL_IMPL, GEMINI_TOOLS, SYSTEM_PROMPT


def _extract_text(response) -> str:
    """Pull text out of a Gemini response without raising on multi-part / tool-only replies."""
    if response is None:
        return ''
    try:
        t = response.text
        if t and str(t).strip():
            return str(t).strip()
    except Exception:
        pass
    chunks = []
    try:
        for cand in (response.candidates or []):
            content = getattr(cand, 'content', None)
            if not content:
                continue
            for part in (content.parts or []):
                txt = getattr(part, 'text', None)
                if txt:
                    chunks.append(str(txt))
    except Exception:
        pass
    return '\n'.join(chunks).strip()


def _finish_reason(response) -> str:
    try:
        cands = list(response.candidates or [])
        if not cands:
            return 'NO_CANDIDATES'
        fr = getattr(cands[0], 'finish_reason', None)
        return str(fr) if fr is not None else ''
    except Exception:
        return ''


def run_gemini(api_key: str, user_message: str, history: list | None = None) -> dict:
    """Call Gemini with function calling. Returns {reply, tool_results, error}."""
    try:
        import google.generativeai as genai
    except ImportError:
        return {
            'error': 'google-generativeai is not installed. Run: pip install google-generativeai',
            'reply': None,
            'tool_results': [],
        }

    genai.configure(api_key=api_key)

    model_candidates = [
        'gemini-2.0-flash',
        'gemini-2.0-flash-001',
        'gemini-1.5-flash',
        'gemini-1.5-flash-latest',
        'gemini-1.5-flash-8b',
        'gemini-pro',
    ]

    try:
        from google.generativeai.types import FunctionDeclaration, Tool
        decls = [
            FunctionDeclaration(
                name=t['name'],
                description=t.get('description', ''),
                parameters=t.get('parameters') or {'type': 'object', 'properties': {}},
            )
            for t in GEMINI_TOOLS
        ]
        tools = [Tool(function_declarations=decls)]
    except Exception:
        tools = [{'function_declarations': GEMINI_TOOLS}]

    last_error = None
    model = None
    model_name_used = None
    for name in model_candidates:
        try:
            model = genai.GenerativeModel(
                model_name=name,
                tools=tools,
                system_instruction=SYSTEM_PROMPT,
            )
            model_name_used = name
            break
        except Exception as e1:
            last_error = e1
            try:
                model = genai.GenerativeModel(model_name=name, tools=tools)
                model_name_used = name
                break
            except Exception as e2:
                last_error = e2
                continue

    if model is None:
        return {
            'error': f'Could not load a Gemini model. Last error: {last_error}',
            'reply': None,
            'tool_results': [],
        }

    chat_history = []
    for h in (history or [])[-12:]:
        role = h.get('role', 'user')
        content = h.get('content', '')
        if not content:
            continue
        if role == 'user':
            chat_history.append({'role': 'user', 'parts': [content]})
        elif role == 'assistant':
            chat_history.append({'role': 'model', 'parts': [content]})

    try:
        chat = model.start_chat(history=chat_history)
    except Exception as e:
        return {'error': f'Failed to start chat ({model_name_used}): {e}', 'reply': None, 'tool_results': []}

    tool_results = []

    try:
        response = chat.send_message(user_message)
    except Exception as e:
        return {'error': f'Gemini request failed ({model_name_used}): {e}', 'reply': None, 'tool_results': []}

    for _ in range(6):
        calls = []
        try:
            for cand in (response.candidates or []):
                content = getattr(cand, 'content', None)
                if not content:
                    continue
                for part in (content.parts or []):
                    fc = getattr(part, 'function_call', None)
                    if fc and getattr(fc, 'name', None):
                        try:
                            args = dict(fc.args) if fc.args else {}
                        except Exception:
                            args = {}
                            try:
                                for k, v in fc.args.items():
                                    args[k] = v
                            except Exception:
                                pass
                        calls.append((fc.name, args))
        except Exception:
            break

        if not calls:
            break

        response_parts = []
        for name, args in calls:
            impl = TOOL_IMPL.get(name)
            if not impl:
                result = {'error': f'Unknown tool: {name}'}
            else:
                try:
                    result = impl(**args)
                except TypeError:
                    import inspect
                    sig = inspect.signature(impl)
                    filtered = {k: v for k, v in args.items() if k in sig.parameters}
                    try:
                        result = impl(**filtered)
                    except Exception as e2:
                        result = {'error': str(e2)}
                except Exception as e:
                    result = {'error': str(e)}
            tool_results.append({'tool': name, 'args': args, 'result': result})
            try:
                response_parts.append(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=name,
                            response={'result': result},
                        )
                    )
                )
            except Exception:
                response_parts.append({
                    'function_response': {
                        'name': name,
                        'response': {'result': result},
                    }
                })

        try:
            response = chat.send_message(response_parts)
        except Exception as e:
            try:
                response = chat.send_message(
                    'Tool results (JSON):\n' + json.dumps(tool_results, default=str)
                    + '\n\nPlease summarize what you did for the user in plain language.'
                )
            except Exception as e2:
                summary = '; '.join(
                    f"{t['tool']}: {json.dumps(t['result'], default=str)[:120]}"
                    for t in tool_results
                )
                return {
                    'error': None,
                    'reply': f'Actions completed, but Gemini could not summarize ({e2}). Results: {summary}',
                    'tool_results': tool_results,
                }

    reply = _extract_text(response)
    if not reply:
        reason = _finish_reason(response)
        if tool_results:
            reply = 'Done. ' + '; '.join(
                f"{t['tool']}: {json.dumps(t['result'], default=str)[:120]}"
                for t in tool_results
            )
        elif reason and 'SAFETY' in reason.upper():
            return {
                'error': 'Gemini blocked the response for safety reasons. Try rephrasing.',
                'reply': None,
                'tool_results': tool_results,
            }
        elif reason and reason not in ('1', 'STOP', 'FinishReason.STOP', '0'):
            return {
                'error': f'Gemini returned no text (finish_reason={reason}, model={model_name_used}).',
                'reply': None,
                'tool_results': tool_results,
            }
        else:
            try:
                plain = genai.GenerativeModel(model_name=model_name_used)
                plain_resp = plain.generate_content(
                    f"{SYSTEM_PROMPT}\n\nUser: {user_message}\n\nAssistant:"
                )
                reply = _extract_text(plain_resp)
            except Exception as e:
                return {
                    'error': f'Gemini returned an empty reply ({model_name_used}): {e}',
                    'reply': None,
                    'tool_results': tool_results,
                }
            if not reply:
                return {
                    'error': f'Gemini returned an empty reply (model={model_name_used}). Check the API key and that the Generative Language API is enabled.',
                    'reply': None,
                    'tool_results': tool_results,
                }

    return {'reply': reply, 'tool_results': tool_results, 'error': None}
