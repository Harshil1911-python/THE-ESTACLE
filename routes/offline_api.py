"""Offline snapshot + mutation sync API."""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request, session
from core.db import get_db, migrate_db
from core.helpers import login_required, role_required, log_activity

offline_api = Blueprint('offline_api', __name__)


def _rows(cur):
    return [dict(r) for r in cur.fetchall()]


@offline_api.route('/api/offline/snapshot', methods=['GET'])
@login_required
@role_required('admin', 'agent')
def offline_snapshot():
    migrate_db()
    db = get_db()
    role = session.get('role')
    uid = session.get('user_id')

    def q(sql, args=()):
        return _rows(db.execute(sql, args))

    if role == 'agent':
        clients = q(
            'SELECT id, full_name, email, phone, status, notes, agent_id, created_at FROM clients WHERE agent_id = ? OR agent_id IS NULL ORDER BY id DESC LIMIT 500',
            (uid,),
        )
        properties = q(
            'SELECT id, title, description, price, property_type, status, address, city, state, bedrooms, bathrooms, area_sqft, agent_id, created_at FROM properties WHERE agent_id = ? OR agent_id IS NULL ORDER BY id DESC LIMIT 500',
            (uid,),
        )
        tasks = q(
            'SELECT id, title, description, due_date, status, priority, assigned_to, related_client_id, related_property_id, created_at FROM tasks WHERE assigned_to = ? OR created_by = ? ORDER BY id DESC LIMIT 300',
            (uid, uid),
        )
        appointments = q(
            'SELECT id, client_id, property_id, agent_id, appointment_date, status, notes, created_at FROM appointments WHERE agent_id = ? ORDER BY id DESC LIMIT 300',
            (uid,),
        )
        leads = q(
            'SELECT id, full_name, email, phone, source, interest, budget, status, notes, assigned_to, created_at FROM leads WHERE assigned_to = ? OR assigned_to IS NULL ORDER BY id DESC LIMIT 300',
            (uid,),
        )
        deals = q(
            'SELECT id, title, client_id, property_id, stage, value, agent_id, notes, created_at FROM deals WHERE agent_id = ? ORDER BY id DESC LIMIT 300',
            (uid,),
        )
    else:
        clients = q('SELECT id, full_name, email, phone, status, notes, agent_id, created_at FROM clients ORDER BY id DESC LIMIT 800')
        properties = q('SELECT id, title, description, price, property_type, status, address, city, state, bedrooms, bathrooms, area_sqft, agent_id, created_at FROM properties ORDER BY id DESC LIMIT 800')
        tasks = q('SELECT id, title, description, due_date, status, priority, assigned_to, related_client_id, related_property_id, created_at FROM tasks ORDER BY id DESC LIMIT 500')
        appointments = q('SELECT id, client_id, property_id, agent_id, appointment_date, status, notes, created_at FROM appointments ORDER BY id DESC LIMIT 500')
        leads = q('SELECT id, full_name, email, phone, source, interest, budget, status, notes, assigned_to, created_at FROM leads ORDER BY id DESC LIMIT 500')
        try:
            deals = q('SELECT id, title, client_id, property_id, stage, value, agent_id, notes, created_at FROM deals ORDER BY id DESC LIMIT 500')
        except Exception:
            deals = []

    users = q("SELECT id, full_name, email, role, phone FROM users WHERE is_active = 1 ORDER BY full_name LIMIT 200")

    return jsonify({
        'ok': True,
        'synced_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'user': {'id': uid, 'role': role, 'name': session.get('full_name') or session.get('email')},
        'data': {
            'clients': clients,
            'properties': properties,
            'tasks': tasks,
            'appointments': appointments,
            'leads': leads,
            'deals': deals,
            'users': users,
        },
    })


