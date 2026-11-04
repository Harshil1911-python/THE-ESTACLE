"""Connection mode (online/offline) toggle."""
from flask import Blueprint, request, redirect, url_for, flash
from core.helpers import (
    login_required, role_required, get_setting, set_setting,
    is_online_mode, pending_sync_count, flush_sync_queue,
)

connection_bp = Blueprint('connection', __name__)


@connection_bp.route('/admin/settings/connection', methods=['POST'])
@login_required
@role_required('admin')
def set_connection_mode():
    mode = (request.form.get('connection_mode') or 'online').strip().lower()
    if mode not in ('online', 'offline'):
        mode = 'online'
    previous = (get_setting('connection_mode', 'online') or 'online').lower()
    set_setting('connection_mode', mode)
    if previous == 'offline' and mode == 'online':
        n = flush_sync_queue()
        flash(
            f'Switched to Online mode. Synced {n} offline change(s).'
            if n else 'Switched to Online mode. Data will sync normally.',
            'success',
        )
    elif previous == 'online' and mode == 'offline':
        flash('Switched to Offline mode. Changes stay local until you go Online again.', 'success')
    else:
        flash('Connection mode updated.', 'success')
    return redirect(url_for('admin.admin_settings'))
