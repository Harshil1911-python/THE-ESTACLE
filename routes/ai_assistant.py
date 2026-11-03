"""Estacle AI - Gemini assistant for CRM actions."""
from __future__ import annotations

import json
from flask import (
    Blueprint, render_template, request, jsonify, session, flash, redirect, url_for
)
from core.db import get_db, migrate_db
from core.helpers import (
    login_required, role_required, get_setting, set_setting, log_activity
)

ai_bp = Blueprint('ai', __name__)


def _db():
    migrate_db()
    return get_db()


def tool_list_clients(status=None, limit=20):
    db = _db()
    limit = max(1, min(int(limit or 20), 50))
    if status:
        rows = db.execute(
            'SELECT id, full_name, email, phone, status, budget, preferred_city FROM clients WHERE status = ? ORDER BY id DESC LIMIT ?',
            (status, limit)
        ).fetchall()
    else:
        rows = db.execute(
            'SELECT id, full_name, email, phone, status, budget, preferred_city FROM clients ORDER BY id DESC LIMIT ?',
            (limit,)
        ).fetchall()
    return {'clients': [dict(r) for r in rows], 'count': len(rows)}


def tool_create_client(full_name, email=None, phone=None, status='lead', notes=None, budget=None, preferred_city=None, source=None):
    if not full_name or not str(full_name).strip():
        return {'error': 'full_name is required'}
    db = _db()
    cur = db.execute(
        'INSERT INTO clients (full_name, email, phone, status, notes, budget, preferred_city, source) VALUES (?,?,?,?,?,?,?,?)',
        (full_name.strip(), (email or '').strip() or None, (phone or '').strip() or None, status or 'lead', notes, budget, preferred_city, source)
    )
    db.commit()
    cid = cur.lastrowid
    log_activity('AI created client', 'client', cid, full_name.strip())
    return {'success': True, 'client_id': cid, 'full_name': full_name.strip()}


def tool_update_client(client_id, **fields):
    db = _db()
    if not db.execute('SELECT id FROM clients WHERE id = ?', (client_id,)).fetchone():
        return {'error': f'Client {client_id} not found'}
    allowed = {'full_name', 'email', 'phone', 'status', 'notes', 'budget', 'preferred_city', 'source', 'interest', 'address'}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return {'error': 'No valid fields'}
    sets = ', '.join(f'{k} = ?' for k in updates)
    db.execute(f'UPDATE clients SET {sets} WHERE id = ?', list(updates.values()) + [client_id])
    db.commit()
    log_activity('AI updated client', 'client', client_id, str(updates))
    return {'success': True, 'client_id': client_id, 'updated': updates}


def tool_list_properties(status=None, city=None, limit=20):
    db = _db()
    limit = max(1, min(int(limit or 20), 50))
    q = 'SELECT id, title, price, property_type, status, city, bedrooms, bathrooms, listing_type FROM properties WHERE 1=1'
    params = []
    if status:
        q += ' AND status = ?'
        params.append(status)
    if city:
        q += ' AND lower(city) LIKE ?'
        params.append(f'%{city.lower()}%')
    q += ' ORDER BY id DESC LIMIT ?'
    params.append(limit)
    rows = db.execute(q, params).fetchall()
    return {'properties': [dict(r) for r in rows], 'count': len(rows)}


def tool_create_property(title, price, property_type='apartment', status='available', listing_type='sale', city=None, address=None, bedrooms=None, bathrooms=None, area_sqft=None, description=None):
    if not title or price is None:
        return {'error': 'title and price required'}
    db = _db()
    cur = db.execute(
        'INSERT INTO properties (title, description, price, property_type, status, listing_type, city, address, bedrooms, bathrooms, area_sqft) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
        (title.strip(), description, float(price), property_type or 'apartment', status or 'available', listing_type or 'sale', city, address, bedrooms, bathrooms, area_sqft)
    )
    db.commit()
    pid = cur.lastrowid
    log_activity('AI created property', 'property', pid, title.strip())
    return {'success': True, 'property_id': pid, 'title': title.strip()}


