"""CRM tool implementations for Estacle AI."""
from __future__ import annotations
from flask import session
from core.db import get_db, migrate_db
from core.helpers import get_setting, log_activity

def _db():
    migrate_db()
    return get_db()

def tool_list_clients(status=None, limit=20):
    db = _db()
    limit = max(1, min(int(limit or 20), 50))
    if status:
        rows = db.execute('SELECT id, full_name, email, phone, status, budget, preferred_city, created_at FROM clients WHERE status = ? ORDER BY id DESC LIMIT ?', (status, limit)).fetchall()
    else:
        rows = db.execute('SELECT id, full_name, email, phone, status, budget, preferred_city, created_at FROM clients ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
    return {'clients': [dict(r) for r in rows], 'count': len(rows)}

def tool_create_client(full_name, email=None, phone=None, status='lead', notes=None, budget=None, preferred_city=None, source=None):
    if not full_name or not str(full_name).strip():
        return {'error': 'full_name is required'}
    db = _db()
    cur = db.execute('INSERT INTO clients (full_name, email, phone, status, notes, budget, preferred_city, source) VALUES (?,?,?,?,?,?,?,?)',
        (full_name.strip(), (email or '').strip() or None, (phone or '').strip() or None, status or 'lead', notes, budget, preferred_city, source))
    db.commit()
    cid = cur.lastrowid
    log_activity('AI created client', 'client', cid, full_name.strip())
    return {'success': True, 'client_id': cid, 'full_name': full_name.strip()}

def tool_update_client(client_id, **fields):
    db = _db()
    if not db.execute('SELECT id FROM clients WHERE id = ?', (client_id,)).fetchone():
        return {'error': f'Client {client_id} not found'}
    allowed = {'full_name','email','phone','status','notes','budget','preferred_city','source','interest','address'}
    updates = {k:v for k,v in fields.items() if k in allowed and v is not None}
    if not updates:
        return {'error': 'No valid fields to update'}
    sets = ', '.join(f'{k} = ?' for k in updates)
    db.execute(f'UPDATE clients SET {sets} WHERE id = ?', list(updates.values()) + [client_id])
    db.commit()
    log_activity('AI updated client', 'client', client_id, str(updates))
    return {'success': True, 'client_id': client_id, 'updated': updates}

def tool_list_properties(status=None, city=None, limit=20):
    db = _db()
    limit = max(1, min(int(limit or 20), 50))
    q, params = 'SELECT id, title, price, property_type, status, city, bedrooms, bathrooms, listing_type FROM properties WHERE 1=1', []
    if status:
        q += ' AND status = ?'; params.append(status)
    if city:
        q += ' AND lower(city) LIKE ?'; params.append(f'%{city.lower()}%')
    q += ' ORDER BY id DESC LIMIT ?'; params.append(limit)
    rows = db.execute(q, params).fetchall()
    return {'properties': [dict(r) for r in rows], 'count': len(rows)}

def tool_create_property(title, price, property_type='apartment', status='available', listing_type='sale', city=None, address=None, bedrooms=None, bathrooms=None, area_sqft=None, description=None):
    if not title or price is None:
        return {'error': 'title and price are required'}
    db = _db()
    cur = db.execute('INSERT INTO properties (title, description, price, property_type, status, listing_type, city, address, bedrooms, bathrooms, area_sqft) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
        (title.strip(), description, float(price), property_type or 'apartment', status or 'available', listing_type or 'sale', city, address, bedrooms, bathrooms, area_sqft))
    db.commit()
    pid = cur.lastrowid
    log_activity('AI created property', 'property', pid, title.strip())
    return {'success': True, 'property_id': pid, 'title': title.strip()}

def tool_update_property(property_id, **fields):
    db = _db()
    if not db.execute('SELECT id FROM properties WHERE id = ?', (property_id,)).fetchone():
        return {'error': f'Property {property_id} not found'}
    allowed = {'title','description','price','property_type','status','listing_type','city','address','bedrooms','bathrooms','area_sqft','state','zip_code'}
    updates = {k:v for k,v in fields.items() if k in allowed and v is not None}
    if not updates:
        return {'error': 'No valid fields to update'}
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
        return {'error': 'full_name, email and password are required'}
    if role not in ('admin', 'agent', 'customer'):
        return {'error': 'role must be admin, agent or customer'}
    from werkzeug.security import generate_password_hash
    db = _db()
    if db.execute('SELECT id FROM users WHERE email = ?', (email.strip().lower(),)).fetchone():
        return {'error': f'Email {email} already exists'}
    cur = db.execute('INSERT INTO users (full_name, email, password, role, phone) VALUES (?,?,?,?,?)',
        (full_name.strip(), email.strip().lower(), generate_password_hash(password), role, phone))
    db.commit()
    uid = cur.lastrowid
    log_activity('AI created user', 'user', uid, f'{full_name} ({role})')
    return {'success': True, 'user_id': uid, 'email': email.strip().lower(), 'role': role}

def tool_schedule_appointment(client_id=None, property_id=None, agent_id=None, appointment_date=None, notes=None, client_name=None):
    db = _db()
    if client_name and not client_id:
        row = db.execute('SELECT id FROM clients WHERE lower(full_name) LIKE ? ORDER BY id DESC LIMIT 1', (f'%{client_name.lower()}%',)).fetchone()
        if not row:
            return {'error': f'No client found matching "{client_name}"'}
        client_id = row['id']
    if not appointment_date:
        return {'error': 'appointment_date is required (YYYY-MM-DD HH:MM)'}
    ad = appointment_date.replace('T', ' ').strip()
    cur = db.execute("INSERT INTO appointments (client_id, property_id, agent_id, appointment_date, status, notes) VALUES (?,?,?,?,'scheduled',?)",
        (client_id, property_id, agent_id or session.get('user_id'), ad, notes))
    db.commit()
    aid = cur.lastrowid
    log_activity('AI scheduled appointment', 'appointment', aid, ad)
    return {'success': True, 'appointment_id': aid, 'appointment_date': ad, 'client_id': client_id, 'property_id': property_id}

def tool_create_task(title, description=None, due_date=None, priority='medium', assigned_to=None, related_client_id=None):
    if not title:
        return {'error': 'title is required'}
    db = _db()
    priority = priority if priority in ('low', 'medium', 'high') else 'medium'
    cur = db.execute("INSERT INTO tasks (title, description, due_date, priority, status, assigned_to, related_client_id, created_by) VALUES (?,?,?,?,?,?,?,?)",
        (title.strip(), description, due_date, priority, 'pending', assigned_to, related_client_id, session.get('user_id')))
    db.commit()
    tid = cur.lastrowid
    log_activity('AI created task', 'task', tid, title.strip())
    return {'success': True, 'task_id': tid, 'title': title.strip()}

def tool_list_tasks(status=None, limit=15):
    db = _db()
    limit = max(1, min(int(limit or 15), 40))
    if status:
        rows = db.execute('SELECT t.id, t.title, t.due_date, t.priority, t.status, u.full_name as assigned_name FROM tasks t LEFT JOIN users u ON t.assigned_to = u.id WHERE t.status = ? ORDER BY t.id DESC LIMIT ?', (status, limit)).fetchall()
    else:
        rows = db.execute('SELECT t.id, t.title, t.due_date, t.priority, t.status, u.full_name as assigned_name FROM tasks t LEFT JOIN users u ON t.assigned_to = u.id ORDER BY t.id DESC LIMIT ?', (limit,)).fetchall()
    return {'tasks': [dict(r) for r in rows], 'count': len(rows)}

def tool_create_deal(title, value=0, stage='offer', client_id=None, property_id=None, agent_id=None, notes=None):
    if not title:
        return {'error': 'title is required'}
    db = _db()
    cur = db.execute('INSERT INTO deals (title, value, stage, client_id, property_id, agent_id, notes) VALUES (?,?,?,?,?,?,?)',
        (title.strip(), float(value or 0), stage or 'offer', client_id, property_id, agent_id or session.get('user_id'), notes))
    db.commit()
    did = cur.lastrowid
    log_activity('AI created deal', 'deal', did, title.strip())
    return {'success': True, 'deal_id': did, 'title': title.strip()}

def tool_search(query, limit=10):
    if not query or not query.strip():
        return {'error': 'query is required'}
    db = _db()
    q = f'%{query.strip()}%'
    limit = max(1, min(int(limit or 10), 20))
    clients = db.execute('SELECT id, full_name, email, phone, status FROM clients WHERE full_name LIKE ? OR email LIKE ? OR phone LIKE ? LIMIT ?', (q,q,q,limit)).fetchall()
    props = db.execute('SELECT id, title, price, city, status FROM properties WHERE title LIKE ? OR city LIKE ? OR address LIKE ? LIMIT ?', (q,q,q,limit)).fetchall()
    users = db.execute('SELECT id, full_name, email, role FROM users WHERE full_name LIKE ? OR email LIKE ? LIMIT ?', (q,q,limit)).fetchall()
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
