# Troubleshooting

## Método

Ante un error:

1. Leer traceback completo.
2. Identificar el primer error del proyecto.
3. Separar causa primaria y errores secundarios.
4. Determinar dónde ocurre:
   - PC.
   - Raspberry Pi.
   - ESP32.
   - Navegador.
   - Red.
5. Verificar versiones.
6. Verificar hardware.
7. Probar la hipótesis mínima.
8. Aplicar el cambio mínimo.
9. Confirmar regresiones.

No reinstalar todo como primer paso.

## Información básica

```bash
python --version
pip --version
uname -a
cat /etc/os-release
git status
git log -1 --oneline
```

## Flask

```bash
python app.py
curl -i http://localhost:5000/
curl -i http://localhost:5000/api/camera/camera_status
```

Revisar:

- Binding `0.0.0.0`.
- Puerto.
- Imports.
- Blueprints.
- Application factory.
- Variables de entorno.
- Secretos.
- Base de datos.

## Administración del sistema

El dashboard puede disparar un reinicio de la Raspberry Pi mediante:

```bash
curl -i -X POST http://localhost:5000/api/admin/reboot \
  -H "Content-Type: application/json" \
  -d '{"confirm": true}'
```

Si Flask no corre como root, el usuario del servicio debe tener permiso para
ejecutar `sudo systemctl reboot` sin requerir TTY ni contraseña interactiva.
Probar el endpoint sólo cuando sea aceptable interrumpir streaming, BLE, Tuya y
cualquier captura en curso.

## Cámara

```bash
rpicam-hello --list-cameras
rpicam-still -o test.jpg
```

También:

```bash
python -c "from picamera2 import Picamera2; print(Picamera2.global_camera_info())"
```

Problemas comunes:

- Cámara no detectada.
- Cable CSI.
- Puerto equivocado.
- Overlay.
- Biblioteca no instalada.
- Venv sin acceso a paquetes del sistema.
- Cámara ocupada.
- Control no soportado.

## Streaming

Probar:

```bash
curl -v http://localhost:5000/api/camera/video_feed
```

Revisar:

- Boundary.
- Bytes JPEG.
- Excepción en generador.
- Cliente desconectado.
- CPU.
- Memoria.
- Locks.
- Múltiples clientes.

## Bluetooth

```bash
rfkill list
sudo rfkill unblock bluetooth
systemctl status bluetooth
bluetoothctl show
bluetoothctl devices
bluetoothctl scan on
```

Problemas:

- Adaptador apagado.
- Servicio detenido.
- Dispositivo fuera de rango.
- UUID incorrecto.
- Cliente anterior abierto.
- ESP32 reiniciado.
- D-Bus.
- Permisos.

## ESP32

Revisar monitor serial.

Buscar:

- Brownout.
- Reinicio.
- Watchdog.
- Fallo de sensor.
- Error NVS.
- Desconexión BLE.
- Comando inválido.

Cuando el fallo ocurre al mover servos, medir alimentación.

## Tuya

Revisar:

- Variables de entorno.
- Región.
- Device ID cargado en el dashboard o `TUYA_DEVICE_ID` legado.
- Código de switch, normalmente `switch_1`.
- Local key o credenciales.
- Timeout.
- Conectividad.
- Respuesta API.
- Consumo de cuota en Tuya Dev Platform.

La aplicación debe seguir funcionando si Tuya falla.

El dashboard no debe hacer polling automático contra Tuya Cloud. El endpoint de
listado local de dispositivos no debe consumir llamadas remotas. Para
diagnosticar consumo excesivo, buscar:

- Intervalos JavaScript que llamen endpoints Tuya.
- Endpoints de listado que consulten `/status` remoto por dispositivo.
- Refresh automático de detalle/nombre remoto al agregar dispositivos.
- Reintentos sin backoff ante errores 429, cuota o red.

Las lecturas de estado, telemetría eléctrica, fallas o nombre remoto deben
hacerse sólo cuando el usuario presiona un botón de consulta/refresco en el
frontend. Encender/apagar es la operación prioritaria para gastar llamadas API.

## Base de datos

Primero consultar la identidad activa:

```bash
curl -s http://localhost:5000/api/system/capabilities
```

La instancia `default` utiliza el path histórico:

```bash
ls -l database/
sqlite3 database/app.db ".tables"
```

Una instancia nombrada utiliza por defecto:

```bash
sqlite3 data/<instancia>/app.db ".tables"
```

`DATABASE_PATH` puede reemplazar ambas ubicaciones.

Revisar:

- Ruta absoluta.
- Permisos.
- Esquema.
- Inicialización.
- Archivo corrupto.
- Migraciones.

## Red

```bash
hostname -I
ip addr
ip route
ping -c 4 8.8.8.8
ping -c 4 pi40.local
```

En Windows:

```powershell
ping pi40.local
ipconfig
```

Revisar:

- VPN.
- Firewall.
- mDNS.
- Avahi.
- Subred.
- Wi-Fi.

## Vite histórico

Error:

```text
This host is not allowed
```

Revisar:

```js
server: {
  allowedHosts: ['pi40.local']
}
```

Sólo aplica si Vite está en uso.

## Logs

```bash
journalctl -u cameracontrol.service -n 200 --no-pager
journalctl -u bluetooth -n 200 --no-pager
dmesg | tail -n 100
```

Si se ejecuta manualmente, capturar stdout y stderr.

## Verificación después de un cambio

1. Flask inicia.
2. Página carga.
3. Stream funciona.
4. Captura funciona.
5. Timelapse inicia y detiene.
6. ESP32 conecta.
7. Pan/tilt responde.
8. Posición configurada guarda y vuelve con `SET_ABS`.
9. Tuya no bloquea.
10. Logs no muestran errores nuevos.
