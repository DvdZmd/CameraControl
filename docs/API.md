# Contrato HTTP actual

Este documento inventaría la superficie HTTP existente de CameraControl para
estabilizar el backend antes de crear frontends satélite. Describe el código
vigente; no propone una API nueva.

La representación para tooling está en `docs/openapi.json` (OpenAPI 3.1). Se
genera desde `api_contract.py`, que no importa Flask ni inicializa hardware:

```bash
python api_contract.py > docs/openapi.json
```

La política para cambios compatibles e incompatibles está en
`docs/API_COMPATIBILITY.md`.

La instantánea ejecutable se encuentra en `tests/test_api_contracts.py`. Todo
cambio de URL, método, nombre interno de endpoint o envelope protegido debe
tratarse como un cambio deliberado de contrato y revisarse junto con el
dashboard y los demás consumidores.

## Convenciones globales

- La API no tiene actualmente un prefijo de versión en la URL.
- `GET /api/system/capabilities` devuelve `api_version: "1"` y es el punto de
  descubrimiento para un frontend.
- Cada respuesta generada por la aplicación completa incluye `X-Request-ID`.
  Se conserva el valor recibido, truncado a 64 caracteres, o se genera uno.
- JSON es el formato normal, excepto HTML, JPEG, MJPEG y ZIP indicados abajo.
- No existe todavía un envelope JSON único. Los formatos históricos se
  documentan y se congelan temporalmente; no deben normalizarse sin una fase
  de migración explícita.
- Los endpoints sólo existen si el blueprint de su feature fue registrado. Una
  feature deshabilitada produce `404`, no una respuesta simulada.
- No se ha definido autenticación HTTP. La API está concebida para una red
  local confiable; exponerla fuera de ella requiere una capa de seguridad.

## Descubrimiento y disponibilidad

`GET /api/system/capabilities` siempre está disponible y responde:

```json
{
  "api_version": "1",
  "profile": "starseek",
  "instance": "observatorio",
  "features": {
    "camera": true,
    "timelapse": true,
    "esp32": true,
    "pan_tilt": true,
    "lighting": false,
    "sensors": false,
    "tuya": false
  }
}
```

`profile` selecciona la composición funcional. `instance` identifica la
instalación y sus paths persistentes. `features` indica módulos configurados,
no disponibilidad física instantánea.

## Inventario completo

### Infraestructura común

| Método | Ruta | Resultado principal | Efecto o dependencia |
|---|---|---|---|
| `GET` | `/api/system/capabilities` | JSON de versión, perfil, instancia y features | Sin acceso a hardware |
| `GET` | `/api/admin/system-status` | JSON de CPU, temperatura, alimentación y disco | Lee información local del sistema |
| `POST` | `/api/admin/bluetooth/enable` | JSON `status`/`message`; exige `{"confirm": true}` | Desbloquea, habilita y enciende Bluetooth local |
| `POST` | `/api/admin/update` | JSON `status`/`message` | Inicia `update.sh` en segundo plano |
| `POST` | `/api/admin/reboot` | JSON `status`/`message`; exige `{"confirm": true}` | Ordena reinicio del sistema |

Administración y sistema se registran en todos los perfiles. `bluetooth/enable`,
`update` y `reboot` tienen efectos operativos y no son consultas idempotentes.

### Cámara — feature `camera`

| Método | Ruta | Resultado principal | Entrada o efecto |
|---|---|---|---|
| `GET` | `/api/camera/` | HTML del dashboard | Render Jinja |
| `GET` | `/api/camera/camera_status` | JSON de estado, controles y capacidades | Consulta cámara runtime |
| `GET` | `/api/camera/video_feed` | `multipart/x-mixed-replace` MJPEG | Requiere streaming habilitado |
| `GET` | `/api/camera/video_feed_sync` | `multipart/x-mixed-replace` MJPEG sincronizado | Requiere streaming habilitado |
| `POST` | `/api/camera/stream/start` | JSON con `stream_enabled` | Habilita entrega de stream |
| `POST` | `/api/camera/stream/stop` | JSON con `stream_enabled` | Detiene entrega sin cerrar la cámara |
| `GET` | `/api/camera/take_photo_custom?w=…&h=…&overlay=true\|false` | JPEG adjunto | Captura en resolución solicitada; el rótulo es opcional |
| `POST` | `/api/camera/update_settings` | JSON `status`/`message` | Objeto con controles soportados |
| `POST` | `/api/camera/apply_preset` | JSON `status`/`message` | Aplica preset persistido |
| `POST` | `/api/camera/reset` | JSON `status`/`message` | Restablece el recurso de cámara |

