# Pipeline de cámara

## Tecnologías

El stack de cámara puede incluir:

- Raspberry Pi Camera.
- Picamera2.
- libcamera / rpicam.
- `rpicam-z`.
- OpenCV.
- MJPEG multipart.
- Captura JPEG.
- Timelapse.

El código actual determina qué biblioteca posee la instancia real de cámara.

## Cámaras conocidas

- Camera v1.3 — OV5647 — 5 MP.
- Camera v2.1 — IMX219 — 8 MP.
- Camera v3 — IMX708 — 12 MP y autofocus.
- Arducam IMX519 — utilizada en pruebas previas.

Las capacidades cambian por sensor.

No asumir:

- Autofocus universal.
- Misma resolución máxima.
- Mismo campo de visión.
- Mismos modos de sensor.
- Mismos controles.
- Mismo comportamiento al rotar.

## Streaming MJPEG

El stream suele ser una respuesta:

```text
multipart/x-mixed-replace; boundary=frame
```

Cada frame debe incluir:

```text
--frame
Content-Type: image/jpeg

<JPEG bytes>
```

El generador debe:

- Emitir bytes JPEG válidos.
- Incluir pausas razonables.
- Detenerse ante cierre o error.
- Evitar loops que consuman CPU sin límite.
- No acumular frames.
- No mantener referencias innecesarias.
- Manejar cámara no disponible.

## Streaming sincronizado

Puede añadir headers como:

- `X-Frame-Id`
- `X-Timestamp-Wall-Ns`
- `X-Timestamp-Mono-Ns`

Estos valores representan timestamps del software salvo que se confirme que provienen del sensor.

No confundir reloj de pared con reloj monotónico.

## Estabilidad

Una implementación histórica con productor permanente de frames provocó congelamientos.

La obtención bajo demanda fue más estable.

No introducir:

- Producer thread.
- Buffer global.
- Cola sin límite.
- Cache de frames.
- Multiplexor complejo.

salvo que exista un problema medido que lo justifique.

## Encendido del streaming

El servicio Flask debe poder arrancar aunque la cámara no esté conectada. Un
fallo al crear el controlador de cámara debe degradar las rutas de cámara a un
error claro, preferentemente HTTP 503, sin impedir que ESP32, Tuya, base de
datos y frontend sigan disponibles.

El streaming MJPEG se controla explícitamente desde el frontend:

- `POST /api/camera/stream/start`: habilita el streaming y reintenta crear la
  cámara si estaba ausente o cerrada.
- `POST /api/camera/stream/stop`: detiene solamente la entrega de frames MJPEG.
  No llama a `close()`, porque cerrar el controlador también detiene el
  timelapse y libera Picamera2.
- `GET /api/camera/video_feed`: sólo debe abrirse cuando el streaming está
  habilitado; si está apagado responde error controlado.
- `GET /api/camera/camera_status`: expone `available` y `stream_enabled` para
  que el frontend no asuma cámara presente durante el arranque.

Apagar o prender el stream no debe introducir productores permanentes de frames,
colas ni polling de cámara.

El estado `stream_enabled` controla exclusivamente `/video_feed` y
`/video_feed_sync`. La cámara permanece operativa para fotografías y timelapse,
por lo que estos flujos deben funcionar con Live Stream encendido o apagado.

## Concurrencia

Antes de cambiar la cámara, revisar:

- Quién crea la instancia.
- Cuántas rutas la utilizan.
- Si existe lock.
- Si captura y stream comparten configuración.
- Si el timelapse reconfigura el sensor.
- Si hay múltiples clientes.
- Si el objeto Picamera2 es thread-safe.
- Si una excepción deja la cámara detenida.

Cuando una operación reconfigura temporalmente la cámara:

```python
previous_state = capture_current_state()
try:
    stop_stream()
    apply_still_configuration()
    capture()
finally:
    restore(previous_state)
```

El código exacto depende de la biblioteca vigente.

## Resolución

Cambiar resolución puede requerir:

