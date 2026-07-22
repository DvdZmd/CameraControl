import importlib
import logging
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


try:
    from flask import Blueprint
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
        "esp32.esp32": SimpleNamespace(
            Esp32Controller=lambda: SimpleNamespace(client=None)
        ),
        "tuya.tuya_controller": SimpleNamespace(TuyaController=Mock),
        "config": SimpleNamespace(
            AppConfig=lambda: SimpleNamespace(tuya=SimpleNamespace())
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
