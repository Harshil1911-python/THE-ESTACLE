"""Gemini runner for Estacle AI.

Uses the Generative Language REST API so both classic AIza keys and
new AQ. auth keys from Google AI Studio work.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from routes.ai_tools import TOOL_IMPL, GEMINI_TOOLS, SYSTEM_PROMPT

API_BASE = "https://generativelanguage.googleapis.com/v1beta"
MODEL_CANDIDATES = [
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemini-pro-latest",
    "gemini-2.5-pro",
]


def _http_json(method: str, url: str, api_key: str, body: dict | None = None, timeout: int = 90) -> dict:
    data = None
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        try:
            err_json = json.loads(err_body)
            msg = err_json.get("error", {}).get("message") or err_body
        except Exception:
            msg = err_body or str(e)
        raise RuntimeError(f"Gemini HTTP {e.code}: {msg}") from e


def _extract_text_from_api(resp: dict) -> str:
    chunks = []
    for cand in resp.get("candidates") or []:
        content = cand.get("content") or {}
        for part in content.get("parts") or []:
            if isinstance(part.get("text"), str) and part["text"].strip():
                chunks.append(part["text"])
    return "\n".join(chunks).strip()


def _extract_function_calls(resp: dict) -> list:
    calls = []
    for cand in resp.get("candidates") or []:
        content = cand.get("content") or {}
        for part in content.get("parts") or []:
            fc = part.get("functionCall") or part.get("function_call")
            if not fc:
                continue
            name = fc.get("name")
            if not name:
                continue
            args = fc.get("args") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            calls.append((name, dict(args)))
    return calls


def _finish_reason(resp: dict) -> str:
    cands = resp.get("candidates") or []
    if not cands:
        return "NO_CANDIDATES"
    return str(cands[0].get("finishReason") or cands[0].get("finish_reason") or "")


def _build_tools_payload() -> list:
    decls = []
    for t in GEMINI_TOOLS:
        decls.append({
            "name": t["name"],
            "description": t.get("description", ""),
            "parameters": t.get("parameters") or {"type": "object", "properties": {}},
        })
    return [{"functionDeclarations": decls}]


def _run_tool(name: str, args: dict) -> dict:
    impl = TOOL_IMPL.get(name)
    if not impl:
        return {"error": f"Unknown tool: {name}"}
    try:
        return impl(**args)
    except TypeError:
        import inspect
        sig = inspect.signature(impl)
        filtered = {k: v for k, v in args.items() if k in sig.parameters}
        try:
            return impl(**filtered)
        except Exception as e:
            return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


def run_gemini(api_key: str, user_message: str, history: list | None = None) -> dict:
    """Call Gemini with function calling. Returns {reply, tool_results, error}."""
    if not api_key or not str(api_key).strip():
        return {"error": "Missing Gemini API key", "reply": None, "tool_results": []}

    api_key = str(api_key).strip()
    tools = _build_tools_payload()

    contents = []
    for h in (history or [])[-12:]:
        role = h.get("role", "user")
        content = (h.get("content") or "").strip()
        if not content:
            continue
        api_role = "user" if role == "user" else "model"
        contents.append({"role": api_role, "parts": [{"text": content}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    body_base = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "tools": tools,
        "contents": contents,
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 2048,
        },
    }

    last_error = None
    model_used = None
    response = None

    for model in MODEL_CANDIDATES:
        url = f"{API_BASE}/models/{model}:generateContent"
        try:
            response = _http_json("POST", url, api_key, body_base)
            model_used = model
            break
        except Exception as e:
            last_error = e
            try:
                body_plain = {
                    "tools": tools,
                    "contents": [
                        {"role": "user", "parts": [{"text": SYSTEM_PROMPT + "\n\nUser: " + user_message}]}
                    ],
                    "generationConfig": body_base["generationConfig"],
                }
                response = _http_json("POST", url, api_key, body_plain)
                model_used = model
                contents = body_plain["contents"]
                break
            except Exception as e2:
                last_error = e2
                continue

    if response is None:
        return {
            "error": f"Could not reach Gemini. Last error: {last_error}",
            "reply": None,
            "tool_results": [],
        }

    tool_results = []

    for _ in range(6):
        calls = _extract_function_calls(response)
        if not calls:
            break

        model_parts = []
        for cand in response.get("candidates") or []:
            content = cand.get("content") or {}
            for part in content.get("parts") or []:
                model_parts.append(part)
        if model_parts:
            contents.append({"role": "model", "parts": model_parts})

        fn_response_parts = []
        for name, args in calls:
            result = _run_tool(name, args)
            tool_results.append({"tool": name, "args": args, "result": result})
            fn_response_parts.append({
                "functionResponse": {
                    "name": name,
                    "response": {"result": result},
                }
            })
        contents.append({"role": "user", "parts": fn_response_parts})

        url = f"{API_BASE}/models/{model_used}:generateContent"
        body = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "tools": tools,
            "contents": contents,
            "generationConfig": body_base["generationConfig"],
        }
        try:
            response = _http_json("POST", url, api_key, body)
        except Exception as e:
            summary = "; ".join(
                f"{t['tool']}: {json.dumps(t['result'], default=str)[:120]}"
                for t in tool_results
            )
            return {
                "error": None,
                "reply": f"Actions ran, but Gemini could not summarize ({e}). Results: {summary}",
                "tool_results": tool_results,
            }

    reply = _extract_text_from_api(response)
    if not reply:
        reason = _finish_reason(response)
        if tool_results:
            reply = "Done. " + "; ".join(
                f"{t['tool']}: {json.dumps(t['result'], default=str)[:120]}"
                for t in tool_results
            )
        elif "SAFETY" in reason.upper():
            return {
                "error": "Gemini blocked the response for safety reasons. Try rephrasing.",
                "reply": None,
                "tool_results": tool_results,
            }
        else:
            try:
                url = f"{API_BASE}/models/{model_used}:generateContent"
                plain = _http_json("POST", url, api_key, {
                    "contents": [{"role": "user", "parts": [{"text": user_message}]}],
                })
                reply = _extract_text_from_api(plain)
            except Exception as e:
                return {
                    "error": f"Gemini returned empty reply (model={model_used}): {e}",
                    "reply": None,
                    "tool_results": tool_results,
                }
            if not reply:
                return {
                    "error": (
                        f"Gemini returned empty reply (model={model_used}, finish={reason}). "
                        "Check the API key is valid and Generative Language API is enabled."
                    ),
                    "reply": None,
                    "tool_results": tool_results,
                }

    return {"reply": reply, "tool_results": tool_results, "error": None}