1. Detener cámara.
2. Crear nueva configuración.
3. Configurar.
4. Iniciar.
5. Esperar estabilización.
6. Actualizar estado.

No asumir que una resolución arbitraria es válida.

Validar contra:

- Capacidades del sensor.
- Modos disponibles.
- Límites de memoria.
- Aspect ratio.
- Requisitos de alineación.

## Controles

### Controles del ISP

Ejemplos:

- Brightness.
- Contrast.
- Saturation.
- Sharpness.

Suelen aplicarse dinámicamente.

### Controles del sensor

Ejemplos:

- ExposureTime.
- AnalogueGain.
- AeEnable.
- AfMode.
- LensPosition.

Dependen de la cámara.

Antes de enviar un control:

- Verificar que existe.
- Validar tipo.
- Validar rango.
- Documentar unidad.
- Manejar error de hardware.

## Exposición

`ExposureTime` suele expresarse en microsegundos.

No mezclar:

- segundos,
- milisegundos,
- microsegundos.

Al usar exposición manual, puede ser necesario desactivar AE.

No asumir que todos los controles se aplican inmediatamente.

## Persistencia de configuración

La última configuración aplicada de stream e imagen se persiste en SQLite por
identidad de cámara. La identidad prioriza el modelo reportado por Picamera2 y
usa como respaldo la resolución máxima detectada junto con soporte de autofocus.

Al iniciar Flask se intenta restaurar la configuración persistida para la cámara
actual. Los controles guardados se filtran contra los controles soportados por
la cámara vigente para evitar aplicar opciones de una versión de sensor distinta.

La rotación se guarda como configuración de cámara con tres valores:

- `rotation`: rotación solicitada por el usuario.
- `pipeline_rotation`: rotación aplicada realmente por `rpicam-z`/Picamera2.
- `display_rotation`: compensación visual que debe aplicar el frontend.

El controlador `rpicam-z` trata 0 y 180 como rotaciones de pipeline seguras. Para
90 y 270 conserva la rotación solicitada en la configuración y devuelve la
compensación visual necesaria. El CSS sólo consume `display_rotation`; no decide
por sí mismo cómo rotar.

## Autofocus

Camera v3 puede soportar:

- Enfoque continuo.
- Enfoque automático.
- Enfoque manual.
- Posición de lente.

Las cámaras v1 y v2 normalmente no tienen autofocus.

El frontend debe reaccionar a capacidades detectadas.

## Captura estática

Para capturas personalizadas:

- Validar ancho y alto.
- Evitar reconfiguración concurrente.
- Restaurar stream.
- Usar `try/finally`.
- Devolver JPEG.
- Nombrar archivo claramente.
- No dejar la cámara en estado inconsistente.

## Timelapse

El timelapse debe manejar:

- Estado start/stop.
- Intervalo.
- Resolución.
- Directorio.
- Nombre de archivo.
- Cancelación.
- Excepciones.
- Reinicio de aplicación.

Usar `threading.Event` o mecanismo equivalente para detener de forma limpia.

No iniciar múltiples timelapses simultáneos.

### Implementación vigente

Cuando `rpicam-z` expone callbacks, conserva la propiedad del thread y ofrece
cancelación, estado de runtime y eventos de captura. La versión actualmente
instalada en algunas instalaciones sólo acepta intervalo y resolución. En ese
caso `TimelapseService` selecciona mediante introspección un worker compatible
propio, cancelable con `threading.Event`, que usa `take_custom_photo()` y no
inicia simultáneamente el worker legacy de la dependencia.

Se distinguen dos estados:

- `running`: el thread existe y está activo en este proceso.
- `desired_running`: el usuario dejó el timelapse activado y debe reanudarse si
  la cámara o el proceso vuelven a estar disponibles.

