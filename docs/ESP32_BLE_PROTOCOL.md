# ESP32 y protocolo BLE

## Propósito

El ESP32 controla el cabezal pan/tilt y puede centralizar sensores ambientales.

La Raspberry Pi se comunica mediante BLE.

Nombre habitual del dispositivo:

`ESP32-CameraHead`

El firmware vigente y confirmado es:

`PanTiltMicrocontroller/FungiESP.ino`

`PanTiltMicrocontroller/PanTiltPro.ino` se conserva como variante histórica y
no debe modificarse ni usarse como contrato actual.

El firmware vigente es la fuente de verdad para:

- Nombre BLE.
- UUIDs.
- Pines.
- Comandos.
- Formato de telemetría.
- Persistencia.
- Rangos de servos.

## Comandos conocidos

Comandos históricos o actuales:

- `PAN_LEFT`
- `PAN_RIGHT`
- `TILT_UP`
- `TILT_DOWN`
- `CENTER`
- `STOP`
- `SET_SPEED:<valor>`
- `SET_ABS:<pan>:<tilt>`

No asumir el formato exacto de `SET_ABS` sin revisar el firmware.

## Flujo BLE

```text
Raspberry Pi
    |
    | scan
    v
ESP32 encontrado
    |
    | connect
    v
GATT service
    |
    +--> RX characteristic: comandos
    +--> TX characteristic: notificaciones
```

## Diagnóstico por capas

### 1. Adaptador

Comprobar:

```bash
rfkill list
bluetoothctl show
systemctl status bluetooth
```

### 2. Escaneo

Comprobar que el dispositivo aparece:

```bash
bluetoothctl scan on
```

### 3. Conexión

Problemas frecuentes:

- Dispositivo fuera de alcance.
- ESP32 reiniciado.
- Conexión anterior sin cerrar.
- BlueZ ocupado.
- Alimentación inestable.

### 4. Servicios

Confirmar UUIDs.

No reutilizar UUIDs recordados sin revisar firmware.

### 5. Notificaciones

Verificar:

- Suscripción exitosa.
- Callback.
- Decodificación.
- Separación de mensajes.
- Estado cacheado.

### 6. Escritura

Validar comando antes de escribir.

No enviar comandos a frecuencia excesiva.

### 7. Telemetría

Puede incluir:

- Pan actual.
- Tilt actual.
- Velocidad.
- Temperatura.
- Humedad.
- Soil.
- Estado.

Documentar el formato real cuando se confirme.

### 8. Reconexión

El controlador debe:

- Detectar desconexión.
- Limpiar cliente anterior.
- Evitar instancias duplicadas.
- Poder reconectar.
- Cerrar al terminar Flask.

## Sync y async

Bleak es asíncrono.

Si el backend ofrece wrappers síncronos:

- Revisar event loop.
- Evitar `asyncio.run()` repetido dentro de un loop activo.
- Evitar bloquear el thread de Flask indefinidamente.
- Aplicar timeouts.
- Propagar errores claros.

## Movimiento

Experiencia esperada:

- Click: movimiento de un paso.
- Centro: ambos ejes.
- Posición configurada: guardar la posición actual reportada por telemetría y
  volver a ella con `SET_ABS`.
- Velocidad: seleccionable.
- Estado: visible.

No se implementará por ahora movimiento continuo al mantener pulsado. Cada
comando cardinal se consume una sola vez en `FungiESP.ino`. `STOP` existe para
limpiar órdenes pendientes, no para detener un movimiento sostenido.

Formato vigente de posición absoluta:

`SET_ABS:<pan>,<tilt>`

Ambos valores son pulsos en microsegundos dentro del rango configurado por el
firmware.

## API Flask

Endpoints específicos del dashboard:

- `GET /api/esp32/status`: estado BLE, última telemetría, posición configurada
  y perfil de velocidad persistidos cuando existan.
- `POST /api/esp32/connect`: conecta por BLE. Puede bloquear mientras escanea y
  negocia GATT.
- `POST /api/esp32/disconnect`: cierra la conexión BLE activa.
- `POST /api/esp32/move`: acepta `direction` con `left`, `right`, `up` o
  `down`; cada request envía un único paso.
- `POST /api/esp32/center`: envía `CENTER`.
- `POST /api/esp32/speed`: acepta `mode` entre 0 y 4, envía `SET_SPEED` y
  persiste el perfil seleccionado para rehidratar el dashboard.
- `POST /api/esp32/position/current`: guarda en SQLite la posición `P`/`T`
  recibida en la última telemetría válida. No mueve los servos.
- `POST /api/esp32/position/return`: valida la posición persistida y envía
  `SET_ABS:<pan>,<tilt>`.

El botón `Parar` no forma parte del dashboard actual. Aunque el firmware acepta
`STOP` para limpiar órdenes pendientes, no hay movimiento continuo que requiera
un botón dedicado de parada.

## Servos

Hardware conocido:

- Dos SG90.
- Pan y tilt.
- Fuente dedicada.
- GND común con lógica.

No fijar pines ni pulsos sin revisar firmware.

Valores históricos:

- Pulso mínimo aproximado: 500 µs.
- Pulso máximo aproximado: 2400 µs.
- Centro aproximado: 1450 µs.

Estos valores pueden cambiar.

## Persistencia

Datos candidatos:

- Configuración del dashboard en SQLite: posición custom `pan`/`tilt` y perfil
  de velocidad.
- En `FungiESP.ino`: pan, tilt y velocidad se restauran desde NVS al iniciar.

Preferir `Preferences`/NVS.

Evitar escrituras por cada paso.

Estrategias:

- Debounce.
- Guardar tras inactividad.
- Guardar sólo si cambió.
- Validar al iniciar.

El firmware vigente guarda pan/tilt con persistencia diferida para no escribir
flash por cada paso. Los cambios de perfil de velocidad se guardan de inmediato
porque son infrecuentes y deben sobrevivir reinicios aunque el ESP32 se apague
poco después del cambio.

No mover inmediatamente a una posición inválida.

## Sensores

Sensores conocidos:

- DHT22.
- DS18B20.
- Soil capacitivo v1.2.

Pines históricos:

- Pan GPIO 22.
- Tilt GPIO 23.
- DHT22 GPIO 32.
- Soil GPIO 34.
- DS18B20 GPIO 12 o 13.

Verificar siempre el `.ino`.

## Errores eléctricos

Síntomas:

- BLE se desconecta al mover servo.
- ESP32 se reinicia.
- Valores de sensor erráticos.
- Movimiento tembloroso.
- Cámara o Raspberry Pi pierde conectividad.

Causas:

- Fuente insuficiente.
- Ground deficiente.
- Ruido.
- Cables largos.
- Regulador inestable.
- Pico de corriente.

Nunca alimentar servos desde 3.3 V.

## Cambios de protocolo

Antes de cambiar un comando:

1. Actualizar firmware.
2. Actualizar Python.
3. Actualizar frontend.
4. Actualizar pruebas.
5. Actualizar este documento.
6. Mantener compatibilidad o versionar protocolo.
