from flask import Blueprint, Response, request, jsonify, render_template
from camera.picam import camera_controller
import time

camera_basic_bp = Blueprint('camera_basic', __name__)

@camera_basic_bp.route('/')
def index():
    """Sirve el archivo index.html"""
    return render_template('index.html')


def generate_frames():
    while True:
        frame = camera_controller.get_jpeg_frame()
        if frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.03) # 30 FPS aprox

@camera_basic_bp.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@camera_basic_bp.route('/camera_status')
def camera_status():
    return jsonify({
        "af_supported": camera_controller.af_supported,
        "current_controls": camera_controller.controls
    })


@camera_basic_bp.route('/update_settings', methods=['POST'])
def update_settings():
    """Endpoint para actualizar calidad y rotación"""
    data = request.json
    
    # Manejo de Rotación
    if 'rotation' in data:
        camera_controller.set_rotation(int(data['rotation']))

    #Manejo de Timelapse
    if 'timelapse' in data:
        if data['timelapse'] == 'start':
            interval = int(data.get('interval', 5))
            camera_controller.start_timelapse(interval)
        else:
            camera_controller.stop_timelapse()  
    
    # Actualizar controles (Brightness, Contrast, Saturation, Sharpness, AfMode)
    for param in ['Brightness', 'Contrast', 'Saturation', 'Sharpness', 'AfMode']:
        if param in data:
            camera_controller.update_control(param, data[param])
            
    return jsonify({"status": "success"})