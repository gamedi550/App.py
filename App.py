import streamlit as st
import serial
import serial.tools.list_ports
import struct
import time
import re

# 1. CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(page_title="FPV Diagnostic Tool", page_icon="🛠️", layout="wide")

# 2. INICIALIZACIÓN ESTRICTA (Esto evita por completo el AttributeError)
if "conectado" not in st.session_state:
    st.session_state.conectado = False
if "ser_conn" not in st.session_state:
    st.session_state.ser_conn = None

# --- DICCIONARIO DE ERRORES DE ARMADO (ARMING DISABLE FLAGS) ---
BETAFLIGHT_ARMING_FLAGS = {
    0: ("NO_GYRO", "🔴 Falla en el Giroscopio: No se detecta o está dañado. Revisa soldaduras o cambia la FC."),
    1: ("FAILSAFE", "⚠️ Failsafe Activo: Tu radio está apagada, desvinculada o el receptor (RX) no tiene señal."),
    2: ("RX_FAILSAFE", "📡 RX Failsafe: El receptor detecta pérdida de señal con la estación de radio."),
    3: ("BAD_RX_RECOVERY", "⚡ Error de Recuperación RX: Señal de radio corrupta o con exceso de ruido."),
    4: ("BOXFAILSAFE", "🛑 Failsafe por Switch: Se activó un switch de seguridad o failsafe manual en la radio."),
    5: ("RUNAWAY", "🔄 Runaway Takeoff Prevention: El dron abortó el despegue previo porque las hélices o motores giraban al revés."),
    6: ("CRASH_FLIP", "🐢 Modo Tortuga Activo: Tienes habilitado el modo de inversión tras choque (Crash Flip)."),
    7: ("THROTTLE", "🎮 Stick de Acelerador Alto: Baja la palanca de aceleración a 0 antes de armar."),
    8: ("ANGLE", "📐 Ángulo Excesivo: El dron está muy inclinado o de cabeza. Colócalo en una superficie plana."),
    9: ("BOOTLOG", "📝 Bootlog Activo: Error crítico durante el arranque de la controladora."),
    12: ("MOTOR_PROTO", "⚙️ Protocolo de Motores: Configuración incorrecta del protocolo de los ESCs (ej. DShot no compatible)."),
    13: ("NAVIGATION", "🌐 Falla de Navegación / GPS: Esperando bloqueo de satélites GPS suficientes (GPS Rescue)."),
    14: ("COMPASS", "🧭 Brújula no Calibrada: El magnetómetro requiere calibración o detecta interferencia electromagnética."),
    15: ("ACC_CALIBRATION", "⚖️ Acelerómetro sin Calibrar: Calibra el acelerómetro en una superficie completamente plana."),
    16: ("ARM_SWITCH", "🔘 Switch de Armado: Ya tienes el switch de armado activo. Apágalo y vuélvelo a encender."),
    17: ("HARDWARE_FAILURE", "🚨 FALLA DE HARDWARE: Componente físico dañado en la placa (Barómetro, Giroscopio, etc.)."),
    20: ("LOAD", "🧠 Sobrecarga de CPU: El procesador de la FC está saturado. Baja los kHz del ciclo PID o desactiva funciones."),
    21: ("CALIBRATING", "⏳ Calibrando Sensores: Deja el dron completamente quieto mientras termina de iniciar."),
    22: ("CLI", "💻 Modo CLI Activo: Estás dentro de la línea de comandos de Betaflight."),
    23: ("CMS_MENU", "📺 Menú OSD Abierto: Cierra el menú de configuración visual en tus gogles antes de armar."),
    25: ("OSD", "📺 Actualizando OSD: El chip de video está ocupado configurando la pantalla."),
    28: ("REBOOT_REQD", "🔄 Reinicio Requerido: Guarda los cambios y desconecta/conecta la batería."),
    31: ("MSP", "🔌 Conectado a la PC (MSP): Tienes el cable USB puesto. ¡Por seguridad Betaflight no te dejará armar!"),
}

