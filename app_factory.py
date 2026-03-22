from flask import Flask
from database.models import db
from routes.camera_controller import camera_controller_bp
from routes.esp32_controller import esp32_bp
from esp32.esp32 import Esp32Controller

import os

ble_controller = Esp32Controller()

def create_app():
    """
    Create and configure the Flask application.

    The factory initializes database bindings, registers API blueprints, and
    attaches the shared BLE controller used to communicate with the ESP32. It
    also creates database tables inside an application context as a side effect.

    Returns:
        A configured Flask application instance.
    """
    app = Flask(__name__)

    # Database config
    db_path = os.path.join(os.path.dirname(__file__), 'database', 'app.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    app.config["BLE_CAMERA_CONTROLLER"] = ble_controller

    # Register routes
    app.register_blueprint(camera_controller_bp)
    app.register_blueprint(esp32_bp)

    # Secret key for session management
    app.secret_key = 'REPLACE_WITH_RANDOM_SECRET_KEY'  # use os.urandom(24) in production

    # Initialize database
    with app.app_context():
        db.create_all()
        #TODO: Load saved timelapse configuration
        #load_timelapse_config()

    return app
