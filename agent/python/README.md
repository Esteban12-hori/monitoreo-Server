# Agente de Monitoreo

Este agente es un script ligero en Python diseñado para recolectar métricas del sistema (CPU, RAM, Disco, Docker) y enviarlas a un servidor central de monitoreo.

## 🚀 Características
- **Ligero**: Consume mínimos recursos.
- **Intervalo Configurable**: Por defecto envía datos cada **40 minutos** (2400 segundos), pero es ajustable.
- **Seguro**: Autenticación mediante Tokens y soporte para TLS/SSL.
- **Métricas**:
  - Uso de CPU (Total y por núcleo).
  - Uso de Memoria RAM.
  - Uso de Disco.
  - Estado de contenedores Docker (si está instalado).

---

## 📦 Instalación y Configuración

Existen dos formas de instalar el agente:

### Opción A: Instalación Automática (Recomendada)
El script `install.py` te guiará paso a paso para instalar dependencias, registrar el servidor y crear la configuración.

1. Abre una terminal en la carpeta del agente:
   ```bash
   cd agent/python
   ```
2. Ejecuta el instalador:
   ```bash
   python install.py
   ```
3. Sigue las instrucciones en pantalla:
   - Ingresa la URL de tu servidor (ej: `http://20.153.165.55`).
   - Asigna un nombre a este servidor (ej: `servidor-produccion-01`).
   - El instalador guardará el token automáticamente.

### Opción B: Configuración Manual
Si prefieres configurar todo manualmente o automatizarlo con scripts:

1. **Instalar Dependencias**:
   ```bash
   pip install -r requirements.txt
   ```
   *(O manualmente: `pip install requests psutil`)*

2. **Registrar el Agente** (Obtener Token):
   Ejecuta este comando para obtener tu token de acceso desde el servidor:
   ```bash
   curl -X POST http://TU_IP_SERVIDOR/api/register \
        -H "Content-Type: application/json" \
        -d "{\"server_id\": \"NOMBRE_DE_TU_SERVIDOR\"}"
   ```
   Copia el `token` que recibirás en la respuesta JSON.

3. **Crear Archivo de Configuración**:
   Crea un archivo llamado `agent.config.json` en la misma carpeta que `agent.py` con el siguiente contenido:
   ```json
   {
     "server": "http://TU_IP_SERVIDOR",
     "server_id": "NOMBRE_DE_TU_SERVIDOR",
     "token": "PEGA_AQUI_TU_TOKEN",
     "interval": 2400,
     "verify": ""
   }
   ```
   - `interval`: Tiempo en segundos entre reportes (2400s = 40 minutos).
   - `verify`: Ruta al certificado SSL (déjalo vacío `""` para HTTP o HTTPS estándar).

---

## ▶️ Ejecución

Para iniciar el agente simplemente ejecuta:

```bash
python agent.py
```

Deberías ver un mensaje indicando que el agente ha iniciado. El script se mantendrá en ejecución enviando datos cada 40 minutos.

### 🖥️ Ejecutar en Segundo Plano (Modo Servicio)

Para que el agente se inicie automáticamente con el sistema y corra en segundo plano (sin dejar la terminal abierta):

#### Linux (Systemd)
La forma profesional es crear un servicio de sistema.

1. Crea el archivo de servicio:
   ```bash
   sudo nano /etc/systemd/system/monitor-agent.service
   ```

2. Pega el siguiente contenido (ajusta las rutas según donde descargaste el agente):
   ```ini
   [Unit]
   Description=Agente de Monitoreo
   After=network.target

   [Service]
   Type=simple
   User=root
   WorkingDirectory=/ruta/a/tu/carpeta/agent/python
   ExecStart=/usr/bin/python3 /ruta/a/tu/carpeta/agent/python/agent.py
   Restart=always
   RestartSec=60

   [Install]
   WantedBy=multi-user.target
   ```

3. Activa e inicia el servicio:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable monitor-agent
   sudo systemctl start monitor-agent
   ```

#### Windows (Sin ventana)
Para ejecutarlo sin que aparezca la ventana negra de la terminal, usa `pythonw` en lugar de `python`.

1. **Opción Rápida**:
   ```powershell
   Start-Process -WindowStyle Hidden -FilePath "pythonw" -ArgumentList "agent.py"
   ```

2. **Opción Permanente (Inicio de Windows)**:
   - Crea un acceso directo al archivo `agent.py`.
   - Haz clic derecho en el acceso directo -> Propiedades.
   - En "Destino", cambia `python.exe` por `pythonw.exe`.
   - Mueve este acceso directo a la carpeta de Inicio (`Win + R` y escribe `shell:startup`).

#### Linux/MacOS (Alternativa con PM2)
Si prefieres usar un gestor de procesos moderno como PM2 (requiere Node.js):

1. **Instalar PM2**:
   ```bash
   npm install -g pm2
   ```

2. **Iniciar el Agente**:
   ```bash
   pm2 start agent.py --name monitor-agent --interpreter python3
   ```

3. **Comandos Útiles**:
   - Ver estado: `pm2 status`
   - Ver logs: `pm2 logs monitor-agent`
   - Reiniciar: `pm2 restart monitor-agent`
   - Detener: `pm2 stop monitor-agent`

4. **Persistencia (Inicio automático)**:
   ```bash
   pm2 save
   pm2 startup
   ```
   *(Copia y pega el comando que te muestre la terminal para finalizar).*

---

## 🛠️ Solución de Problemas

- **Error de conexión**: Verifica que la URL en `agent.config.json` sea correcta y que el servidor sea accesible desde esta máquina.
- **Falta de permisos**: Si no detecta Docker o Discos, intenta ejecutarlo como Administrador o con `sudo`.
- **Cambiar intervalo**: Edita el valor `"interval"` en `agent.config.json` y reinicia el agente.
