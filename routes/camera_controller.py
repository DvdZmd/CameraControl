from flask import Blueprint, Response, request, jsonify, render_template, send_file
from camera.picam import camera_controller
import time
import io
from datetime import datetime


# En tu proyecto complejo (Flask, FastApi, etc.)
#from camera import CameraController
# Instancias una sola vez
#camera = CameraController(default_res=(1280, 720), save_path="/home/pi/my_app/photos")


camera_controller_bp = Blueprint('camera_controller', __name__)

@camera_controller_bp.route('/')
def index():
    """Sirve el archivo index.html"""
    return render_template('index.html')

@camera_controller_bp.route('/reset', methods=['POST'])
def reset_camera():
    camera_controller.reset_to_defaults()
    return jsonify({"status": "success", "message": "Camera reset to defaults"})

@camera_controller_bp.route('/apply_preset', methods=['POST'])
def apply_preset():
    preset_name = request.json.get('preset') # Ej: 'LUNAR_PHOTOGRAPHY'
    if camera_controller.apply_preset(preset_name):
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Preset not found"}), 404

@camera_controller_bp.route('/take_photo_custom')
def take_photo_custom():
    # Recibimos el ancho y alto por parámetros de URL (?w=1920&h=1080)
    w = request.args.get('w', default=1280, type=int)
    h = request.args.get('h', default=720, type=int)
    
    image_binary = camera_controller.take_custom_photo(w, h)
    
    return send_file(
        io.BytesIO(image_binary),
        mimetype='image/jpeg',
        as_attachment=True,
        download_name=f"custom_snap_{w}x{h}.jpg"
    )

def generate_frames():
    while True:
        frame = camera_controller.get_jpeg_frame()
        if frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.03) # 30 FPS aprox

@camera_controller_bp.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@camera_controller_bp.route('/camera_status')
def camera_status():
    return jsonify(camera_controller.get_capabilities())


@camera_controller_bp.route('/update_settings', methods=['POST'])
def update_settings():
    """Endpoint para actualizar calidad y rotación"""
    data = request.json
    
    # Cambio de resolución
    if 'width' in data and 'height' in data:
        camera_controller.set_resolution(int(data['width']), int(data['height']))

    # Manejo de Rotación
    if 'rotation' in data:
        camera_controller.set_rotation(int(data['rotation']))

    #Manejo de Timelapse
    if 'timelapse' in data:
        if data['timelapse'] == 'start':
            interval = int(data.get('interval', 5))
            # Opcional: pasar resolución deseada para el timelapse
            tw = data.get('t_width') 
            th = data.get('t_height')
            camera_controller.start_timelapse(interval, tw, th)
        else:
            camera_controller.stop_timelapse() 
    
    # Actualizar controles (Brightness, Contrast, Saturation, Sharpness, AfMode)
    for param in ['Brightness', 'Contrast', 'Saturation', 'Sharpness', 'AfMode', 'LensPosition', 'ExposureTime', 'AnalogueGain']:
        if param in data:
            camera_controller.update_control(param, data[param])
            
    return jsonify({"status": "success"})