La estabilidad del multipart y los bytes JPEG forman parte del contrato. Las
capacidades y rangos reales deben obtenerse del estado de cámara; el frontend
no debe asumir autofocus u otros controles.

### Transporte ESP32 — feature `esp32`

| Método | Ruta | Resultado principal | Entrada o efecto |
|---|---|---|---|
| `GET` | `/api/esp32/status` | JSON de conexión y última telemetría | Consulta el controlador BLE compartido |
| `POST` | `/api/esp32/connect` | JSON `ok` o `error` | Escaneo/conexión BLE |
| `POST` | `/api/esp32/disconnect` | JSON `ok` o `error` | Desconexión BLE |
| `POST` | `/api/esp32/target` | JSON `ok` o `error` | Persiste `{"device_name": "ESP32-FungiESP"}` como destino BLE |
| `POST` | `/api/esp32/command` | JSON `ok` o `error` | `{"command": "…"}` validado y filtrado por feature |

### Pan/tilt — features `esp32` y `pan_tilt`

| Método | Ruta | Resultado principal | Entrada o efecto |
|---|---|---|---|
| `POST` | `/api/esp32/center` | JSON `ok` o `error` | Centra ambos ejes |
| `POST` | `/api/esp32/move` | JSON `ok` o `error` | Movimiento discreto validado |
| `POST` | `/api/esp32/speed` | JSON `ok` o `error` | Configura velocidad por pasos |
| `POST` | `/api/esp32/position/current` | JSON `ok` o `error` | Guarda la posición reportada |
| `POST` | `/api/esp32/position/return` | JSON `ok` o `error` | Regresa a la posición guardada |

### Iluminación — features `esp32` y `lighting`

| Método | Ruta | Resultado principal | Entrada o efecto |
|---|---|---|---|
| `POST` | `/api/esp32/light` | JSON `ok` o `error` | Ajusta intensidad PWM validada |

### Sensores — features `esp32` y `sensors`

| Método | Ruta | Resultado principal | Entrada o efecto |
|---|---|---|---|
| `GET` | `/api/sensors/logging-config` | JSON de activación e intervalo | Consulta configuración runtime |
| `PUT` | `/api/sensors/logging-config` | JSON actualizado o `error` | `enabled` e `interval_seconds` |
| `GET` | `/api/sensors/readings` | JSON paginado con `readings` | Filtros de fecha y rangos por query string |
| `DELETE` | `/api/sensors/readings` | JSON `ok`/`deleted` | Objeto con lista `ids` |
| `DELETE` | `/api/sensors/readings/all` | JSON `ok`/`deleted` | Exige `{"confirm": true}` |

Las lecturas ausentes permanecen explícitas; no se inventan valores. Las
fechas de almacenamiento son UTC y los filtros de fechas calendario se
interpretan usando `APP_TIMEZONE`.

### Timelapse — features `camera` y `timelapse`

