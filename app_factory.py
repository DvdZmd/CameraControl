from flask import Flask
from database.models import db
from routes.admin_routes import admin_bp
from routes.camera_routes import camera_bp
from routes.esp32_routes import esp32_bp
from routes.tuya_routes import tuya_bp
from esp32.esp32 import Esp32Controller
from tuya.tuya_controller import TuyaController
from config import AppConfig
import atexit

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

    # Cargar configuración desde el objeto AppConfig
    # (En un futuro, esto podría venir de un archivo YAML o similar)
    app_config = AppConfig()

    # Database config
    db_path = os.path.join(os.path.dirname(__file__), 'database', 'app.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    # Inicializar y registrar controlador del ESP32
    app.config["BLE_CAMERA_CONTROLLER"] = ble_controller

    # Inicializar y registrar controlador de Tuya
    tuya_controller = TuyaController(config=app_config.tuya)
    # Conectamos al iniciar la app, pero manejamos el fallo para no bloquear el inicio
    connection_result = tuya_controller.connect()
    if not connection_result["ok"]:
        # Usamos app.logger que estará disponible una vez que la app esté configurada
        app.logger.warning(f"No se pudo conectar a la API de Tuya al iniciar: {connection_result.get('error')}")
    app.config["TUYA_CONTROLLER"] = tuya_controller

    # Register routes
    app.register_blueprint(admin_bp)
    app.register_blueprint(camera_bp)
    app.register_blueprint(esp32_bp)
    app.register_blueprint(tuya_bp)

    # Secret key for session management
    app.secret_key = 'REPLACE_WITH_RANDOM_SECRET_KEY'  # use os.urandom(24) in production

    # Initialize database
    with app.app_context():
        db.create_all()
        #TODO: Load saved timelapse configuration
        #load_timelapse_config()

    # --- INICIO: Solución al problema de reconexión ---
    # Registramos una función para que se ejecute al salir de la aplicación.
    # Esto asegura que la conexión BLE se cierre de forma limpia.
    def on_exit():
        """Función de limpieza para desconectar el ESP32 al cerrar la app."""
        print("Cerrando la aplicación. Intentando desconectar el ESP32...")
        if ble_controller and ble_controller.client and ble_controller.client.is_connected:
            try:
                ble_controller.disconnect_sync()
                print("Conexión BLE con ESP32 cerrada correctamente.")
            except Exception as e:
                print(f"Error durante la desconexión automática del ESP32: {e}")

    atexit.register(on_exit)
    # --- FIN: Solución al problema de reconexión ---

    return app
