from flask import Flask, session, g
from config import Config
from extensions import db, migrate
from models import User
from routes.main_routes import bp as main_bp
from routes.member_routes import bp as member_bp
from routes.chat_routes import bp as chat_bp
from routes.decision_routes import bp as decision_bp
from routes.history_routes import bp as history_bp
from routes.community_routes import bp as community_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    migrate.init_app(app, db)
    for bp in [main_bp, member_bp, chat_bp, decision_bp, history_bp, community_bp]:
        app.register_blueprint(bp)

    @app.before_request
    def load_user():
        g.user = db.session.get(User, session['user_id']) if 'user_id' in session else None

    @app.context_processor
    def inject_user():
        return {'current_user': g.get('user'), 'csrf_token': lambda: session.setdefault('_csrf_token', __import__('secrets').token_urlsafe(32))}

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
