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
from routes.ai_engine import TOOL_IMPL, GEMINI_TOOLS, SYSTEM_PROMPT, run_gemini

ai_bp = Blueprint('ai', __name__)


@ai_bp.route('/admin/ai', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def estacle_ai():
    if request.method == 'POST' and request.form.get('action') == 'save_key':
        key = (request.form.get('gemini_api_key') or '').strip()
        if key:
            set_setting('gemini_api_key', key)
            flash('Gemini API key saved.', 'success')
        else:
            set_setting('gemini_api_key', '')
            flash('API key cleared.', 'success')
        return redirect(url_for('ai.estacle_ai'))

    api_key = get_setting('gemini_api_key', '')
    masked = ''
    if api_key:
        masked = api_key[:6] + '...' + api_key[-4:] if len(api_key) > 12 else '--------'
    return render_template(
        'admin_ai.html',
        has_key=bool(api_key),
        masked_key=masked,
    )


@ai_bp.route('/admin/ai/chat', methods=['POST'])
@login_required
@role_required('admin')
def estacle_ai_chat():
    try:
        data = request.get_json(silent=True) or {}
        message = (data.get('message') or '').strip()
        history = data.get('history') or []
        if not message:
            return jsonify({'error': 'Empty message', 'reply': None}), 400
        api_key = get_setting('gemini_api_key', '')
        if not api_key:
            return jsonify({
                'error': 'No Gemini API key configured. Open ESTACLE AI settings and paste your key from Google AI Studio (aistudio.google.com/apikey).',
                'reply': None,
            }), 400
        result = run_gemini(api_key, message, history)
        if not isinstance(result, dict):
            return jsonify({'error': 'Unexpected AI response', 'reply': None}), 502
        if result.get('error') and not result.get('reply'):
            return jsonify({'error': result.get('error'), 'reply': None, 'tool_results': result.get('tool_results') or []}), 502
        return jsonify({
            'reply': result.get('reply') or '',
            'tool_results': result.get('tool_results') or [],
            'error': result.get('error'),
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'reply': None}), 500
