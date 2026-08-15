import subprocess
import sys
import textwrap
import unittest


class CameraImportLifecycleTests(unittest.TestCase):
    def test_importing_camera_routes_does_not_create_camera_controller(self):
        script = textwrap.dedent(
            """
            import sys
            from types import ModuleType

            class CameraController:
                def __init__(self):
                    raise AssertionError("camera created during route import")

            class UnavailableCamera:
                def __init__(self, error):
                    self.error = error

                def get_capabilities(self):
                    return {"available": False, "error": str(self.error)}

            module = ModuleType("rpicam_z.rpicam_z")
            module.CAMERA_IMPORT_ERROR = None
            module.UnavailableCamera = UnavailableCamera
            module.rpicam_z = CameraController
            package = ModuleType("rpicam_z")
            package.rpicam_z = module
            sys.modules["rpicam_z"] = package
            sys.modules["rpicam_z.rpicam_z"] = module

            from routes import camera_routes

            assert camera_routes.camera_initialized is False
            assert camera_routes.rpicamz.get_capabilities()["available"] is False
            """
        )

        result = subprocess.run(
            [sys.executable, "-c", script],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
