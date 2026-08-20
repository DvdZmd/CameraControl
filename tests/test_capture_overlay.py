import io
import unittest
from datetime import datetime

from PIL import Image

from camera.capture_overlay import add_capture_overlay, overlay_lines


class CaptureOverlayTests(unittest.TestCase):
    def test_formats_requested_text_and_missing_values(self):
        lines = overlay_lines(datetime(2026, 8, 20, 14, 5, 9), {
            "DT": "24.25", "DH": "70", "DS": "19.8",
        })
        self.assertEqual(lines[0], "20/08/2026 14:05:09")
        self.assertIn("Temp Ambiente: 24.2 °C", lines[1])
        self.assertIn("Humedad Ambiente: 70.0 %", lines[1])
        self.assertIn("Temp Cultivo: 19.8 °C", lines[2])
        self.assertIn("Humedad Cultivo: --", lines[2])

    def test_preserves_dimensions_and_returns_jpeg(self):
        source = io.BytesIO()
        Image.new("RGB", (1280, 720), "green").save(source, "JPEG")
        result = add_capture_overlay(source.getvalue(), datetime.now(), {})
        with Image.open(io.BytesIO(result)) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertEqual(image.size, (1280, 720))


if __name__ == "__main__":
    unittest.main()
