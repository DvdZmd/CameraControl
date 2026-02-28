import io, time, threading
from picamera2 import Picamera2
from config import FRAME_RATE, CAMERA_WIDTH, CAMERA_HEIGHT
from libcamera import Transform

class CameraController:
    def __init__(self):
        self.picam2 = Picamera2()
        # Valores iniciales (puedes vincularlos a tu config.py)
        self.controls = {
            "Brightness": 0.0,    # -1.0 a 1.0
            "Contrast": 1.0,      # 0.0 a 15.99
            "Saturation": 1.0,    # 0.0 a 32.0
            "Sharpness": 1.0      # 0.0 a 16.0
        }

        self.lock = threading.Lock()
        self.last_frame = None

        self.current_rotation = 0
        self._initialize_camera()

    def _initialize_camera(self):
        """Configura la cámara con rotación y controles por hardware"""
        # Evitamos resoluciones 0,0 forzando un estándar si no están definidas
        width = CAMERA_WIDTH if CAMERA_WIDTH > 0 else 1280
        height = CAMERA_HEIGHT if CAMERA_HEIGHT > 0 else 720
        
        config = self.picam2.create_video_configuration(
            main={"size": (width, height), "format": "XRGB8888"},
            transform=self._get_transform(self.current_rotation),
            controls=self.controls
        )
        self.picam2.configure(config)
        self.picam2.start()

    def _get_transform(self, angle):
        """Retorna el objeto Transform de libcamera adecuado"""
        mapping = {
            0: Transform(), # Identity
            90: Transform(rotation=90),
            180: Transform(rotation=180),
            270: Transform(rotation=270)
        }
        return mapping.get(angle, Transform())

    def update_control(self, name, value):
        """Cambia brillo, contraste, etc., en tiempo real sin lag"""
        if name in self.controls:
            self.controls[name] = float(value)
            self.picam2.set_controls({name: self.controls[name]})

    def set_rotation(self, angle):
        """Cambia la rotación reiniciando el stream (requerido por libcamera)"""
        if angle in [0, 90, 180, 270]:
            self.current_rotation = angle
            self.picam2.stop()
            self._initialize_camera() # Aplica el nuevo transform

    def get_jpeg_frame(self):
        """Captura directa del ISP a memoria (máxima calidad)"""
        buf = io.BytesIO()
        # El hardware ya procesó rotación y calidad antes de entregarnos este buffer
        self.picam2.capture_file(buf, format="jpeg")
        return buf.getvalue()

camera_controller = CameraController()


# import io, time, threading
# from picamera2 import Picamera2
# from libcamera import Transform
# from config import FRAME_RATE, CAMERA_WIDTH, CAMERA_HEIGHT

# class CameraController:
#     def __init__(self):
#         self.picam2 = Picamera2()
#         self.controls = {"Brightness": 0.0, "Contrast": 1.0, "Saturation": 1.0, "Sharpness": 1.0}
#         self.current_rotation = 0
        
#         self.lock = threading.Lock()
#         self.last_frame = None
#         self.running = True
        
#         self._initialize_camera()
        
#         # Hilo dedicado a capturar para que Flask no sature la cámara
#         self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
#         self.capture_thread.start()

#     def _initialize_camera(self):
#         width = CAMERA_WIDTH if CAMERA_WIDTH > 0 else 1280
#         height = CAMERA_HEIGHT if CAMERA_HEIGHT > 0 else 720
        
#         # Usamos configuración de Video para máxima fluidez
#         config = self.picam2.create_video_configuration(
#             main={"size": (width, height), "format": "XRGB8888"},
#             transform=self._get_transform(self.current_rotation),
#             controls=self.controls
#         )
#         self.picam2.configure(config)
#         self.picam2.start()

#     def _get_transform(self, angle):
#         mapping = {0: Transform(), 90: Transform(rotation=90), 180: Transform(rotation=180), 270: Transform(rotation=270)}
#         return mapping.get(angle, Transform())

#     def _capture_loop(self):
#         """Este bucle corre a 30fps constantes sin importar Flask"""
#         while self.running:
#             try:
#                 # El método request es mucho más rápido que capture_file
#                 frame = self.picam2.capture_array()
                
#                 # Convertimos a JPEG solo una vez
#                 import cv2
#                 _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                
#                 with self.lock:
#                     self.last_frame = buffer.tobytes()
                
#                 time.sleep(1/FRAME_RATE)
#             except Exception as e:
#                 print(f"Error en captura: {e}")
#                 time.sleep(1)

#     def update_control(self, name, value):
#         """Actualización inmediata sin colisiones"""
#         with self.lock:
#             if name in self.controls:
#                 self.controls[name] = float(value)
#                 self.picam2.set_controls({name: self.controls[name]})

#     def set_rotation(self, angle):
#         """Reinicia la cámara de forma segura"""
#         with self.lock:
#             self.current_rotation = angle
#             self.picam2.stop()
#             self._initialize_camera()

#     def get_latest_frame(self):
#         with self.lock:
#             return self.last_frame

# camera_controller = CameraController()

# --- FUNCIONALIDAD TIMELAPSE ---
"""     def start_timelapse(self, interval_sec, folder="timelapse"):
        if not os.path.exists(folder): os.makedirs(folder)
        self.timelapse_active = True
        self.timelapse_thread = threading.Thread(
            target=self._timelapse_worker, 
            args=(interval_sec, folder)
        )
        self.timelapse_thread.start()

    def stop_timelapse(self):
        self.timelapse_active = False

    def _timelapse_worker(self, interval, folder):
        while self.timelapse_active:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(folder, f"img_{ts}.jpg")
            self.capture_image(path)
            time.sleep(interval) """

