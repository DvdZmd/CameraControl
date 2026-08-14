from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException
from database.models import db
from routes.admin_routes import admin_bp
from routes import camera_routes
from routes import esp32_routes
from routes import tuya_routes
from routes.camera_routes import camera_bp
from routes.esp32_routes import esp32_bp, lighting_bp, pan_tilt_bp
from routes.tuya_routes import tuya_bp
from routes.sensor_routes import sensor_bp
from routes.timelapse_routes import timelapse_bp
from routes.system_routes import system_bp
from esp32.esp32 import Esp32Controller
from tuya.tuya_controller import TuyaController
from logs.sensor_logger import start_sensor_logger
from logs.logging_config import configure_logging, enable_database_logging
from timelapse.service import TimelapseService
from config import AppConfig
from profiles import resolve_profile
import atexit
import logging
import threading
import uuid

import os

logger = logging.getLogger(__name__)


def _connect_tuya(controller, logger):
    """Conecta Tuya fuera del camino crítico de creación de la aplicación."""
    try:
        connection_result = controller.connect()
    except Exception:
        logger.exception("Excepción no controlada al inicializar la conexión con Tuya")
        return

    if not isinstance(connection_result, dict):
        logger.error("Respuesta inválida al inicializar la conexión con Tuya")
        return

    if connection_result.get("ok"):
        logger.info("Conexión inicial con la API de Tuya establecida")
        return

    logger.warning(
        "No se pudo conectar a la API de Tuya al iniciar: %s",
        connection_result.get("error", "error no especificado"),
    )


def _start_tuya_initialization(controller, logger):
    """Inicia en segundo plano el intento inicial de conexión con Tuya."""
    initialization_thread = threading.Thread(
        target=_connect_tuya,
        args=(controller, logger),
        name="tuya-initialization",
        daemon=True,
    )
    initialization_thread.start()
    return initialization_thread

