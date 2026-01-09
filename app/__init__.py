from flask import Flask
from app.config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    from app.routes.main_routes import main_bp
    from app.routes.ai_routes import ai_bp
    from app.routes.screen_routes import screen_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(ai_bp, url_prefix='/ai')
    app.register_blueprint(screen_bp)

    return app
