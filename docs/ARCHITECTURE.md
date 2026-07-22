# Arquitectura de CameraControl

## Objetivo

CameraControl centraliza el control de una cámara Raspberry Pi y dispositivos IoT relacionados dentro de una aplicación Flask accesible desde la red local.

La aplicación debe mantener desacoplados:

- Servidor web.
- Cámara.
- BLE y ESP32.
- Sensores.
- Tuya.
- Persistencia.
- Logging.
- Interfaz web.

## Componentes principales

### `app.py`

Punto de entrada mínimo.

Responsabilidades:

- Crear la aplicación mediante `create_app()`.
- Registrar la ruta inicial si corresponde.
- Ejecutar Flask en desarrollo.

No debe contener lógica de cámara, BLE, Tuya o base de datos.

### `app_factory.py`

Responsable de:

- Crear Flask.
- Cargar configuración.
- Inicializar SQLAlchemy.
- Registrar blueprints.
- Crear y registrar controladores compartidos.
- Inicializar integraciones opcionales.
- Ejecutar limpieza al terminar.

La conexión inicial con Tuya se ejecuta en un hilo daemon para no bloquear la
creación de Flask. El controlador se registra antes en `app.config`.

Los controladores compartidos pueden registrarse en `app.config`.

Ejemplos conceptuales:

- `BLE_CAMERA_CONTROLLER`
- `TUYA_CONTROLLER`

Las integraciones opcionales no deben impedir que Flask inicie.

### Blueprints

La API se organiza por dominios.

#### Cámara

Prefijo esperado:

`/api/camera`

Puede incluir:

- Estado y capacidades.
- Streaming.
- Streaming sincronizado.
- Captura.
- Presets.
- Reset.
- Controles.
- Timelapse.

#### ESP32

Prefijo esperado:

`/api/esp32`

Puede incluir:

- Estado.
- Connect.
- Disconnect.
- Command.
- Move.
- Center.
- Speed.

#### Tuya

Debe encapsular:

- Conexión con la API.
- Lectura de estado.
- Encendido y apagado.
- Alta local de dispositivos ya registrados en Tuya IoT Platform.
- Traducción de errores externos.

Las credenciales de usuario, API key, secret, región y schema viven en
variables de entorno. El dashboard sólo persiste metadatos operativos del
dispositivo: nombre informativo, `device_id` y código de switch.

#### Administración

Puede incluir:

- Estado de aplicación.
- Logs.
- Configuración.
- Actualización de software.

## Flujo de una petición

```text
Navegador
   |
   v
Flask Blueprint
   |
   v
Validación de entrada
   |
   v
Servicio o controlador
   |
   +--> Cámara
   +--> ESP32 BLE
   +--> Tuya
   +--> Base de datos
   |
   v
Respuesta HTTP / JSON / MJPEG
```

Las rutas no deben duplicar lógica del controlador.

## Dependencias compartidas

Los objetos con estado deben tener una única instancia deliberada cuando controlan un recurso físico exclusivo.

Ejemplos:

- Una instancia activa de cámara.
- Un controlador BLE para un ESP32.
- Un controlador Tuya compartido.

Evitar crear una instancia de cámara o cliente BLE por request.

## Base de datos

SQLite mediante Flask-SQLAlchemy.

Usos posibles:

- Configuración.
- Presets.
- Estado persistente.
- Errores.
- Historial de eventos.

La inicialización puede crear tablas, pero no debe ocultar errores críticos.

## Degradación controlada

El sistema debe aislar fallas.

| Componente | Resultado esperado si falla |
|---|---|
| Cámara | API devuelve error claro; Flask sigue vivo |
| ESP32 | Cámara y Tuya continúan |
| Tuya | Warning; cámara y BLE continúan |
| Base de datos | Error explícito; evitar pérdida silenciosa |
| Frontend | API sigue siendo diagnosticable |

## Contratos

Antes de modificar un endpoint:

1. Buscar llamadas desde JavaScript.
2. Buscar documentación.
3. Buscar pruebas.
4. Revisar nombres de campos.
5. Revisar códigos HTTP.
6. Revisar compatibilidad hacia atrás.

Antes de modificar un comando BLE:

1. Revisar Python.
2. Revisar firmware.
3. Revisar frontend.
4. Revisar telemetría.
5. Revisar persistencia.

## Configuración

La configuración debería separarse en:

- Valores por defecto.
- Variables de entorno.
- Configuración sensible.
- Capacidades detectadas en runtime.

No mezclar secretos con constantes públicas.

## Evolución recomendada

Cuando el proyecto crezca, considerar:

- Servicios con interfaces claras.
- Adaptadores para hardware.
- Mocks de cámara y BLE.
- Esquemas de validación.
- Estado de aplicación centralizado.
- Pruebas de integración.
- Health checks.
- Migrations para la base de datos.

No introducir estas capas si añaden complejidad sin resolver un problema real.