@offline_api.route('/api/offline/sync', methods=['POST'])
@login_required
@role_required('admin', 'agent')
def offline_sync():
    migrate_db()
    db = get_db()
    payload = request.get_json(silent=True) or {}
    mutations = payload.get('mutations') or []
    results = []
    uid = session.get('user_id')

    for m in mutations:
        mid = m.get('id')
        entity = (m.get('entity') or '').strip()
        action = (m.get('action') or 'create').strip()
        data = m.get('data') or {}
        try:
            if entity == 'clients' and action == 'create':
                cur = db.execute(
                    'INSERT INTO clients (full_name, email, phone, status, notes, agent_id) VALUES (?,?,?,?,?,?)',
                    (
                        (data.get('full_name') or '').strip() or 'Offline client',
                        data.get('email'),
                        data.get('phone'),
                        data.get('status') or 'lead',
                        data.get('notes'),
                        data.get('agent_id') or uid,
                    ),
                )
                new_id = cur.lastrowid
                log_activity('Created client (offline sync)', 'client', new_id, data.get('full_name'))
                results.append({'id': mid, 'ok': True, 'server_id': new_id})
            elif entity == 'leads' and action == 'create':
                cur = db.execute(
                    'INSERT INTO leads (full_name, email, phone, source, interest, budget, status, notes, assigned_to) VALUES (?,?,?,?,?,?,?,?,?)',
                    (
                        (data.get('full_name') or '').strip() or 'Offline lead',
                        data.get('email'),
                        data.get('phone'),
                        data.get('source') or 'offline',
                        data.get('interest'),
                        data.get('budget'),
                        data.get('status') or 'new',
                        data.get('notes'),
                        data.get('assigned_to') or uid,
                    ),
                )
                new_id = cur.lastrowid
                log_activity('Created lead (offline sync)', 'lead', new_id, data.get('full_name'))
                results.append({'id': mid, 'ok': True, 'server_id': new_id})
            elif entity == 'tasks' and action == 'create':
                cur = db.execute(
                    'INSERT INTO tasks (title, description, due_date, status, priority, assigned_to, related_client_id, related_property_id, created_by) VALUES (?,?,?,?,?,?,?,?,?)',
                    (
                        (data.get('title') or '').strip() or 'Offline task',
                        data.get('description'),
                        data.get('due_date'),
                        data.get('status') or 'pending',
                        data.get('priority') or 'medium',
                        data.get('assigned_to') or uid,
                        data.get('related_client_id'),
                        data.get('related_property_id'),
                        uid,
                    ),
                )
                new_id = cur.lastrowid
                log_activity('Created task (offline sync)', 'task', new_id, data.get('title'))
                results.append({'id': mid, 'ok': True, 'server_id': new_id})
            elif entity == 'appointments' and action == 'create':
                cur = db.execute(
                    'INSERT INTO appointments (client_id, property_id, agent_id, appointment_date, status, notes) VALUES (?,?,?,?,?,?)',
                    (
                        data.get('client_id'),
                        data.get('property_id'),
                        data.get('agent_id') or uid,
                        data.get('appointment_date'),
                        data.get('status') or 'scheduled',
                        data.get('notes') or 'Created offline',
                    ),
                )
                new_id = cur.lastrowid
                log_activity('Created appointment (offline sync)', 'appointment', new_id, None)
                results.append({'id': mid, 'ok': True, 'server_id': new_id})
            elif entity == 'tasks' and action == 'update_status':
                tid = data.get('id')
                status = data.get('status') or 'pending'
                db.execute('UPDATE tasks SET status = ? WHERE id = ?', (status, tid))
                log_activity('Updated task status (offline sync)', 'task', tid, status)
                results.append({'id': mid, 'ok': True, 'server_id': tid})
            else:
                results.append({'id': mid, 'ok': False, 'error': f'Unsupported {entity}/{action}'})
        except Exception as e:
            results.append({'id': mid, 'ok': False, 'error': str(e)})

    db.commit()
    return jsonify({'ok': True, 'results': results})