# --- FUNCIONES DE CONTROL CLI ---
def ejecutar_comando_cli(ser, comando):
    """Entra a modo CLI, ejecuta un comando y sale limpiamente"""
    try:
        ser.write(b'#')
        time.sleep(0.1)
        ser.read_all() # Limpiar buffer
        
        ser.write(f"{comando}\n".encode('utf-8'))
        time.sleep(0.2)
        respuesta = ser.read_all().decode('utf-8', errors='ignore')
        
        ser.write(b'exit\n')
        return respuesta
    except Exception as e:
        return f"Error de comunicación: {e}"

# --- INTERFAZ GRÁFICA ---
st.title("🛠️ FPV Diagnostic Tool & Centro de Soluciones")
st.markdown("Analiza la salud de tu dron, errores de armado, telemetría de video DJI O4 y estado térmico.")

# Columnas principales: Configuración izquierda, Diagnóstico derecha
col_config, col_status = st.columns([1, 3])

with col_config:
    st.subheader("🔌 Conexión USB")
    
    # Detección de puertos locales
    puertos = [port.device for port in serial.tools.list_ports.comports()]
    puerto_sel = st.selectbox("Selecciona Puerto COM/USB:", puertos if puertos else ["No se detectaron puertos"])
    
    # Alerta inteligente sobre ejecución en la Nube
    if "streamlit.app" in st.get_option("browser.serverAddress"):
        st.warning("⚠️ **Estás en la nube:** Los servidores web no pueden acceder al USB de tu computadora. Descarga este código y córrelo localmente con `streamlit run app.py` para usar el cable.")

    if not st.session_state.conectado:
        if st.button("🔌 Conectar Dron", type="primary", disabled=len(puertos) == 0):
            try:
                st.session_state.ser_conn = serial.Serial(puerto_sel, 115200, timeout=0.5)
                st.session_state.conectado = True
                st.success("¡Conectado con éxito!")
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo abrir el puerto: {e}")
    else:
        if st.button("❌ Desconectar Dron", type="secondary"):
            if st.session_state.ser_conn:
                st.session_state.ser_conn.close()
            st.session_state.conectado = False
            st.session_state.ser_conn = None
            st.rerun()

