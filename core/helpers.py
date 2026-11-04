from functools import wraps
from flask import session, flash, redirect, url_for
from core.db import get_db


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            from flask import request, jsonify
            wants_json = (
                request.path.endswith('/chat')
                or 'application/json' in (request.headers.get('Accept') or '')
                or request.is_json
                or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            )
            if wants_json:
                return jsonify({'error': 'Please log in to continue.', 'reply': None}), 401
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import request, jsonify
            wants_json = (
                request.path.endswith('/chat')
                or 'application/json' in (request.headers.get('Accept') or '')
                or request.is_json
                or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            )
            if 'user_id' not in session:
                if wants_json:
                    return jsonify({'error': 'Please log in to continue.', 'reply': None}), 401
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login'))
            if session.get('role') not in roles:
                if wants_json:
                    return jsonify({'error': 'You do not have permission for this action.', 'reply': None}), 403
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('auth.role_redirect'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_setting(key, default=''):
    db = get_db()
    row = db.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
    return row['value'] if row else default


def set_setting(key, value):
    db = get_db()
    db.execute(
        'INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value',
        (key, value)
    )
    db.commit()


def format_money(amount, currency=None):
    if amount is None:
        return '-'
    currency = currency or get_setting('currency', 'INR')
    symbols = {'USD': '$', 'INR': 'Rs.', 'AED': 'AED '}
    sym = symbols.get(currency, currency + ' ')
    try:
        return f"{sym}{float(amount):,.0f}"
    except (TypeError, ValueError):
        return str(amount)


def is_online_mode() -> bool:
    """True when the platform is in online (sync) mode."""
    return (get_setting('connection_mode', 'online') or 'online').lower() != 'offline'


def queue_sync_event(entity_type, entity_id, action, payload=None):
    """Record a local change made while offline so it can sync when online."""
    try:
        import json
        from datetime import datetime
        db = get_db()
        db.execute(
            """CREATE TABLE IF NOT EXISTS pending_sync (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                action TEXT NOT NULL,
                payload TEXT,
                created_at TEXT NOT NULL,
                synced_at TEXT
            )"""
        )
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.execute(
            'INSERT INTO pending_sync (entity_type, entity_id, action, payload, created_at) VALUES (?, ?, ?, ?, ?)',
            (
                entity_type,
                entity_id,
                action,
                json.dumps(payload, default=str) if payload is not None else None,
                now,
            ),
        )
        db.commit()
    except Exception as e:
        try:
            import sys
            print(f'[queue_sync_event] {e}', file=sys.stderr)
        except Exception:
            pass


def pending_sync_count() -> int:
    try:
        db = get_db()
        db.execute(
            """CREATE TABLE IF NOT EXISTS pending_sync (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                action TEXT NOT NULL,
                payload TEXT,
                created_at TEXT NOT NULL,
                synced_at TEXT
            )"""
        )
        row = db.execute('SELECT COUNT(*) AS c FROM pending_sync WHERE synced_at IS NULL').fetchone()
        return int(row['c'] if row else 0)
    except Exception:
        return 0


def flush_sync_queue() -> int:
    """Mark all pending offline changes as synced. Returns number flushed."""
    try:
        from datetime import datetime
        db = get_db()
        db.execute(
            """CREATE TABLE IF NOT EXISTS pending_sync (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                action TEXT NOT NULL,
                payload TEXT,
                created_at TEXT NOT NULL,
                synced_at TEXT
            )"""
        )
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cur = db.execute(
            'UPDATE pending_sync SET synced_at = ? WHERE synced_at IS NULL',
            (now,),
        )
        db.commit()
        n = cur.rowcount or 0
        if n:
            log_activity('Sync completed', 'system', None, f'Flushed {n} offline change(s) to online mode')
        return n
    except Exception as e:
        try:
            import sys
            print(f'[flush_sync_queue] {e}', file=sys.stderr)
        except Exception:
            pass
        return 0


def log_activity(action, entity_type=None, entity_id=None, details=None):
    """Record an action in activity_log. Uses local wall-clock time so today filters work."""
    try:
        from datetime import datetime
        db = get_db()
        uid = session.get('user_id')
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.execute(
            'INSERT INTO activity_log (user_id, action, entity_type, entity_id, details, created_at) VALUES (?, ?, ?, ?, ?, ?)',
            (uid, action, entity_type, entity_id, details, now)
        )
        db.commit()
        if not is_online_mode() and entity_type and entity_type != 'system':
            queue_sync_event(entity_type, entity_id, action, {'details': details, 'user_id': uid})
    except Exception as e:
        try:
            import sys
            print(f'[log_activity] failed: {e}', file=sys.stderr)
        except Exception:
            pass


def get_redirect_for_role(role):
    if role == 'admin':
        return url_for('admin.admin_dashboard')
    elif role == 'agent':
        return url_for('agent.agent_dashboard')
    else:
        return url_for('client.client_dashboard')


def highlight_match(text, query):
    """Wrap case-insensitive matches of query inside text with a yellow highlight span."""
    if text is None:
        return ''
    text = str(text)
    if not query or not text:
        return text
    import re
    from markupsafe import Markup, escape
    pattern = re.compile(re.escape(query), re.IGNORECASE)

    def repl(m):
        return f'<mark class="search-hl">{escape(m.group(0))}</mark>'

    return Markup(pattern.sub(repl, escape(text)))
