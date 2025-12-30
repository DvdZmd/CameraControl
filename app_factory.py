# app_factory.py
from flask import Flask
from camera.timelapse import load_saved_config
from database.models import db
from routes.camera_routes import camera_bp, register_camera_blueprints
import os

def create_app():
    app = Flask(__name__)

    # Database config
    db_path = os.path.join(os.path.dirname(__file__), 'database', 'app.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    # Register routes
    app.register_blueprint(camera_bp)
    register_camera_blueprints(app)

    # Secret key for session management
    app.secret_key = 'REPLACE_WITH_RANDOM_SECRET_KEY'  # use os.urandom(24) in production

    # Initialize database
    with app.app_context():
        db.create_all()
        load_saved_config()

    return app
