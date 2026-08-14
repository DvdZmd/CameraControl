# Perfiles de producto

## Propósito

CameraControl mantiene un único backend y selecciona su composición mediante un
perfil de producto. El perfil es configuración de despliegue del servidor: el
navegador no puede activar módulos ni cambiarlo durante la ejecución.

La selección se realiza con:

```dotenv
CAMERACONTROL_PROFILE=default
```

También puede pasarse un nombre explícito a `create_app(profile_name)` en
pruebas o integraciones. El parámetro explícito tiene precedencia sobre la
variable de entorno. Un perfil desconocido o con dependencias inválidas impide
el arranque con un error descriptivo; no existe fallback silencioso.

## Perfiles actuales

| Módulo | `default` | `starseek` | `fungiforge` |
|---|---:|---:|---:|
| Cámara | Sí | Sí | Sí |
| Timelapse | Sí | Sí | Sí |
| ESP32/BLE | Sí | Sí | Sí |
| Sensores e historial periódico | Sí | No | Sí |
| Tuya | Sí | No | Sí |

`default` preserva la composición histórica cuando no se configura ninguna
variable. `fungiforge` tiene por ahora la misma composición, pero establece una
identidad de producto independiente para cambios posteriores.

Pan/tilt, iluminación y conexión BLE todavía comparten `esp32_bp` y el mismo
controlador. Por eso no se anuncian como features independientes en esta etapa.
Separarlos requiere primero delimitar sus rutas y contratos sin cambiar el
protocolo vigente.

## Efecto de deshabilitar un módulo

Un módulo deshabilitado:

- no registra su blueprint HTTP;
- no crea su controlador externo, cuando corresponde;
- no inicia workers asociados;
- no ejecuta migraciones de compatibilidad específicas;
- no muestra su pestaña ni ejecuta sus llamadas periódicas en el dashboard.

Las tablas existentes no se eliminan al cambiar de perfil. Esto permite volver
a otro perfil sin pérdida de configuración o historial.

## Contrato para frontends

La composición activa se consulta sin acceder al hardware:

```http
GET /api/system/capabilities
```

Ejemplo:

```json
{
  "api_version": "1",
  "profile": "starseek",
  "features": {
    "camera": true,
    "timelapse": true,
    "esp32": true,
    "sensors": false,
    "tuya": false
  }
}
```

`features` describe la composición configurada, no la disponibilidad física en
tiempo real. Por ejemplo, `esp32: true` no afirma que exista una conexión BLE.
Los endpoints de estado de cada módulo siguen siendo responsables de informar
si el hardware está conectado o disponible.

## Dependencias validadas

- `timelapse` requiere `camera`.
- `sensors` requiere `esp32`.

Los perfiles se definen y validan en `profiles.py`. No contienen credenciales,
pines ni datos específicos del hardware.

## Prueba manual inicial

```bash
CAMERACONTROL_PROFILE=starseek python app.py
curl -s http://localhost:5000/api/system/capabilities
curl -i http://localhost:5000/api/sensors/readings
curl -i http://localhost:5000/api/tuya/devices
```

Las últimas dos peticiones deben responder `404` en StarSeek. Después se debe
verificar desde el dashboard que cámara, streaming, timelapse y ESP32 conservan
su comportamiento. Esto no reemplaza las pruebas físicas de cámara, BLE o
servos.
