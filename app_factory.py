from flask import Flask
from database.models import db
from routes.camera_controller import camera_controller_bp
from routes.esp32_controller import esp32_bp
from camera.ble_camera_controller import Esp32BleCameraController

import os

ble_controller = Esp32BleCameraController()

def create_app():
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
        #TODO: Cargar configuración de timelapse guardada
        #load_timelapse_config()

    return app
