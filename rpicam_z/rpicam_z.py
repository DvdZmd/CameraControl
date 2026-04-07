import io, time, threading, os
from datetime import datetime
from rpicam_z.camera_utils import CameraPresets, validate_control_value # Import the validator

CAMERA_IMPORT_ERROR = None

try:
    from picamera2 import Picamera2
    from libcamera import Transform
except ModuleNotFoundError as exc:
    Picamera2 = None
    Transform = None
    CAMERA_IMPORT_ERROR = exc

class rpicam_z:
    def __init__(self, width=1640, height=1232, rotation=0, save_path="captures"):
        """
        Initialize the camera controller and start the video pipeline.

        This constructor creates a Picamera2 instance, caches default camera
        settings, probes sensor limits, and starts camera streaming. It touches
        camera hardware during initialization and may block while libcamera
        configures the device.

        Args:
            width: Initial stream width in pixels.
            height: Initial stream height in pixels.
            rotation: Initial clockwise rotation in degrees. Supported values are
                0, 90, 180, and 270.
            save_path: Directory used to persist timelapse JPEG files.

        Returns:
            None

        Raises:
            Exception: Propagates camera initialization errors raised by
                Picamera2 or libcamera.
        """
        if CAMERA_IMPORT_ERROR is not None:
            raise RuntimeError(
                "Camera dependencies are unavailable. Original import error: "
                f"{CAMERA_IMPORT_ERROR}"
            ) from CAMERA_IMPORT_ERROR

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
        """
        Detect the maximum sensor resolution supported by the camera.

        The method queries Picamera2 sensor modes once and caches the highest
        width and height reported by the hardware. Failures are intentionally
        suppressed so camera startup can continue with the configured fallback
        resolution.

        Returns:
            None
        """
        try:
            modes = self.picam2.sensor_modes
            if modes:
                w = max(m['size'][0] for m in modes)
                h = max(m['size'][1] for m in modes)
                self.max_sensor_res = (w, h)
        except:
            pass

    def _initialize_camera(self):
        """
        Configure and start the camera with the current stream settings.

        This method stops any active stream, applies the configured resolution,
        rotation, and controls, checks autofocus support, and restarts the
        Picamera2 pipeline. It performs direct camera hardware access and can
        block while libcamera reconfigures the device.

        Returns:
            None

        Raises:
            Exception: Propagates camera configuration or startup failures raised
                by Picamera2 or libcamera.
        """
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
        """
        Restore factory settings and restart the stream.

        The operation updates in-memory control state and reconfigures the
        camera hardware under a thread lock. Any active stream is restarted as a
        side effect.

        Returns:
            None

        Raises:
            Exception: Propagates camera restart failures raised during
                reinitialization.
        """
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
        """
        Apply a named control preset to the active camera.

        This method updates the in-memory control cache and pushes the resulting
        controls to Picamera2. It performs camera hardware I/O and may fail if
        the camera rejects a control value.

        Args:
            preset_name: Name of a preset defined on ``CameraPresets``.

        Returns:
            True if the preset exists and was applied, otherwise False.
        """
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
        """
        Return cached camera capabilities and current stream state.

        Returns:
            A dictionary containing the maximum sensor resolution in pixels,
            autofocus support, and the current stream width and height.
        """
        # We no longer call self.picam2.sensor_modes here to avoid the error
        return {
            "max_width": self.max_sensor_res[0],
            "max_height": self.max_sensor_res[1],
            "af_supported": self.af_supported,
            "current_width": self.current_width,
            "current_height": self.current_height
        }

    def _get_transform(self, angle):
        """
        Build a libcamera transform for the requested rotation.

        Args:
            angle: Clockwise rotation in degrees.

        Returns:
            A ``Transform`` configured for 0, 90, 180, or 270 degrees. Invalid
            values fall back to the identity transform.
        """
        mapping = {
            0: Transform(), # Identity
            90: Transform(rotation=90),
            180: Transform(rotation=180),
            270: Transform(rotation=270)
        }
        return mapping.get(angle, Transform())

    def set_resolution(self, width, height):
        """
        Update the active stream resolution and restart the camera.

        This method changes the live Picamera2 video configuration. The stream
        is interrupted while the camera hardware is reconfigured.

        Args:
            width: Target stream width in pixels.
            height: Target stream height in pixels.

        Returns:
            None

        Raises:
            Exception: Propagates camera reconfiguration failures.
        """
        with self.lock:
            self.current_width = width
            self.current_height = height
            self._initialize_camera()

    def take_snapshot(self):
        """
        Capture a JPEG frame from the current stream.

        The capture reads directly from the active camera pipeline and returns
        the encoded bytes in memory without writing to disk.

        Returns:
            JPEG image bytes captured from the current stream.

        Raises:
            Exception: Propagates capture errors raised by Picamera2.
        """
        with self.lock:
            # Capture directly from the current stream
            buf = io.BytesIO()
            self.picam2.capture_file(buf, format="jpeg")
            return buf.getvalue()


    def update_control(self, name, value):
        """
        Validate and apply a camera control change.

        The method clamps or normalizes the provided value, updates the cached
        control state, and sends the change to Picamera2. When exposure time or
        analogue gain are changed, automatic exposure is disabled as a side
        effect so manual values take effect.

        Args:
            name: Camera control name, such as ``Brightness`` or
                ``ExposureTime``.
            value: Proposed control value. Exposure time is expressed in
                microseconds when provided.

        Returns:
            None

        Raises:
            Exception: Propagates control application failures raised by
                Picamera2.
        """

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
        """
        Change stream rotation and restart the camera pipeline.

        Args:
            angle: Clockwise rotation in degrees. Supported values are 0, 90,
                180, and 270.

        Returns:
            None

        Raises:
            Exception: Propagates camera restart failures when applying the new
                transform.
        """
        if angle in [0, 90, 180, 270]:
            self.current_rotation = angle
            self.picam2.stop()
            self._initialize_camera() # Apply the new transform

    def take_custom_photo(self, width, height):
        """
        Capture a still JPEG at a requested resolution and restore the stream.

        This method temporarily stops the active video stream, configures a
        still capture pipeline, reads one JPEG frame from the camera, and then
        restores the previous streaming configuration. Requested dimensions are
        clamped to the detected sensor maximum.

        Args:
            width: Requested still image width in pixels.
            height: Requested still image height in pixels.

        Returns:
            JPEG image bytes captured at the requested resolution.

        Raises:
            Exception: Propagates capture or camera reconfiguration failures.
        """
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
        """
        Capture a JPEG frame directly from the ISP output buffer.

        The method accesses the active camera pipeline and returns in-memory
        JPEG bytes suitable for multipart HTTP streaming.

        Returns:
            JPEG image bytes from the current camera frame.

        Raises:
            Exception: Propagates capture errors raised by Picamera2.
        """
        buf = io.BytesIO()
        # The hardware already processed rotation and quality before giving us this buffer
        self.picam2.capture_file(buf, format="jpeg")
        return buf.getvalue()

    # --- Timelapse logic ---
    def start_timelapse(self, interval_seconds, width=None, height=None):
        """
        Start a background timelapse capture thread.

        The worker captures still JPEG frames using the camera hardware and
        writes them to ``save_path``. If width or height are omitted, the
        sensor's maximum cached resolution is used. The thread is daemonized and
        does not block the caller after startup.

        Args:
            interval_seconds: Delay between captures in seconds.
            width: Optional capture width in pixels.
            height: Optional capture height in pixels.

        Returns:
            None
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
        """
        Request termination of the timelapse worker.

        The background thread exits after the current capture cycle completes,
        so shutdown may be delayed by camera latency and file I/O.

        Returns:
            None
        """
        self.timelapse_active = False
        
    def _timelapse_worker(self, interval, width, height):
        """
        Capture timelapse frames and persist them to disk.

        This worker runs in a background thread, repeatedly capturing JPEG
        images from the camera and writing them to the filesystem using
        timestamped filenames. Each iteration can block on camera
        reconfiguration, image capture, and file writes.

        Args:
            interval: Delay between capture cycles in seconds.
            width: Capture width in pixels.
            height: Capture height in pixels.

        Returns:
            None
        """
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

class UnavailableCamera:
    def __init__(self, error):
        self.error = error

    def get_capabilities(self):
        return {
            "available": False,
            "error": str(self.error),
        }

    def __getattr__(self, name):
        raise RuntimeError(
            "Camera is unavailable because its dependencies could not be imported: "
            f"{self.error}"
        ) from self.error


if CAMERA_IMPORT_ERROR is None:
    rpicamz = rpicam_z()
else:
    rpicamz = UnavailableCamera(CAMERA_IMPORT_ERROR)
