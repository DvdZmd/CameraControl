import io, time, threading, os
from datetime import datetime
from picamera2 import Picamera2
from libcamera import Transform
from camera.camera_utils import CameraPresets, validate_control_value # Import the validator

class rpicam_z:
    def __init__(self, width=1640, height=1232, rotation=0, save_path="captures"):
        self.picam2 = Picamera2()
        # Store initial factory values for Reset
        self.default_config = {
            "width": width,
            "height": height,
            "rotation": rotation,
            "controls": {
                "Brightness": 0.0,
                "Contrast": 1.0,
                "Saturation": 1.0,
                "Sharpness": 1.0,
                "AeEnable": True
            }
        }

        # Store the maximum available resolution only once
        self.max_sensor_res = (width, height) # Default value
        self._detect_sensor_limits()

        # Initial values (these can be tied to config.py)
        self.controls = dict(self.default_config["controls"])
        self.current_width = width
        self.current_height = height
        self.current_rotation = rotation
        self.save_path = save_path

        self.is_running = False
        self.af_supported = False
        self.lock = threading.Lock()
        self.timelapse_thread = None
        self.timelapse_active = False

        self._initialize_camera()

    def _detect_sensor_limits(self):
        try:
            modes = self.picam2.sensor_modes
            if modes:
                w = max(m['size'][0] for m in modes)
                h = max(m['size'][1] for m in modes)
                self.max_sensor_res = (w, h)
        except:
            pass

    def _initialize_camera(self):
        """Configure and start the camera with the current resolution and rotation."""
        # Stop it if it was already running
        if self.is_running:
            self.picam2.stop()        
            
        # 1. Basic configuration
        config = self.picam2.create_video_configuration(
            main={"size": (self.current_width, self.current_height), "format": "XRGB8888"},
            transform=self._get_transform(self.current_rotation),
            controls=self.controls
        )
        self.picam2.configure(config)

        # 2. HARDWARE DETECTION: Check whether AfMode is available
        available_controls = self.picam2.camera_controls
        if "AfMode" in available_controls:
            self.af_supported = True
            self.controls["AfMode"] = 2  # Continuous AF by default
            print("Cámara con Autofocus detectada.")
        else:
            self.af_supported = False
            print("Cámara de foco fijo detectada (V1/V2/HQ). AF desactivado.")

        # 3. Apply initial controls and start
        self.picam2.set_controls(self.controls)

        self.picam2.start()
        self.is_running = True

    def reset_to_defaults(self):
        """Restore factory settings and restart the stream."""
        with self.lock:
            print("Restaurando configuración por defecto...")
            self.current_width = self.default_config["width"]
            self.current_height = self.default_config["height"]
            self.current_rotation = self.default_config["rotation"]
            self.controls = dict(self.default_config["controls"])
            
            # If AF is available, return it to Continuous
            if self.af_supported:
                self.controls["AfMode"] = 2
                
            self._initialize_camera()

    def apply_preset(self, preset_name):
        """Apply a group of values from CameraPresets."""
        preset = getattr(CameraPresets, preset_name, None)
        if not preset:
            print(f"Error: Preset {preset_name} no encontrado.")
            return False
        
        print(f"Aplicando preset: {preset_name}")
        with self.lock:
            self.controls.update(preset)
            self.picam2.set_controls(self.controls)
        return True

    def get_capabilities(self):
        """Return capabilities using cached data."""
        # We no longer call self.picam2.sensor_modes here to avoid the error
        return {
            "max_width": self.max_sensor_res[0],
            "max_height": self.max_sensor_res[1],
            "af_supported": self.af_supported,
            "current_width": self.current_width,
            "current_height": self.current_height
        }

    def _get_transform(self, angle):
        """Return the appropriate libcamera Transform object."""
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
        """Capture a high-quality JPEG image."""
        with self.lock:
            # Capture directly from the current stream
            buf = io.BytesIO()
            self.picam2.capture_file(buf, format="jpeg")
            return buf.getvalue()


    def update_control(self, name, value):
        """Validate and apply hardware changes."""

        # Prevent JS from trying to move AF if the camera cannot do it
        if name == "AfMode" and not self.af_supported:
            return
        
        is_valid, adjusted_value = validate_control_value(name, value)

        if is_valid:
            with self.lock:
                self.controls[name] = adjusted_value
                
                # If AfMode is manual, you may want to reset LensPosition here
                # Special logic for V3 and astronomy:
                # If the user changes ExposureTime or AnalogueGain,
                # we automatically disable AE so the value is actually applied.
                # TODO update frontend
                if name in ["ExposureTime", "AnalogueGain"]:
                    self.controls["AeEnable"] = False
                    self.picam2.set_controls({
                        "AeEnable": False,
                        name: adjusted_value
                    })
                else:
                    self.picam2.set_controls({name: adjusted_value})

    def set_rotation(self, angle):
        """Change rotation by restarting the stream (required by libcamera)."""
        if angle in [0, 90, 180, 270]:
            self.current_rotation = angle
            self.picam2.stop()
            self._initialize_camera() # Apply the new transform

    def take_custom_photo(self, width, height):
        """Capture a photo at a specific resolution and restore the original stream."""
        with self.lock:
            # 1. Save the current stream configuration
            old_w, old_h = self.current_width, self.current_height
            
            try:
                # 2. Stop the stream and configure PHOTO resolution
                self.picam2.stop()
                
                # Validate that it does not exceed the sensor maximum
                max_w, max_h = self.max_sensor_res
                target_w = min(int(width), max_w)
                target_h = min(int(height), max_h)

                still_config = self.picam2.create_still_configuration(
                    main={"size": (target_w, target_h), "format": "XRGB8888"},
                    transform=self._get_transform(self.current_rotation),
                    controls=self.controls
                )
                self.picam2.configure(still_config)
                self.picam2.start()
                
                # 3. Capture frame
                buf = io.BytesIO()
                self.picam2.capture_file(buf, format="jpeg")
                data = buf.getvalue()
                return data
                
            finally:
                # 4. ALWAYS restore the original stream
                self.picam2.stop()
                self.current_width, self.current_height = old_w, old_h
                self._initialize_camera()

    def get_jpeg_frame(self):
        """Direct capture from the ISP to memory (maximum quality)."""
        buf = io.BytesIO()
        # The hardware already processed rotation and quality before giving us this buffer
        self.picam2.capture_file(buf, format="jpeg")
        return buf.getvalue()

    # --- Timelapse logic ---
    def start_timelapse(self, interval_seconds, width=None, height=None):
        """
        Start the timelapse.
        If width/height are not provided, it will use the sensor's maximum resolution.
        """
        if not self.timelapse_active:
            # If no resolution is defined, use the detected maximum
            t_width = width or self.max_sensor_res[0]
            t_height = height or self.max_sensor_res[1]
            
            self.timelapse_active = True
            self.timelapse_thread = threading.Thread(
                target=self._timelapse_worker, 
                args=(interval_seconds, t_width, t_height),
                daemon=True
            )
            self.timelapse_thread.start()

    def stop_timelapse(self):
        self.timelapse_active = False
        
    def _timelapse_worker(self, interval, width, height):
        save_path = self.save_path
        os.makedirs(save_path, exist_ok=True)
        
        while self.timelapse_active:
            # Use take_custom_photo so it changes resolution,
            # captures at high quality, and restores the stream automatically.
            frame = self.take_custom_photo(width, height)
            
            if frame:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{save_path}/shot_{timestamp}.jpg"
                with open(filename, "wb") as f:
                    f.write(frame)
            
            # The wait time must consider that take_custom_photo
            # takes ~1-2 seconds to reset the camera
            time.sleep(max(1, interval))

rpicamz = rpicam_z()
