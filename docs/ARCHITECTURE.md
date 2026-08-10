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

### Frontend

El dashboard se renderiza con Jinja a partir de un shell mínimo y componentes
parciales organizados por dominio:

- `templates/index.html`: estructura general y orden de carga de scripts.
- `templates/components/layout/`: barra superior, streaming y navegación.
- `templates/components/tabs/`: contenedores de las pestañas principales.
- `templates/components/{camera,timelapse,esp32,sensors,devices}/`: controles de
  cada dominio.
- `static/js/components/`: comportamiento separado por dominio.
- `static/js/dashboard.js`: registro central de eventos e inicialización.

Los scripts son clásicos y se cargan en un orden explícito. Esta organización
mantiene los contratos actuales basados en IDs y atributos `data-*`, a la vez
que delimita los futuros componentes para la migración a Vue.js.

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
- Lectura de estado bajo demanda.
- Encendido y apagado.
- Alta local de dispositivos ya registrados en Tuya IoT Platform.
- Traducción de errores externos.

Tuya Cloud tiene cuota mensual limitada en el plan gratuito observado
(`Cloud Develop Base Resource Trial`: 30000 API calls/mes, 140000 Message
Subscription/mes, 50 dispositivos). La arquitectura debe reservar llamadas para
comandos críticos, especialmente prender/apagar switches. No debe existir
polling automático contra Tuya Cloud desde frontend o backend.

El listado de dispositivos usa SQLite y no consulta estado remoto. Las lecturas
informativas remotas, como estado eléctrico, fallas o nombre remoto, deben
ejecutarse sólo por acción explícita del usuario. Después de un comando de
encendido/apagado puede mostrarse el último comando enviado como estado local,
pero no como confirmación remota.

Las credenciales de usuario, API key, secret, región y schema viven en
variables de entorno. El dashboard sólo persiste metadatos operativos del
dispositivo: alias local editable, nombre remoto reportado por Tuya cuando está
disponible, `device_id` y código de switch.

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

### Historial de telemetría BLE

El logger de sensores toma snapshots del último payload ya recibido por el
controlador BLE compartido. No inicia escaneos, conexiones ni lecturas GATT.
Solo persiste una muestra cuando el ESP32 está conectado y existen valores
numéricos válidos para `DT`, `DH`, `DS` y `SP`.

`SensorReading` guarda las cuatro métricas ambientales. Sus columnas nullable
`pan_pulse_us` y `tilt_pulse_us` asocian la posición reportada por la última
telemetría a una captura. `timelapse_folder_id` referencia a `TimelapseFolder`,
que conserva una sola vez el nombre de carpeta; el logger ambiental periódico
no completa ninguno de esos campos.

La frecuencia se configura mediante `SENSOR_LOG_ENABLED` y
`SENSOR_LOG_INTERVAL_SECONDS`. La consulta se expone bajo
`GET /api/sensors/readings` y nunca provoca tráfico BLE.

La inicialización puede crear tablas, pero no debe ocultar errores críticos.

## Logging centralizado

`logs/logging_config.py` configura el logger raíz y conecta `app.logger` por
propagación. Los módulos deben declarar únicamente
`logging.getLogger(__name__)`; no deben crear handlers ni escribir logs de
aplicación con `print()`.

Los destinos son independientes:

- Consola mediante `StreamHandler`.
- Archivo mediante `RotatingFileHandler`.
- SQLite mediante `DatabaseLogHandler` y una cola acotada.

El handler SQLite se habilita después de `db.create_all()`. Su worker utiliza
un contexto y una sesión separados del request original, hace rollback ante
fallos y escribe sus propios errores directamente a `stderr` para evitar
recursión. `ErrorLog` se conserva como tabla legacy; los eventos nuevos usan
`ApplicationLog`.

Los niveles de los destinos son umbrales estándar. `LOG_LEVEL` actúa como
umbral global, por lo que no debe configurarse por encima de un destino que
necesite recibir eventos más detallados.

El contexto HTTP se incorpora mediante un filtro: request ID, método y path.
Las excepciones Flask no controladas se registran en un error handler global;
las `HTTPException` esperadas conservan su comportamiento normal.

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
