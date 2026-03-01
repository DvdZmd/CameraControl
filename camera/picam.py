import io, time, threading, os
from datetime import datetime
from picamera2 import Picamera2
from config import FRAME_RATE, CAMERA_WIDTH, CAMERA_HEIGHT
from libcamera import Transform
from camera.camera_utils import validate_control_value # Importamos el validador

class CameraController:
    def __init__(self):
        self.picam2 = Picamera2()

        # Guardamos la resolución máxima disponible una sola vez
        self.max_sensor_res = (1640, 1232) # Valor por defecto
        try:
            modes = self.picam2.sensor_modes
            if modes:
                # Buscamos el modo con mayor resolución
                w_max = max(m['size'][0] for m in modes)
                h_max = max(m['size'][1] for m in modes)
                self.max_sensor_res = (w_max, h_max)
        except Exception as e:
            print(f"No se pudieron leer los modos del sensor: {e}")
        # ---------------------------------------------------


        # Valores iniciales (puedes vincularlos a tu config.py)
        self.controls = {
            "Brightness": 0.0,    # -1.0 a 1.0
            "Contrast": 1.0,      # 0.0 a 15.99
            "Saturation": 1.0,    # 0.0 a 32.0
            "Sharpness": 1.0,     # 0.0 a 16.0
            #"LensPosition": 0.0   # Añadimos valor inicial para el foco
        }

        self.is_running = False
        self.current_width = 1640
        self.current_height = 1232
        self.current_rotation = 0
        self.af_supported = False # Bandera de detección

        self.lock = threading.Lock()
        self.current_rotation = 0

        # Atributos para Timelapse
        self.timelapse_thread = None
        self.timelapse_active = False

        self._initialize_camera()

    def _initialize_camera(self):
        """Configura e inicia la cámara con la resolución y rotación actual"""
        # Detener si ya estaba corriendo
        if self.is_running:
            self.picam2.stop()        
            
        # 1. Configuración básica        
        config = self.picam2.create_video_configuration(
            main={"size": (self.current_width, self.current_height), "format": "XRGB8888"},
            transform=self._get_transform(self.current_rotation),
            controls=self.controls
        )
        self.picam2.configure(config)

        # 2. DETECCIÓN DE HARDWARE: Verificamos si AfMode está disponible
        available_controls = self.picam2.camera_controls
        if "AfMode" in available_controls:
            self.af_supported = True
            self.controls["AfMode"] = 2  # Continuous AF por defecto
            print("Cámara con Autofocus detectada.")
        else:
            self.af_supported = False
            print("Cámara de foco fijo detectada (V1/V2/HQ). AF desactivado.")

        # 3. Aplicar controles iniciales y arrancar
        self.picam2.set_controls(self.controls)

        self.picam2.start()
        self.is_running = True

    def get_capabilities(self):
        """Retorna las capacidades usando los datos cacheados"""
        # Ya no llamamos a self.picam2.sensor_modes aquí para evitar el error
        return {
            "max_width": self.max_sensor_res[0],
            "max_height": self.max_sensor_res[1],
            "af_supported": self.af_supported,
            "current_width": self.current_width,
            "current_height": self.current_height
        }

    def _get_transform(self, angle):
        """Retorna el objeto Transform de libcamera adecuado"""
        mapping = {
            0: Transform(), # Identity
            90: Transform(rotation=90),
            180: Transform(rotation=180),
            270: Transform(rotation=270)
        }
        return mapping.get(angle, Transform())

    def set_resolution(self, width, height):
        with self.lock:
            self.current_width = width
            self.current_height = height
            self._initialize_camera()

    def take_snapshot(self):
        """Captura una imagen JPEG de alta calidad"""
        with self.lock:
            # Captura directamente del stream actual
            buf = io.BytesIO()
            self.picam2.capture_file(buf, format="jpeg")
            return buf.getvalue()


    def update_control(self, name, value):
        """Valida y aplica cambios de hardware"""

        # Evitar que el JS intente mover el AF si la cámara no puede
        if name == "AfMode" and not self.af_supported:
            return
        

        is_valid, adjusted_value = validate_control_value(name, value)
        if is_valid:
            with self.lock:
                self.controls[name] = adjusted_value
                self.picam2.set_controls({name: adjusted_value})
                # Si es AfMode manual, podrías querer resetear el LensPosition aquí

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

    # --- Lógica de Timelapse ---
    def start_timelapse(self, interval_seconds):
        if not self.timelapse_active:
            self.timelapse_active = True
            self.timelapse_thread = threading.Thread(
                target=self._timelapse_worker, 
                args=(interval_seconds,),
                daemon=True
            )
            self.timelapse_thread.start()

    def stop_timelapse(self):
        self.timelapse_active = False

    def _timelapse_worker(self, interval):
        """Hilo secundario para no bloquear el servidor Flask"""
        save_path = "captures/timelapse"
        os.makedirs(save_path, exist_ok=True)
        
        while self.timelapse_active:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{save_path}/shot_{timestamp}.jpg"
            
            # Capturamos usando el método existente
            frame = self.get_jpeg_frame()
            with open(filename, "wb") as f:
                f.write(frame)
            
            time.sleep(interval)

camera_controller = CameraController()