def tool_update_property(property_id, **fields):
    db = _db()
    if not db.execute('SELECT id FROM properties WHERE id = ?', (property_id,)).fetchone():
        return {'error': f'Property {property_id} not found'}
    allowed = {'title', 'description', 'price', 'property_type', 'status', 'listing_type', 'city', 'address', 'bedrooms', 'bathrooms', 'area_sqft', 'state', 'zip_code'}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return {'error': 'No valid fields'}
    sets = ', '.join(f'{k} = ?' for k in updates)
    db.execute(f'UPDATE properties SET {sets} WHERE id = ?', list(updates.values()) + [property_id])
    db.commit()
    log_activity('AI updated property', 'property', property_id, str(updates))
    return {'success': True, 'property_id': property_id, 'updated': updates}


def tool_list_users(role=None, limit=20):
    db = _db()
    limit = max(1, min(int(limit or 20), 50))
    if role:
        rows = db.execute('SELECT id, full_name, email, role, phone, is_active FROM users WHERE role = ? ORDER BY id DESC LIMIT ?', (role, limit)).fetchall()
    else:
        rows = db.execute('SELECT id, full_name, email, role, phone, is_active FROM users ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
    return {'users': [dict(r) for r in rows], 'count': len(rows)}


def tool_create_user(full_name, email, password, role='agent', phone=None):
    if not full_name or not email or not password:
        return {'error': 'full_name, email and password required'}
    if role not in ('admin', 'agent', 'customer'):
        return {'error': 'role must be admin, agent or customer'}
    from werkzeug.security import generate_password_hash
    db = _db()
    if db.execute('SELECT id FROM users WHERE email = ?', (email.strip().lower(),)).fetchone():
        return {'error': f'Email {email} already exists'}
    cur = db.execute(
        'INSERT INTO users (full_name, email, password, role, phone) VALUES (?,?,?,?,?)',
        (full_name.strip(), email.strip().lower(), generate_password_hash(password), role, phone)
    )
    db.commit()
    uid = cur.lastrowid
    log_activity('AI created user', 'user', uid, f'{full_name} ({role})')
    return {'success': True, 'user_id': uid, 'email': email.strip().lower(), 'role': role}


def tool_schedule_appointment(client_id=None, property_id=None, agent_id=None, appointment_date=None, notes=None, client_name=None):
    db = _db()
    if client_name and not client_id:
        row = db.execute(
            'SELECT id FROM clients WHERE lower(full_name) LIKE ? ORDER BY id DESC LIMIT 1',
            (f'%{client_name.lower()}%',)
        ).fetchone()
        if not row:
            return {'error': f'No client matching "{client_name}"'}
        client_id = row['id']
    if not appointment_date:
        return {'error': 'appointment_date required (YYYY-MM-DD HH:MM)'}
    ad = appointment_date.replace('T', ' ').strip()
    cur = db.execute(
        "INSERT INTO appointments (client_id, property_id, agent_id, appointment_date, status, notes) VALUES (?,?,?,?,'scheduled',?)",
        (client_id, property_id, agent_id or session.get('user_id'), ad, notes)
    )
    db.commit()
    aid = cur.lastrowid
    log_activity('AI scheduled appointment', 'appointment', aid, ad)
    return {'success': True, 'appointment_id': aid, 'appointment_date': ad, 'client_id': client_id}


def tool_create_task(title, description=None, due_date=None, priority='medium', assigned_to=None, related_client_id=None):
    if not title:
        return {'error': 'title required'}
    db = _db()
    priority = priority if priority in ('low', 'medium', 'high') else 'medium'
    cur = db.execute(
        "INSERT INTO tasks (title, description, due_date, priority, status, assigned_to, related_client_id, created_by) VALUES (?,?,?,?,?,?,?,?)",
        (title.strip(), description, due_date, priority, 'pending', assigned_to, related_client_id, session.get('user_id'))
    )
    db.commit()
    tid = cur.lastrowid
    log_activity('AI created task', 'task', tid, title.strip())
    return {'success': True, 'task_id': tid, 'title': title.strip()}


def tool_list_tasks(status=None, limit=15):
    db = _db()
    limit = max(1, min(int(limit or 15), 40))
    if status:
        rows = db.execute(
            'SELECT t.id, t.title, t.due_date, t.priority, t.status, u.full_name as assigned_name FROM tasks t LEFT JOIN users u ON t.assigned_to = u.id WHERE t.status = ? ORDER BY t.id DESC LIMIT ?',
            (status, limit)
        ).fetchall()
    else:
        rows = db.execute(
            'SELECT t.id, t.title, t.due_date, t.priority, t.status, u.full_name as assigned_name FROM tasks t LEFT JOIN users u ON t.assigned_to = u.id ORDER BY t.id DESC LIMIT ?',
            (limit,)
        ).fetchall()
    return {'tasks': [dict(r) for r in rows], 'count': len(rows)}


def tool_create_deal(title, value=0, stage='offer', client_id=None, property_id=None, agent_id=None, notes=None):
    if not title:
        return {'error': 'title required'}
    db = _db()
    cur = db.execute(
        'INSERT INTO deals (title, value, stage, client_id, property_id, agent_id, notes) VALUES (?,?,?,?,?,?,?)',
        (title.strip(), float(value or 0), stage or 'offer', client_id, property_id, agent_id or session.get('user_id'), notes)
    )
    db.commit()
    did = cur.lastrowid
    log_activity('AI created deal', 'deal', did, title.strip())
    return {'success': True, 'deal_id': did, 'title': title.strip()}


def tool_search(query, limit=10):
    if not query or not query.strip():
        return {'error': 'query required'}
    db = _db()
    q = f'%{query.strip()}%'
    limit = max(1, min(int(limit or 10), 20))
    clients = db.execute('SELECT id, full_name, email, phone, status FROM clients WHERE full_name LIKE ? OR email LIKE ? OR phone LIKE ? LIMIT ?', (q, q, q, limit)).fetchall()
    props = db.execute('SELECT id, title, price, city, status FROM properties WHERE title LIKE ? OR city LIKE ? OR address LIKE ? LIMIT ?', (q, q, q, limit)).fetchall()
    users = db.execute('SELECT id, full_name, email, role FROM users WHERE full_name LIKE ? OR email LIKE ? LIMIT ?', (q, q, limit)).fetchall()
    return {'clients': [dict(r) for r in clients], 'properties': [dict(r) for r in props], 'users': [dict(r) for r in users]}


def tool_get_stats():
    db = _db()
    return {
        'users': db.execute('SELECT COUNT(*) FROM users').fetchone()[0],
        'agents': db.execute("SELECT COUNT(*) FROM users WHERE role='agent'").fetchone()[0],
        'properties': db.execute('SELECT COUNT(*) FROM properties').fetchone()[0],
        'available_properties': db.execute("SELECT COUNT(*) FROM properties WHERE status='available'").fetchone()[0],
        'clients': db.execute('SELECT COUNT(*) FROM clients').fetchone()[0],
        'tasks_open': db.execute("SELECT COUNT(*) FROM tasks WHERE status IN ('pending','in_progress','open')").fetchone()[0],
        'appointments': db.execute('SELECT COUNT(*) FROM appointments').fetchone()[0],
        'deals': db.execute('SELECT COUNT(*) FROM deals').fetchone()[0],
        'currency': get_setting('currency', 'INR'),
    }


TOOL_IMPL = {
    'list_clients': tool_list_clients,
    'create_client': tool_create_client,
    'update_client': tool_update_client,
    'list_properties': tool_list_properties,
    'create_property': tool_create_property,
    'update_property': tool_update_property,
    'list_users': tool_list_users,
    'create_user': tool_create_user,
    'schedule_appointment': tool_schedule_appointment,
    'create_task': tool_create_task,
    'list_tasks': tool_list_tasks,
    'create_deal': tool_create_deal,
    'search': tool_search,
    'get_stats': tool_get_stats,
}

GEMINI_TOOLS = [
    {'name': 'list_clients', 'description': 'List clients/leads', 'parameters': {'type': 'object', 'properties': {'status': {'type': 'string'}, 'limit': {'type': 'integer'}}}},
    {'name': 'create_client', 'description': 'Create client/lead', 'parameters': {'type': 'object', 'properties': {'full_name': {'type': 'string'}, 'email': {'type': 'string'}, 'phone': {'type': 'string'}, 'status': {'type': 'string'}, 'notes': {'type': 'string'}, 'budget': {'type': 'number'}, 'preferred_city': {'type': 'string'}, 'source': {'type': 'string'}}, 'required': ['full_name']}},
    {'name': 'update_client', 'description': 'Update client by id', 'parameters': {'type': 'object', 'properties': {'client_id': {'type': 'integer'}, 'full_name': {'type': 'string'}, 'email': {'type': 'string'}, 'phone': {'type': 'string'}, 'status': {'type': 'string'}, 'notes': {'type': 'string'}, 'budget': {'type': 'number'}}, 'required': ['client_id']}},
    {'name': 'list_properties', 'description': 'List properties', 'parameters': {'type': 'object', 'properties': {'status': {'type': 'string'}, 'city': {'type': 'string'}, 'limit': {'type': 'integer'}}}},
    {'name': 'create_property', 'description': 'Add property', 'parameters': {'type': 'object', 'properties': {'title': {'type': 'string'}, 'price': {'type': 'number'}, 'property_type': {'type': 'string'}, 'status': {'type': 'string'}, 'listing_type': {'type': 'string'}, 'city': {'type': 'string'}, 'address': {'type': 'string'}, 'bedrooms': {'type': 'integer'}, 'bathrooms': {'type': 'number'}, 'area_sqft': {'type': 'number'}, 'description': {'type': 'string'}}, 'required': ['title', 'price']}},
    {'name': 'update_property', 'description': 'Update property', 'parameters': {'type': 'object', 'properties': {'property_id': {'type': 'integer'}, 'title': {'type': 'string'}, 'price': {'type': 'number'}, 'status': {'type': 'string'}, 'city': {'type': 'string'}}, 'required': ['property_id']}},
    {'name': 'list_users', 'description': 'List users', 'parameters': {'type': 'object', 'properties': {'role': {'type': 'string'}, 'limit': {'type': 'integer'}}}},
    {'name': 'create_user', 'description': 'Create user', 'parameters': {'type': 'object', 'properties': {'full_name': {'type': 'string'}, 'email': {'type': 'string'}, 'password': {'type': 'string'}, 'role': {'type': 'string'}, 'phone': {'type': 'string'}}, 'required': ['full_name', 'email', 'password']}},
    {'name': 'schedule_appointment', 'description': 'Schedule viewing YYYY-MM-DD HH:MM', 'parameters': {'type': 'object', 'properties': {'client_id': {'type': 'integer'}, 'client_name': {'type': 'string'}, 'property_id': {'type': 'integer'}, 'agent_id': {'type': 'integer'}, 'appointment_date': {'type': 'string'}, 'notes': {'type': 'string'}}, 'required': ['appointment_date']}},
    {'name': 'create_task', 'description': 'Create task', 'parameters': {'type': 'object', 'properties': {'title': {'type': 'string'}, 'description': {'type': 'string'}, 'due_date': {'type': 'string'}, 'priority': {'type': 'string'}, 'assigned_to': {'type': 'integer'}, 'related_client_id': {'type': 'integer'}}, 'required': ['title']}},
    {'name': 'list_tasks', 'description': 'List tasks', 'parameters': {'type': 'object', 'properties': {'status': {'type': 'string'}, 'limit': {'type': 'integer'}}}},
    {'name': 'create_deal', 'description': 'Create deal', 'parameters': {'type': 'object', 'properties': {'title': {'type': 'string'}, 'value': {'type': 'number'}, 'stage': {'type': 'string'}, 'client_id': {'type': 'integer'}, 'property_id': {'type': 'integer'}, 'notes': {'type': 'string'}}, 'required': ['title']}},
    {'name': 'search', 'description': 'Search CRM', 'parameters': {'type': 'object', 'properties': {'query': {'type': 'string'}, 'limit': {'type': 'integer'}}, 'required': ['query']}},
    {'name': 'get_stats', 'description': 'CRM counts', 'parameters': {'type': 'object', 'properties': {}}},
]

SYSTEM_PROMPT = 'You are Estacle AI for a real estate CRM. Use tools for all data operations. Be concise. Dates: appointments YYYY-MM-DD HH:MM, tasks YYYY-MM-DD.'


def _run_gemini(api_key, user_message, history=None):
    try:
        import google.generativeai as genai
    except ImportError:
        return {'error': 'Install google-generativeai: pip install google-generativeai', 'reply': None, 'tool_results': []}
    genai.configure(api_key=api_key)
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
    model = genai.GenerativeModel(model_name='gemini-2.0-flash', tools=tools, system_instruction=SYSTEM_PROMPT)
    chat_history = []
    for h in (history or [])[-12:]:
        if h.get('role') == 'user':
            chat_history.append({'role': 'user', 'parts': [h.get('content', '')]})
        elif h.get('role') == 'assistant':
            chat_history.append({'role': 'model', 'parts': [h.get('content', '')]})
    chat = model.start_chat(history=chat_history)
    tool_results = []
    try:
        response = chat.send_message(user_message)
    except Exception as e:
        return {'error': str(e), 'reply': None, 'tool_results': []}
    for _ in range(6):
        calls = []
        try:
            for cand in response.candidates:
                for part in cand.content.parts:
                    fc = getattr(part, 'function_call', None)
                    if fc and getattr(fc, 'name', None):
                        calls.append((fc.name, dict(fc.args) if fc.args else {}))
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
            response_parts.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=name, response={'result': result}
                    )
                )
            )
        try:
            response = chat.send_message(response_parts)
        except Exception:
            try:
                response = chat.send_message('Tool results:\n' + json.dumps(tool_results, default=str))
            except Exception as e2:
                return {'error': str(e2), 'reply': None, 'tool_results': tool_results}
    reply = ''
    try:
        reply = (response.text or '').strip()
    except Exception:
        if tool_results:
            reply = 'Done. ' + '; '.join(
                f"{t['tool']}: {json.dumps(t['result'], default=str)[:100]}" for t in tool_results
            )
        else:
            reply = 'Completed.'
    return {'reply': reply, 'tool_results': tool_results, 'error': None}


@ai_bp.route('/admin/ai', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def estacle_ai():
    if request.method == 'POST' and request.form.get('action') == 'save_key':
        key = (request.form.get('gemini_api_key') or '').strip()
        set_setting('gemini_api_key', key)
        flash('Gemini API key saved.' if key else 'API key cleared.', 'success')
        return redirect(url_for('ai.estacle_ai'))
    api_key = get_setting('gemini_api_key', '')
    masked = ''
    if api_key:
        masked = api_key[:6] + '...' + api_key[-4:] if len(api_key) > 12 else '********'
    return render_template('admin_ai.html', has_key=bool(api_key), masked_key=masked)


@ai_bp.route('/admin/ai/chat', methods=['POST'])
@login_required
@role_required('admin')
def estacle_ai_chat():
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    history = data.get('history') or []
    if not message:
        return jsonify({'error': 'Empty message'}), 400
    api_key = get_setting('gemini_api_key', '')
    if not api_key:
        return jsonify({
            'error': 'No Gemini API key. Open ESTACLE AI and save your key from Google AI Studio.',
            'reply': None,
        }), 400
    result = _run_gemini(api_key, message, history)
    if result.get('error') and not result.get('reply'):
        return jsonify(result), 502
    return jsonify(result)