| Método | Ruta | Resultado principal | Entrada o efecto |
|---|---|---|---|
| `GET` | `/api/timelapse/status` | JSON de estado y configuración | Consulta servicio local |
| `PUT` | `/api/timelapse/config` | JSON de estado o `error` | Configura intervalo, captura, luz, sensores y `capture_overlay_enabled` |
| `POST` | `/api/timelapse/start` | JSON de estado o `error` | Inicia capturas |
| `POST` | `/api/timelapse/stop` | JSON de estado o `error` | Detiene capturas |
| `GET` | `/api/timelapse/folders` | JSON `folders`/`selected` | Lista almacenamiento local |
| `GET` | `/api/timelapse/captures?folder=…` | JSON `folder`/`captures`/`total` | Lista capturas locales |
| `GET` | `/api/timelapse/capture/download?folder=…&path=…` | Archivo de captura | Descarga individual |
| `POST` | `/api/timelapse/captures/download` | ZIP adjunto | Objeto `folder`/`captures` |
| `DELETE` | `/api/timelapse/captures` | JSON `ok`/`deleted`/`folder` | Borra selección explícita, incluso del timelapse activo |
| `GET` | `/api/timelapse/folders/<folder_name>/download` | ZIP adjunto | Descarga carpeta |
| `DELETE` | `/api/timelapse/folders/<folder_name>` | JSON `ok`/`deleted_folder`/`timelapse_resumed` | Borra carpeta validada; si está activa, pausa y reanuda el timelapse sobre una carpeta vacía |

Con `capture_overlay_enabled=true`, cada JPEG guardado incluye fecha/hora local
(`DD/MM/AAAA HH:MM:SS`) y la última telemetría BLE cacheada. Los sensores sin
dato se muestran como `--`; esta función no provoca lecturas BLE adicionales.

### Tuya — feature `tuya`

| Método | Ruta | Resultado principal | Acceso remoto |
|---|---|---|---|
| `GET` | `/api/tuya/status` | JSON `ok` o `error` | Sí; endpoint legado para dispositivo configurado |
| `POST` | `/api/tuya/on` | JSON `ok` o `error` | Sí; comando legado de encendido |
| `POST` | `/api/tuya/off` | JSON `ok` o `error` | Sí; comando legado de apagado |
| `GET` | `/api/tuya/devices` | JSON `ok`/`devices` | No; sólo SQLite |
| `POST` | `/api/tuya/devices` | JSON `ok`/`device` o `error` | No; alta local |
| `PATCH` | `/api/tuya/devices/<device_pk>` | JSON `ok`/`device` o `error` | No; metadatos locales |
| `POST` | `/api/tuya/devices/<device_pk>/details` | JSON `ok`/`device` o `error` | Sí; refresh explícito |
| `POST` | `/api/tuya/devices/<device_pk>/status` | JSON `ok` o `error` | Sí; comando explícito `{"on": bool}` |
| `GET` | `/api/tuya/devices/<device_pk>/status` | JSON `ok`/`device` o `error` | Sí; refresh explícito |

No se debe hacer polling de Tuya Cloud. La carga del dashboard y el listado de
dispositivos deben usar SQLite. Las consultas remotas son exclusivamente
acciones explícitas del usuario para preservar cuota.

## Envelopes históricos protegidos

Actualmente conviven estas familias:

- Administración y cámara: `{"status": "…", "message": "…"}` en varias
  operaciones y validaciones.
- ESP32 y Tuya: `{"ok": false, "error": "…"}` para errores habituales.
- Sensores y timelapse: `{"error": "…"}` para validación y fallos.
- El manejador global de excepciones inesperadas responde
  `{"error": "Internal server error"}` con HTTP `500`.

Los tests congelan ejemplos representativos. Esto no declara deseable la
inconsistencia: permite diseñar después una normalización compatible o una API
versionada sin perder conocimiento del contrato existente.

## Alcance de los tests de contrato

`tests/test_api_contracts.py` comprueba:

1. Las 49 reglas exactas del perfil completo: método, URL y endpoint Flask.
2. Envelopes y códigos de validación representativos por dominio.
3. Correspondencia completa entre Flask y las operaciones OpenAPI.
4. Sincronización del archivo generado y resolución de referencias locales.

Los tests funcionales existentes siguen cubriendo payloads, persistencia,
traducción de comandos y respuestas concretas. Esta suite se ejecuta sin
validación física: no certifica cámara, Bluetooth, servos, sensores ni Tuya
Cloud reales.