def create_app(profile_name: str | None = None):
    """
    Create and configure the Flask application.

    The factory resolves the product profile, initializes database bindings,
    registers enabled API blueprints, and creates enabled shared controllers.
    It also creates database tables inside an application context as a side effect.

    Returns:
        A configured Flask application instance.
    """
    app = Flask(__name__)

    # Cargar configuración desde el objeto AppConfig
    # (En un futuro, esto podría venir de un archivo YAML o similar)
    app_config = AppConfig()
    instance_config = app_config.instance
    instance_config.ensure_directories()
    project_profile = resolve_profile(profile_name)
    features = project_profile.features
    app.config["PROJECT_PROFILE"] = project_profile
    app.config["INSTANCE_CONFIG"] = instance_config
    app.config["INSTANCE_NAME"] = instance_config.name
    app.config["FEATURES"] = features.as_dict()
    app.config["APP_TIMEZONE"] = getattr(
        app_config, "timezone_name", "America/Argentina/Buenos_Aires"
    )
    configure_logging(app, app_config.logging)

    # Database config
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        f"sqlite:///{instance_config.database_path}"
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    @app.before_request
    def assign_request_id():
        incoming_id = request.headers.get("X-Request-ID", "").strip()
        g.request_id = incoming_id[:64] if incoming_id else uuid.uuid4().hex

    @app.after_request
    def expose_request_id(response):
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")
        return response

    @app.errorhandler(Exception)
    def handle_unexpected_exception(error):
        if isinstance(error, HTTPException):
            return error
        logger.exception("Excepción HTTP no controlada")
        return jsonify({"error": "Internal server error"}), 500

    # Los recursos físicos se crean únicamente cuando el perfil los habilita.
    ble_controller = Esp32Controller() if features.esp32 else None
    app.config["BLE_CAMERA_CONTROLLER"] = ble_controller

    # Registrar primero el controlador compartido para que las rutas puedan
    # degradar de forma controlada mientras finaliza el intento de conexión.
    tuya_controller = None
    app.config["TUYA_CONTROLLER"] = None
    app.config["TUYA_INITIALIZATION_THREAD"] = None
    if features.tuya:
        tuya_controller = TuyaController(config=app_config.tuya)
        app.config["TUYA_CONTROLLER"] = tuya_controller
        app.config["TUYA_INITIALIZATION_THREAD"] = _start_tuya_initialization(
            tuya_controller,
            logger,
        )

    # Register routes
    app.register_blueprint(admin_bp)
    app.register_blueprint(system_bp)
    if features.camera:
        app.register_blueprint(camera_bp)
    if features.esp32:
        app.register_blueprint(esp32_bp)
    if features.pan_tilt:
        app.register_blueprint(pan_tilt_bp)
    if features.lighting:
        app.register_blueprint(lighting_bp)
    if features.tuya:
        app.register_blueprint(tuya_bp)
    if features.sensors:
        app.register_blueprint(sensor_bp)
    if features.timelapse:
        app.register_blueprint(timelapse_bp)

    @app.context_processor
    def expose_project_profile():
        camera_control = project_profile.as_dict()
        camera_control["instance"] = instance_config.name
        return {"camera_control": camera_control}

    # Secret key for session management. An ephemeral fallback keeps local
    # development usable without embedding a shared secret in source control.
    app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.urandom(24)
    if not os.environ.get("FLASK_SECRET_KEY"):
        logger.warning(
            "FLASK_SECRET_KEY no configurada; se usará una clave efímera hasta reiniciar"
        )

    # Initialize database
    with app.app_context():
        db.create_all()
        ensure_camera_schema = getattr(camera_routes, "ensure_camera_settings_schema", None)
        if features.camera and callable(ensure_camera_schema):
            ensure_camera_schema(logger)
        ensure_esp32_schema = getattr(esp32_routes, "ensure_esp32_settings_schema", None)
        if features.esp32 and callable(ensure_esp32_schema):
            ensure_esp32_schema(logger)
        ensure_tuya_schema = getattr(tuya_routes, "ensure_tuya_devices_schema", None)
        if features.tuya and callable(ensure_tuya_schema):
            ensure_tuya_schema(logger)
        ensure_tuya_device = getattr(tuya_routes, "ensure_tuya_legacy_device", None)
        if features.tuya and callable(ensure_tuya_device):
            ensure_tuya_device(app_config.tuya, logger)
        apply_saved_settings = getattr(camera_routes, "apply_saved_camera_settings", None)
        if features.camera and callable(apply_saved_settings):
            apply_saved_settings(logger)
        app.config["TIMELAPSE_SERVICE"] = None
        if features.timelapse:
            timelapse_service = TimelapseService(
                app,
                lambda: camera_routes.rpicamz,
                ble_controller,
                app_config.timelapse,
            )
            timelapse_service.ensure_schema()
            timelapse_service.ensure_default_config()
            app.config["TIMELAPSE_SERVICE"] = timelapse_service
            timelapse_service.resume_if_needed()

    database_log_handler = enable_database_logging(app, app_config.logging)
    app.config["DATABASE_LOG_HANDLER"] = database_log_handler

    sensor_thread = None
    sensor_stop_event = None
    sensor_logging_runtime = None
    if features.sensors:
        sensor_logger_result = start_sensor_logger(
            app,
            ble_controller,
            app_config.sensor_logging,
        )
        if len(sensor_logger_result) == 3:
            sensor_thread, sensor_stop_event, sensor_logging_runtime = sensor_logger_result
        else:
            # Compatibilidad con dobles de prueba y extensiones antiguas.
            sensor_thread, sensor_stop_event = sensor_logger_result
    app.config["SENSOR_LOGGER_THREAD"] = sensor_thread
    app.config["SENSOR_LOGGER_STOP_EVENT"] = sensor_stop_event
    app.config["SENSOR_LOGGING_RUNTIME"] = sensor_logging_runtime

    # --- INICIO: Solución al problema de reconexión ---
    # Registramos una función para que se ejecute al salir de la aplicación.
    # Esto asegura que la conexión BLE se cierre de forma limpia.
    def on_exit():
        """Función de limpieza para desconectar el ESP32 al cerrar la app."""
        if sensor_stop_event is not None:
            sensor_stop_event.set()
        if sensor_logging_runtime is not None:
            sensor_logging_runtime.wake_event.set()
        logger.info("Cerrando la aplicación; se desconectará el ESP32")
        if (
            ble_controller
            and ble_controller.client
            and ble_controller.client.is_connected
        ):
            try:
                ble_controller.disconnect_sync()
                logger.info("Conexión BLE con ESP32 cerrada correctamente")
            except Exception:
                logger.exception("Error durante la desconexión automática del ESP32")
        if database_log_handler is not None:
            database_log_handler.close()

    atexit.register(on_exit)
    # --- FIN: Solución al problema de reconexión ---

    return app
