from flask import Flask
import os

from core.db import get_db, close_db, init_db, migrate_db
from routes.auth import auth as auth_bp
from routes.admin import admin as admin_bp
from routes.agent import agent as agent_bp
from routes.client import client as client_bp
from routes.connection import connection_bp


def create_app():
    app = Flask(__name__)
    app.secret_key = 'estacle_secret_key_change_in_production_2026'
    app.config['DATABASE'] = os.path.join(app.instance_path, 'estacle.db')
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads', 'properties')
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(os.path.join(app.root_path, 'static', 'uploads', 'avatars'), exist_ok=True)

    app.teardown_appcontext(close_db)

    from core.helpers import highlight_match
    app.jinja_env.filters['highlight'] = highlight_match

    @app.before_request
    def touch_last_seen():
        from flask import session, request
        uid = session.get('user_id')
        if not uid:
            return
        if request.endpoint and str(request.endpoint).startswith('static'):
            return
        try:
            db = get_db()
            db.execute(
                "UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE id = ?",
                (uid,)
            )
            db.commit()
        except Exception:
            pass

    @app.context_processor
    def inject_connection_mode():
        try:
            from core.helpers import is_online_mode, pending_sync_count, get_setting
            online = is_online_mode()
            pending = pending_sync_count() if not online else 0
            mode = 'online' if online else 'offline'
            return {
                'app_is_online': online,
                'app_connection_mode': mode,
                'app_pending_sync': pending,
                'is_online': online,
                'connection_mode': mode,
                'pending_sync': pending,
            }
        except Exception:
            return {
                'app_is_online': True, 'app_connection_mode': 'online', 'app_pending_sync': 0,
                'is_online': True, 'connection_mode': 'online', 'pending_sync': 0,
            }

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(agent_bp)
    app.register_blueprint(client_bp)
    app.register_blueprint(connection_bp)

    with app.app_context():
        init_db()
        migrate_db()

    @app.get('/healthz')
    def healthz():
        return {'ok': True}, 200

    return app


app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug, host='0.0.0.0', port=port)
