# Hardware

## Raspberry Pi

Hardware conocido:

- Raspberry Pi 5, 8 GB.
- Raspberry Pi 4.
- Raspberry Pi 3.
- Raspberry Pi Zero 2 W.

Sistema habitual:

- Raspberry Pi OS Bookworm.

El comportamiento puede variar por modelo, kernel, firmware y cámara.

## Cámaras

### Camera v1.3

- Sensor OV5647.
- 5 MP.
- Sin autofocus.

### Camera v2.1

- Sensor IMX219.
- 8 MP.
- Sin autofocus.

### Camera v3

- Sensor IMX708.
- 12 MP.
- Autofocus.
- Resolución máxima aproximada 4608×2592 según modo y configuración.

### Arducam IMX519

- 16 MP.
- Autofocus.
- Hubo problemas previos de detección.

No asumir compatibilidad sin probar en la Raspberry Pi concreta.

## Diferencias de imagen

Se observaron diferencias entre cámaras al cambiar resolución:

- Recorte.
- Zoom aparente.
- Campo de visión.
- Rotación.
- Modos de sensor.

Una resolución igual no garantiza una imagen equivalente entre sensores.

## Servos

- Dos SG90.
- Uno para pan.
- Uno para tilt.

Recomendaciones:

- Fuente separada.
- GND común.
- Condensadores cerca de la alimentación.
- Evitar alimentar desde el pin 5 V de la Raspberry Pi si la corriente no está adecuadamente dimensionada.
- Revisar picos de corriente.

## Reguladores

Se utilizaron LM2596 separados para:

- Servos.
- ESP32 y sensores.

Los valores exactos de tensión deben confirmarse antes de conectar.

No asumir que 3.3 V es adecuado para servos SG90.

## Sensores

### DHT22

- Temperatura.
- Humedad.
- Señal digital.
- Requiere timing sensible.

### DS18B20

- Temperatura.
- OneWire.
- Puede compartir bus con múltiples sensores.

### Soil capacitivo v1.2

- Salida analógica.
- En ESP32 debe conectarse a un ADC válido.
- Requiere calibración seca/húmeda.

### HL-69

Sensor resistivo usado históricamente.

Puede corroerse con uso prolongado.

## ESP32

Funciones:

- BLE.
- Servos.
- Sensores.
- Telemetría.
- Persistencia.
- Conmutación low-side de una tira LED de 5 V mediante GPIO21 y transistor
  NPN S8050. El firmware usa PWM a 20 kHz y resolución de 8 bits; `0%` mantiene
  el transistor apagado y `100%` aplica duty máximo.

La tira debe alimentarse desde su fuente de 5 V, compartir GND con el ESP32 y
respetar la corriente admisible del transistor y del cableado. GPIO21 controla
la base del driver; no alimenta directamente la tira.

La base del S8050 debe tener un resistor pull-down hacia GND (típicamente entre
10 kΩ y 47 kΩ), además del resistor limitador en serie desde GPIO21. El
pull-down mantiene el transistor apagado mientras GPIO21 está en alta
impedancia durante encendido, reset y bootloader. El firmware fuerza GPIO21 a
LOW como primera acción de `setup()`, pero no puede garantizar el nivel antes
de que comience a ejecutarse; por eso el pull-down físico es necesario para un
arranque siempre apagado.

`ESP32Servo` y el control de intensidad de la luz comparten el periférico LEDC
del ESP32. El firmware adjunta primero los servos de GPIO22/GPIO23 y después el
PWM de GPIO21 para evitar que la asignación dinámica de canales deje sin señal
al servo pan en algunas versiones del core Arduino-ESP32.

El modelo exacto y la placa seleccionada afectan:

- Pines.
- ADC.
- PWM.
- Bluetooth.
- Bootstrapping.

Evitar pines de arranque problemáticos sin revisar la placa.

## Alimentación

Principios:

- Dimensionar corriente con margen.
- Compartir GND cuando hay señales comunes.
- Mantener servos separados de lógica sensible.
- Usar cables cortos.
- Desacoplar alimentación.
- Medir tensión durante movimiento.
- No confiar sólo en tensión en vacío.

## Red

Acceso local habitual:

- Flask: puerto 5000.
- Vite histórico: puerto 5173.
- Hostname histórico: `pi40.local`.

Problemas conocidos:

- VPN en Windows bloqueando mDNS.
- Host no permitido en Vite.
- Wi-Fi deshabilitado o desconectado.
- Hostname no resuelto.

## Bluetooth

Comandos útiles:

```bash
rfkill list
sudo rfkill unblock bluetooth
systemctl status bluetooth
bluetoothctl show
bluetoothctl scan on
```

## Cámara

En Bookworm, usar preferentemente:

```bash
rpicam-hello --list-cameras
rpicam-still -o test.jpg
```

En instalaciones antiguas pueden existir:

```bash
libcamera-hello
libcamera-still
```

## Seguridad física

Antes de probar movimiento:

- Confirmar límites mecánicos.
- Confirmar orientación.
- Confirmar centro.
- Confirmar pulsos.
- Evitar que cables queden tensos.
- Probar a baja velocidad.
- Probar pasos individuales antes de usar retorno a posición absoluta.
