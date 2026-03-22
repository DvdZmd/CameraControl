from flask import Blueprint, Response, request, jsonify, render_template, send_file
from camera.rpicam_z import rpicamz
import time
import io

camera_controller_bp = Blueprint(
    'camera_controller', 
    __name__, 
    url_prefix="/api/camera")

@camera_controller_bp.route('/')
def index():
    """Serve the index.html file."""
    return render_template('index.html')

@camera_controller_bp.route('/reset', methods=['POST'])
def reset_camera():
    rpicamz.reset_to_defaults()
    return jsonify({"status": "success", "message": "Camera reset to defaults"})

@camera_controller_bp.route('/apply_preset', methods=['POST'])
def apply_preset():
    preset_name = request.json.get('preset') # Example: 'LUNAR_PHOTOGRAPHY'
    if rpicamz.apply_preset(preset_name):
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Preset not found"}), 404

@camera_controller_bp.route('/take_photo_custom')
def take_photo_custom():
    # Receive width and height through URL parameters (?w=1920&h=1080)
    w = request.args.get('w', default=1280, type=int)
    h = request.args.get('h', default=720, type=int)
    
    image_binary = rpicamz.take_custom_photo(w, h)
    
    return send_file(
        io.BytesIO(image_binary),
        mimetype='image/jpeg',
        as_attachment=True,
        download_name=f"custom_snap_{w}x{h}.jpg"
    )

def generate_frames():
    while True:
        frame = rpicamz.get_jpeg_frame()
        if frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.03) # ~30 FPS

@camera_controller_bp.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@camera_controller_bp.route('/camera_status')
def camera_status():
    return jsonify(rpicamz.get_capabilities())


@camera_controller_bp.route('/update_settings', methods=['POST'])
def update_settings():
    """Endpoint to update quality and rotation."""
    data = request.json
    
    # Resolution change
    if 'width' in data and 'height' in data:
        rpicamz.set_resolution(int(data['width']), int(data['height']))

    # Rotation handling
    if 'rotation' in data:
        rpicamz.set_rotation(int(data['rotation']))

    # Timelapse handling
    if 'timelapse' in data:
        if data['timelapse'] == 'start':
            interval = int(data.get('interval', 5))
            # Optional: pass the desired resolution for timelapse
            tw = data.get('t_width') 
            th = data.get('t_height')
            rpicamz.start_timelapse(interval, tw, th)
        else:
            rpicamz.stop_timelapse() 
    
    # Update controls (Brightness, Contrast, Saturation, Sharpness, AfMode)
    for param in ['Brightness', 'Contrast', 'Saturation', 'Sharpness', 'AfMode', 'LensPosition', 'ExposureTime', 'AnalogueGain']:
        if param in data:
            rpicamz.update_control(param, data[param])
            
    return jsonify({"status": "success"})