with col_status:
    if not st.session_state.conectado:
        st.info("Por favor, conecta tu controladora de vuelo (FC) por USB y presiona 'Conectar Dron' en el panel izquierdo.")
    else:
        st.success("🟢 Controladora de Vuelo en línea.")
        
        # Uso de pestañas para organizar los problemas
        tab_general, tab_dji, tab_osd, tab_termico = st.tabs([
            "🔍 Diagnóstico de Armado", 
            "📺 Enlace DJI O4 Air Unit", 
            "📊 Formato de OSD", 
            "🔥 Monitor Térmico"
        ])
        
        ser_actual = st.session_state.ser_conn
        
        # ----------------------------------------------------------------
        # PESTAÑA 1: DIAGNÓSTICO GENERAL DE ARMADO
        # ----------------------------------------------------------------
        with tab_general:
            st.subheader("🚫 ¿Por qué no arranca mi dron?")
            if st.button("🔄 Escanear Banderas de Bloqueo"):
                # Enviar comando MSP_STATUS nativo
                packet = b"$M<\x00\x65\x65"
                ser_actual.write(packet)
                header = ser_actual.read(5)
                
                if len(header) == 5 and header[0:3] == b"$M>":
                    size = header[3]
                    cmd = header[4]
                    payload = ser_actual.read(size)
                    ser_actual.read(1) # Checksum
                    
                    if cmd == 101 and len(payload) >= 14:
                        cycleTime, i2c_errors, sensors, setting_mode, armingFlags = struct.unpack("<HHHII", payload[:14])
                        
                        st.write("### 🧠 Estado del bus I2C:")
                        if i2c_errors > 0:
                            st.error(f"❌ Se detectaron {i2c_errors} errores I2C. Revisa si hay cables de sensores haciendo falso contacto.")
                        else:
                            st.success("🟢 Líneas de comunicación de hardware estables (0 errores I2C).")
                        
                        st.write("### 🚫 Causas de bloqueo detectadas:")
                        fallas = []
                        for bit, (nombre, desc) in BETAFLIGHT_ARMING_FLAGS.items():
                            if armingFlags & (1 << bit):
                                if nombre != "MSP":  # Omitir la advertencia de cable USB estándar
                                    fallas.append(desc)
                        
                        if not fallas:
                            st.success("🏁 ¡Ninguna falla crítica bloqueando los motores! Listo para armar en campo.")
                        else:
                            for f in fallas:
                                st.warning(f)
                else:
                    st.error("Error al obtener el estado MSP. Verifica que no tengas otra app de drones abierta.")

        # ----------------------------------------------------------------
        # PESTAÑA 2: ENLACE DJI O4 AIR UNIT
        # ----------------------------------------------------------------
        with tab_dji:
            st.subheader("🎥 Diagnóstico de Transmisión Digital DJI O4")
            if st.button("🔍 Comprobar Conexión de Video"):
                with st.spinner("Analizando puertos UART de video..."):
                    log_vtx = ejecutar_comando_cli(ser_actual, "vtx")
                    log_min = log_vtx.lower()
                    
                    if "type: msp" in log_min and ("ready: yes" in log_min or "is ready" in log_min):
                        st.success("🟢 **DJI O4 Detectada:** La comunicación serial entre la FC y la Air Unit funciona perfectamente.")
                    elif "type: msp" in log_min:
                        st.error("❌ **Falla de comunicación física (Ready: NO):** La configuración existe pero la unidad DJI no responde.")
                        st.markdown("""
                        **Soluciones rápidas:**
                        1. **Conecta la LiPo:** La O4 no enciende solo con el USB de la computadora.
                        2. **Cables TX/RX Invertidos:** Asegúrate de que el pin TX de la Air Unit vaya al RX de tu placa de vuelo (y viceversa).
                        """)
                    else:
                        st.warning("⚠️ El protocolo MSP no está asignado al transmisor de video.")
                        st.info("Solución: Ve a la pestaña 'Puertos' en Betaflight y activa la casilla MSP en el UART correcto.")

        # ----------------------------------------------------------------
        # PESTAÑA 3: DIAGNÓSTICO DE FORMATO OSD
        # ----------------------------------------------------------------
        with tab_osd:
            st.subheader("📊 Ajuste de Caracteres en Pantalla (OSD)")
            if st.button("🔧 Verificar Formato de Pantalla"):
                raw_osd = ejecutar_comando_cli(ser_actual, "get osd_video_system")
                match = re.search(r'osd_video_system\s*=\s*(\w+)', raw_osd)
                
                if match:
                    sistema = match.group(1).upper()
                    st.metric(label="Formato de Video Configurado", value=sistema)
                    
                    if sistema in ["PAL", "NTSC"]:
                        st.error("❌ **Error de Formato:** Tienes configurado un sistema analógico.")
                        st.info("🛠️ **Solución para corregirlo:** Copia y pega los siguientes comandos en la pestaña CLI de Betaflight para cambiarlo a Alta Definición:")
                        st.code("set osd_video_system = HD\nsave", language="bash")
                    else:
                        st.success("🟢 **Formato Correcto:** Configuración optimizada para pantallas HD digitales.")
                else:
                    st.warning("No se pudo obtener el parámetro automático.")

        # ----------------------------------------------------------------
        # PESTAÑA 4: MONITOR TÉRMICO
        # ----------------------------------------------------------------
        with tab_termico:
            st.subheader("🌡️ Temperatura en Banco de Trabajo")
            if st.button("🌡️ Leer Sensores de Temperatura"):
                raw_status = ejecutar_comando_cli(ser_actual, "status")
                match_temp = re.search(r'Temp=(\d+)(?:degC|C)', raw_status, re.IGNORECASE)
                
                if match_temp:
                    temp = int(match_temp.group(1))
                    if temp < 60:
                        st.success(f"🟢 Temperatura segura: {temp}°C")
                    elif 60 <= temp < 75:
                        st.warning(f"⚠️ Temperatura elevada: {temp}°C. Ponle un ventilador al dron si vas a seguir probando en la mesa.")
                    else:
                        st.error(f"🚨 ¡SOBRECALENTAMIENTO CRÍTICO!: {temp}°C. ¡Desconecta la batería inmediatamente para proteger la DJI O4 y los componentes!")
                else:
                    st.info("Esta placa de vuelo no reporta telemetría de temperatura interna.")
