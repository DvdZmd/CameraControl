import importlib
import logging
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


try:
    from flask import Blueprint, render_template
except ModuleNotFoundError:
    Blueprint = None


def _import_app_factory_without_hardware():
    database = Mock()
    dependency_modules = {
        "database.models": SimpleNamespace(db=database),
        "routes.admin_routes": SimpleNamespace(
            admin_bp=Blueprint("test-admin", __name__)
        ),
        "routes.camera_routes": SimpleNamespace(
            camera_bp=Blueprint("test-camera", __name__),
            initialize_camera=Mock(),
        ),
        "routes.esp32_routes": SimpleNamespace(
            esp32_bp=Blueprint("test-esp32", __name__),
            pan_tilt_bp=Blueprint("test-pan-tilt", __name__),
            lighting_bp=Blueprint("test-lighting", __name__),
        ),
        "routes.tuya_routes": SimpleNamespace(
            tuya_bp=Blueprint("test-tuya", __name__)
        ),
        "routes.sensor_routes": SimpleNamespace(
            sensor_bp=Blueprint("test-sensors", __name__)
        ),
        "routes.timelapse_routes": SimpleNamespace(
            timelapse_bp=Blueprint("test-timelapse", __name__)
        ),
        "esp32.esp32": SimpleNamespace(
            Esp32Controller=lambda: SimpleNamespace(client=None)
        ),
        "tuya.tuya_controller": SimpleNamespace(TuyaController=Mock),
        "logs.sensor_logger": SimpleNamespace(
            start_sensor_logger=Mock(return_value=(None, None))
        ),
        "logs.logging_config": SimpleNamespace(
            configure_logging=Mock(),
            enable_database_logging=Mock(return_value=None),
        ),
        "timelapse.service": SimpleNamespace(
            TimelapseService=Mock(return_value=SimpleNamespace(
                ensure_schema=Mock(),
                ensure_default_config=Mock(),
                resume_if_needed=Mock(return_value=False),
            ))
        ),
        "config": SimpleNamespace(
            AppConfig=lambda: SimpleNamespace(
                instance=SimpleNamespace(
                    name="default",
                    database_path="/tmp/cameracontrol-test.db",
                    ensure_directories=Mock(),
                ),
                tuya=SimpleNamespace(),
                logging=SimpleNamespace(),
                timelapse=SimpleNamespace(),
                sensor_logging=SimpleNamespace(enabled=False, interval_seconds=60),
            )
        ),
    }
    sys.modules.pop("app_factory", None)
    with patch.dict(sys.modules, dependency_modules):
        module = importlib.import_module("app_factory")
    sys.modules["app_factory"] = module
    return module


app_factory = (
    _import_app_factory_without_hardware() if Blueprint is not None else None
)


class DeferredThread:
    def __init__(self, *, target, args, name, daemon):
        self.target = target
        self.args = args
        self.name = name
        self.daemon = daemon
        self.started = False

    def start(self):
        self.started = True


