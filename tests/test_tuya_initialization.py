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
            camera_bp=Blueprint("test-camera", __name__)
        ),
        "routes.esp32_routes": SimpleNamespace(
            esp32_bp=Blueprint("test-esp32", __name__)
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
    @patch("app_factory.db.create_all")
    @patch("app_factory.threading.Thread", side_effect=DeferredThread)
    @patch("app_factory.TuyaController")
    def test_create_app_registers_controller_before_deferred_connection(
        self,
        controller_class,
        thread_class,
        _create_all,
    ):
        controller = controller_class.return_value

        app = app_factory.create_app()

        self.assertIs(app.config["TUYA_CONTROLLER"], controller)
        initialization_thread = app.config["TUYA_INITIALIZATION_THREAD"]
        self.assertTrue(initialization_thread.started)
        self.assertTrue(initialization_thread.daemon)
        self.assertEqual(initialization_thread.name, "tuya-initialization")
        controller.connect.assert_not_called()

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

    @patch("app_factory.db.create_all")
    @patch("app_factory.TuyaController")
    def test_starseek_does_not_initialize_or_register_disabled_modules(
        self,
        controller_class,
        _create_all,
    ):
        app_factory.start_sensor_logger.reset_mock()

        app = app_factory.create_app("starseek")

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertNotIn("/api/tuya/devices", rules)
        self.assertNotIn("/api/sensors/readings", rules)
        self.assertIn("/api/system/capabilities", rules)
        self.assertIsNone(app.config["TUYA_CONTROLLER"])
        self.assertIsNone(app.config["TUYA_INITIALIZATION_THREAD"])
        controller_class.assert_not_called()
        app_factory.start_sensor_logger.assert_not_called()

        with app.test_request_context():
            tabs = render_template("components/layout/tabs-header.html")
        self.assertNotIn("sensors-tab", tabs)
        self.assertNotIn("devices-tab", tabs)
        self.assertIn("camera-tab", tabs)
        self.assertIn("esp32-tab", tabs)

    def test_unexpected_connection_exception_is_logged_without_raising(self):
        controller = Mock()
        controller.connect.side_effect = RuntimeError("fallo inesperado")
        logger = Mock(spec=logging.Logger)

        app_factory._connect_tuya(controller, logger)

        logger.exception.assert_called_once_with(
            "Excepción no controlada al inicializar la conexión con Tuya"
        )

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
