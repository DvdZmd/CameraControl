import io
import math

from PIL import Image, ImageDraw, ImageFont


TELEMETRY_KEYS = {
    "temperature_air": "DT",
    "humidity_air": "DH",
    "temperature_crop": "DS",
    "humidity_crop": "SP",
}


def _measurement(state, name, unit):
    raw = state.get(TELEMETRY_KEYS[name]) if isinstance(state, dict) else None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return "--"
    if not math.isfinite(value):
        return "--"
    return f"{value:.1f} {unit}"


def overlay_lines(captured_at, sensor_state):
    return [
        captured_at.strftime("%d/%m/%Y %H:%M:%S"),
        f"Temp Ambiente: {_measurement(sensor_state, 'temperature_air', '°C')}   Humedad Ambiente: {_measurement(sensor_state, 'humidity_air', '%')}",
        f"Temp Cultivo: {_measurement(sensor_state, 'temperature_crop', '°C')}   Humedad Cultivo: {_measurement(sensor_state, 'humidity_crop', '%')}",
    ]


def add_capture_overlay(jpeg_bytes, captured_at, sensor_state):
    """Añade un rótulo discreto sin modificar dimensiones ni el pipeline de cámara."""
    with Image.open(io.BytesIO(jpeg_bytes)) as source:
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image, "RGBA")
    font_size = max(8, min(30, round(image.width * 0.012)))
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()
    lines = overlay_lines(captured_at, sensor_state)
    spacing = max(3, font_size // 4)
    padding = max(8, font_size // 2)
    boxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
    text_width = max(box[2] - box[0] for box in boxes)
    line_height = max(box[3] - box[1] for box in boxes)
    block_height = line_height * len(lines) + spacing * (len(lines) - 1)
    left = padding
    top = image.height - block_height - padding * 2
    draw.rounded_rectangle(
        (left, top, left + text_width + padding * 2, image.height - padding),
        radius=max(4, padding // 2), fill=(0, 0, 0, 125),
    )
    y = top + padding
    for line in lines:
        draw.text((left + padding, y), line, font=font, fill=(255, 255, 255, 220))
        y += line_height + spacing
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=95)
    return output.getvalue()