@unittest.skipIf(app_factory is None, "Flask no está instalado")
class TuyaInitializationTests(unittest.TestCase):
    @patch("app_factory.camera_routes.initialize_camera")
    @patch("app_factory.db.create_all")
    def test_profile_without_camera_does_not_initialize_hardware(
        self,
        _create_all,
        initialize_camera,
    ):
        feature_values = {
            "camera": False,
            "timelapse": False,
            "esp32": False,
            "pan_tilt": False,
            "lighting": False,
            "sensors": False,
            "tuya": False,
        }
        profile = SimpleNamespace(
            name="headless-test",
            features=SimpleNamespace(
                **feature_values,
                as_dict=lambda: dict(feature_values),
            ),
        )

        with patch.object(app_factory, "resolve_profile", return_value=profile):
            app = app_factory.create_app()

        initialize_camera.assert_not_called()
        self.assertNotIn("test-camera", app.blueprints)

    @patch("app_factory.camera_routes.initialize_camera")
    @patch("app_factory.db.create_all")
    @patch("app_factory.threading.Thread", side_effect=DeferredThread)
    @patch("app_factory.TuyaController")
    def test_create_app_registers_controller_before_deferred_connection(
        self,
        controller_class,
        thread_class,
        _create_all,
        initialize_camera,
    ):
        controller = controller_class.return_value

        app = app_factory.create_app()

        self.assertEqual(app.config["INSTANCE_NAME"], "default")
        self.assertEqual(
            app.config["SQLALCHEMY_DATABASE_URI"],
            "sqlite:////tmp/cameracontrol-test.db",
        )
        app.config["INSTANCE_CONFIG"].ensure_directories.assert_called_once_with()
        self.assertIs(app.config["TUYA_CONTROLLER"], controller)
        initialization_thread = app.config["TUYA_INITIALIZATION_THREAD"]
        self.assertTrue(initialization_thread.started)
        self.assertTrue(initialization_thread.daemon)
        self.assertEqual(initialization_thread.name, "tuya-initialization")
        controller.connect.assert_not_called()
        initialize_camera.assert_called_once_with()

        initialization_thread.target(*initialization_thread.args)
        controller.connect.assert_called_once_with()

    def test_connection_failure_is_logged_without_raising(self):
        controller = Mock()
        controller.connect.return_value = {"ok": False, "error": "sin red"}
        logger = Mock(spec=logging.Logger)

        app_factory._connect_tuya(controller, logger)

        logger.warning.assert_called_once_with(
            "No se pudo conectar a la API de Tuya al iniciar: %s",
            "sin red",
        )

    @patch("app_factory.camera_routes.initialize_camera")
    @patch("app_factory.db.create_all")
    @patch("app_factory.TuyaController")
    def test_starseek_does_not_initialize_or_register_disabled_modules(
        self,
        controller_class,
        _create_all,
        initialize_camera,
    ):
        app_factory.start_sensor_logger.reset_mock()

        app = app_factory.create_app("starseek")

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertNotIn("/api/tuya/devices", rules)
        self.assertNotIn("/api/sensors/readings", rules)
        self.assertIn("/api/system/capabilities", rules)
        self.assertIsNone(app.config["TUYA_CONTROLLER"])
        self.assertIsNone(app.config["TUYA_INITIALIZATION_THREAD"])
        self.assertNotIn("test-lighting", app.blueprints)
        self.assertIn("test-pan-tilt", app.blueprints)
        controller_class.assert_not_called()
        app_factory.start_sensor_logger.assert_not_called()
        initialize_camera.assert_called_once_with()

        with app.test_request_context():
            tabs = render_template("components/layout/tabs-header.html")
        self.assertNotIn("sensors-tab", tabs)
        self.assertNotIn("devices-tab", tabs)
        self.assertIn("camera-tab", tabs)
        self.assertIn("esp32-tab", tabs)

        with app.test_request_context():
            top_bar = render_template("components/layout/top-bar.html")
            timelapse_settings = render_template(
                "components/timelapse/settings.html"
            )
        self.assertNotIn("light-toggle-btn", top_bar)
        self.assertNotIn("Prender la luz para cada foto", timelapse_settings)
        self.assertNotIn("Guardar sensores y posición", timelapse_settings)

    def test_unexpected_connection_exception_is_logged_without_raising(self):
        controller = Mock()
        controller.connect.side_effect = RuntimeError("fallo inesperado")
        logger = Mock(spec=logging.Logger)

        app_factory._connect_tuya(controller, logger)

        logger.exception.assert_called_once_with(
            "Excepción no controlada al inicializar la conexión con Tuya"
        )

    @patch("app_factory.camera_routes.initialize_camera")
    @patch("app_factory.db.create_all")
    @patch("app_factory.threading.Thread", side_effect=DeferredThread)
    def test_fungiforge_monitor_registers_lighting_without_pan_tilt(
        self,
        _thread_class,
        _create_all,
        initialize_camera,
    ):
        app = app_factory.create_app("fungiforge_monitor")

        self.assertIn("test-lighting", app.blueprints)
        self.assertNotIn("test-pan-tilt", app.blueprints)
        initialize_camera.assert_called_once_with()
        with app.test_request_context():
            esp32_tab = render_template("components/tabs/esp32.html")
        self.assertIn("Estado BLE", esp32_tab)
        self.assertNotIn("Control de movimiento", esp32_tab)

    def test_invalid_connection_response_is_logged_without_raising(self):
        controller = Mock()
        controller.connect.return_value = None
        logger = Mock(spec=logging.Logger)

        app_factory._connect_tuya(controller, logger)

        logger.error.assert_called_once_with(
            "Respuesta inválida al inicializar la conexión con Tuya"
        )


if __name__ == "__main__":
    unittest.main()