Cada callback de captura actualiza contador, timestamp y ruta. Cuando
`save_sensor_readings` está activo y la telemetría BLE contiene las cuatro
lecturas válidas, también crea un `SensorReading` con los pulsos `P` y `T` y una
FK a `TimelapseFolder`. Este flag es independiente del logger ambiental
periódico. El directorio se organiza como
`<TIMELAPSE_DIR>/YYYY-MM-DD/HH-MM-SS/`.

Los timestamps se persisten en UTC. Los callbacks nativos de `rpicam-z` que
entregan una fecha sin offset se interpretan primero en `APP_TIMEZONE` y luego
se convierten a UTC, evitando que el frontend aplique dos veces el desfase
horario al presentar las lecturas. Los nombres de archivo y directorios se
generan siempre con la hora local de `APP_TIMEZONE`, no con el valor UTC usado
en la base de datos.

La configuración se expone mediante `/api/timelapse`, se migra desde el antiguo
campo `interval_minutes` y utiliza segundos como unidad canónica.

`TIMELAPSE_DIR` define la única raíz autorizada para capturas. Cada timelapse
persiste un `folder_name` directo dentro de esa raíz; nombres absolutos,
traversal (`..`) y separadores de ruta son rechazados. Si no se configura la
variable, la raíz es `<repositorio>/timelapse`, independientemente del working
directory del proceso.

El dashboard consume `/api/timelapse/folders` y
`/api/timelapse/captures?folder=...` para presentar detalles de archivos JPEG o
PNG. Las descargas individuales usan `send_file`; carpetas completas y
selecciones múltiples se comprimen en un ZIP temporal fuera del repositorio y
se eliminan al terminar la respuesta.

Las capturas seleccionadas y los directorios completos pueden eliminarse desde
el dashboard. Todas las rutas se resuelven nuevamente en el backend antes de
borrar y se rechaza cualquier eliminación sobre la carpeta de un timelapse en
ejecución para evitar carreras con el thread de captura.

Las fotografías manuales y las capturas de timelapse usan el formato local
`YYYY_MM_DD_HH-MM-SS.jpg`, compatible con Windows, Linux, ZIP, SMB y sistemas
FAT/exFAT. Si ya existe un archivo del mismo segundo, se agrega
un sufijo incremental (`_2`, `_3`, etc.) para evitar sobrescrituras. En el flujo
nativo, CameraControl normaliza el nombre dentro del callback posterior a la
escritura; el worker compatible genera directamente el mismo formato.

Cada configuración también persiste su propia política de iluminación:
`light_enabled` y `light_intensity` (1..100). El worker de `rpicam-z` llama a
`on_before_capture` inmediatamente antes de tomar cada foto; CameraControl
aplica allí la intensidad configurada. Los callbacks de captura, error y fin
restauran el estado manual persistido, por lo que el timelapse no modifica la
preferencia global. Si están disponibles, se usan los callbacks
`on_before_capture`, `on_capture`, `on_error` y `on_complete`; si no, el worker
compatible invoca el mismo contrato internamente.

Con `light_enabled=true`, `on_before_capture` enciende la luz configurada y
espera `light_warmup_seconds` antes de solicitar la fotografía para permitir
que la exposición automática se estabilice. El valor se persiste por
timelapse, admite entre 0 y 60 segundos y vale 3 por defecto. En el worker
compatible esta espera se interrumpe mediante su `Event` al detener el
timelapse. El intervalo mínimo con luz debe ser igual o mayor que la espera y
se valida tanto en API como en el servicio.

## Errores

La cámara ausente debería generar una respuesta clara, por ejemplo HTTP 503.

No bloquear el arranque completo si la arquitectura soporta una cámara no disponible.

## Pruebas

### Sin hardware

- Validación de resoluciones.
- Validación de controles.
- Respuesta 503.
- Formato multipart.
- Traducción de errores.
- Estado de timelapse.

### Con hardware

- Stream prolongado.
- Dos clientes simultáneos.
- Captura mientras hay stream.
- Cambio de resolución.
- Timelapse.
- Desconexión del navegador.
- Reinicio de cámara.
- Autofocus.
- Baja luz.
- Uso de memoria.
