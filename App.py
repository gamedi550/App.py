import streamlit as st
import serial
import serial.tools.list_ports
import struct
import time
import re

# 1. CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(page_title="FPV Diagnostic Tool", page_icon="🛠️", layout="wide")

# 2. INICIALIZACIÓN ESTRICTA DE VARIABLES DE SESIÓN
if "conectado" not in st.session_state:
    st.session_state.conectado = False
if "ser_conn" not in st.session_state:
    st.session_state.ser_conn = None

# --- DICCIONARIO DE ERRORES DE ARMADO ---
BETAFLIGHT_ARMING_FLAGS = {
    0: ("NO_GYRO", "🔴 Falla en el Giroscopio: No se detecta o está dañado. Revisa soldaduras."),
    1: ("FAILSAFE", "⚠️ Failsafe Activo: Tu radio está apagada o el receptor (RX) no tiene señal."),
    2: ("RX_FAILSAFE", "📡 RX Failsafe: El receptor detecta pérdida de señal con la radio."),
    5: ("RUNAWAY", "🔄 Runaway Prevention: El dron abortó el despegue previo (hélices al revés)."),
    7: ("THROTTLE", "🎮 Stick de Acelerador Alto: Baja la palanca de aceleración a 0."),
    8: ("ANGLE", "📐 Ángulo Excesivo: El dron está muy inclinado o de cabeza."),
    17: ("HARDWARE_FAILURE", "🚨 FALLA DE HARDWARE: Componente físico dañado en la placa."),
    31: ("MSP", "🔌 Conectado a la PC (MSP): Tienes el cable USB puesto. (Normal en mesa)."),
}

# --- INTERFAZ GRÁFICA ---
st.title("🛠️ FPV Diagnostic Tool & Centro de Soluciones")
st.markdown("Analiza la salud de tu dron, errores de armado, telemetría de video DJI O4 y estado térmico.")

# Columnas principales
col_config, col_status = st.columns([1, 3])

with col_config:
    st.subheader("🔌 Conexión USB")
    
    # Checkbox para probar sin hardware
    modo_simulado = st.checkbox("🤖 Modo Simulado (Probar sin dron)", value=False)
    
    # Botón explícito para forzar la re-detección de puertos de Windows/Mac
    if st.button("🔄 Refrescar Puertos COM"):
        st.rerun()
    
    # Detección de puertos reales en tiempo de ejecución
    puertos = [port.device for port in serial.tools.list_ports.comports()]
    
    if modo_simulado:
        puerto_sel = st.selectbox("Puerto COM/USB (Simulado):", ["COM3 (Dron Virtual)"])
    else:
        if puertos:
            puerto_sel = st.selectbox("Selecciona Puerto COM/USB Real:", puertos)
        else:
            puerto_sel = st.selectbox("Selecciona Puerto COM/USB Real:", ["No se detectaron puertos"])
            st.warning("🔎 **Tip de Pavo20:** El chasis estrecho suele impedir que los cables USB-C entren por completo. Empuja firmemente el conector o usa un cable de punta delgada.")
        
        if "streamlit.app" in st.get_option("browser.serverAddress"):
            st.warning("⚠️ Estás en la nube: Recuerda correr esto localmente en tu PC con 'streamlit run app.py' para usar el USB real.")

    # Lógica de conexión con manejo inteligente de excepciones
    if not st.session_state.conectado:
        bot_desactivado = False if modo_simulado else (len(puertos) == 0)
        if st.button("🔌 Conectar Dron", type="primary", disabled=bot_desactivado):
            if modo_simulado:
                st.session_state.conectado = True
                st.success("🤖 Conectado al simulador con éxito.")
                st.rerun()
            else:
                try:
                    # Intento de apertura limpia
                    st.session_state.ser_conn = serial.Serial(puerto_sel, 115200, timeout=0.5)
                    st.session_state.conectado = True
                    st.success("¡Conectado al dron real!")
                    st.rerun()
                except serial.SerialException as e:
                    if "PermissionError" in str(e):
                        st.error("🚫 **Puerto Bloqueado:** Cierra Betaflight Configurator o SpeedyBee antes de conectar aquí.")
                    else:
                        st.error(f"Error de conexión: {e}")
    else:
        if st.button("❌ Desconectar Dron", type="secondary"):
            if st.session_state.ser_conn:
                try:
                    st.session_state.ser_conn.close()
                except:
                    pass
            st.session_state.conectado = False
            st.session_state.ser_conn = None
            st.rerun()

with col_status:
    if not st.session_state.conectado:
        st.info("Por favor, conecta tu dron (o activa el Modo Simulado) y presiona 'Conectar Dron' en el panel izquierdo.")
    else:
        st.success(f"🟢 Sistema en línea {'(MODO SIMULADO)' if modo_simulado else '(DRON REAL)'}")
        
        tab_general, tab_dji, tab_osd, tab_termico = st.tabs([
            "🔍 Diagnóstico de Armado", 
            "📺 Enlace DJI O4 Air Unit", 
            "📊 Formato de OSD", 
            "🔥 Monitor Técnico"
        ])
        
        # --- FUNCIÓN INTERNA PARA EVITAR EL CRASHEO POR REINICIO DE CLI ---
        def liberar_conexion_por_reinicio():
            """Cierra ordenadamente el puerto ya que 'exit' reinicia físicamente la FC"""
            if not modo_simulado and st.session_state.ser_conn:
                try:
                    st.session_state.ser_conn.write(b'exit\n')
                    time.sleep(0.2)
                    st.session_state.ser_conn.close()
                except:
                    pass
                st.session_state.conectado = False
                st.session_state.ser_conn = None
                st.warning("🔄 La placa se está reiniciando para guardar/salir del modo CLI. Conéctala de nuevo en 3 segundos.")
                st.rerun()

        # ----------------------------------------------------------------
        # PESTAÑA 1: DIAGNÓSTICO DE ARMADO (Protocolo Binario MSP)
        # ----------------------------------------------------------------
        with tab_general:
            st.subheader("🚫 ¿Por qué no arranca mi dron?")
            if st.button("🔄 Escanear Banderas de Bloqueo"):
                if modo_simulado:
                    st.write("### 🧠 Estado del bus I2C:")
                    st.success("🟢 Líneas de comunicación de hardware estables (0 errores I2C).")
                    st.write("### 🚫 Causas de bloqueo detectadas:")
                    st.warning(BETAFLIGHT_ARMING_FLAGS[7][1]) 
                    st.warning(BETAFLIGHT_ARMING_FLAGS[1][1]) 
                else:
                    try:
                        # Código Real MSP
                        st.session_state.ser_conn.write(b"$M<\x00\x65\x65")
                        header = st.session_state.ser_conn.read(5)
                        if len(header) == 5 and header[0:3] == b"$M>":
                            payload = st.session_state.ser_conn.read(header[3])
                            st.session_state.ser_conn.read(1)
                            cycle, i2c_errors, sens, mode, armingFlags = struct.unpack("<HHHII", payload[:14])
                            
                            if i2c_errors > 0:
                                st.error(f"❌ Se detectaron {i2c_errors} errores I2C.")
                            else:
                                st.success("🟢 Hardware base saludable (0 errores I2C).")
                            
                            banderas_activas = False
                            for bit, (nombre, desc) in BETAFLIGHT_ARMING_FLAGS.items():
                                if armingFlags & (1 << bit) and nombre != "MSP":
                                    st.warning(desc)
                                    banderas_activas = True
                            
                            if not banderas_activas:
                                st.success("🚀 ¡Todo libre! No tienes banderas de bloqueo críticas reteniendo el armado.")
                        else:
                            st.error("Sin respuesta del hardware. Si usaste otra pestaña antes, es posible que la placa esté atrapada en modo CLI.")
                    except Exception as e:
                        st.error(f"Error de lectura serial MSP: {e}")

        # ----------------------------------------------------------------
        # PESTAÑA 2: ENLACE DJI O4 AIR UNIT (Comandos CLI)
        # ----------------------------------------------------------------
        with tab_dji:
            st.subheader("🎥 Diagnóstico de Transmisión Digital DJI O4")
            if st.button("🔍 Comprobar Conexión de Video"):
                if modo_simulado:
                    st.error("❌ Falla de comunicación física (Ready: NO): La configuración existe pero la unidad DJI no responde.")
                    st.markdown("""
                    **Soluciones rápidas sugeridas:**
                    1. **Conecta la LiPo:** La O4 Air Unit no enciende únicamente con el voltaje del USB de la PC. Requieres batería.
                    2. **Cables TX/RX Invertidos:** El pin TX de la DJI debe ir cruzado al RX de la placa, y el RX de la DJI al TX.
                    """)
                else:
                    try:
                        # Forzar entrada limpia a CLI texto plano
                        st.session_state.ser_conn.write(b'#\n')
                        time.sleep(0.1)
                        st.session_state.ser_conn.read_all() # Limpiar buffer residual
                        
                        st.session_state.ser_conn.write(b'vtx\n')
                        time.sleep(0.2)
                        log_vtx = st.session_state.ser_conn.read_all().decode('utf-8', errors='ignore')
                        
                        if "ready: yes" in log_vtx.lower():
                            st.success("🟢 **DJI O4 Detectada:** Conexión serial MSP con la Air Unit operativa.")
                        else:
                            st.error("❌ DJI O4 no responde. Revisa alimentación (LiPo puesta) y cableado UART.")
                        
                        liberar_conexion_por_reinicio()
                    except Exception as e:
                        st.error(f"Error en comunicación CLI: {e}")

        # ----------------------------------------------------------------
        # PESTAÑA 3: DIAGNÓSTICO DE FORMATO OSD (Comandos CLI)
        # ----------------------------------------------------------------
        with tab_osd:
            st.subheader("📊 Ajuste de Caracteres en Pantalla (OSD)")
            if st.button("🔧 Verificar Formato de Pantalla"):
                if modo_simulado:
                    st.metric(label="Formato de Video Configurado", value="PAL")
                    st.error("❌ **Error de Formato:** Tienes configurado un sistema analógico (PAL/NTSC).")
                    st.info("🛠️ **Solución para corregirlo:** Copia y pega estos comandos en la pestaña CLI de Betaflight para pasarlo a HD:")
                    st.code("set osd_video_system = HD\nsave", language="bash")
                else:
                    try:
                        st.session_state.ser_conn.write(b'#\n')
                        time.sleep(0.1)
                        st.session_state.ser_conn.read_all()
                        
                        st.session_state.ser_conn.write(b'get osd_video_system\n')
                        time.sleep(0.2)
                        raw_osd = st.session_state.ser_conn.read_all().decode('utf-8', errors='ignore')
                        
                        if "HD" in raw_osd:
                            st.success("🟢 **Formato Correcto:** Configuración en modo HD ideal para DJI.")
                        else:
                            st.error("❌ Formato analógico detectado en la configuración.")
                            st.code("set osd_video_system = HD\nsave", language="bash")
                        
                        liberar_conexion_por_reinicio()
                    except Exception as e:
                        st.error(f"Error al verificar OSD: {e}")

        # ----------------------------------------------------------------
        # PESTAÑA 4: MONITOR TÉRMICO (Comandos CLI)
        # ----------------------------------------------------------------
        with tab_termico:
            st.subheader("🌡️ Temperatura en Banco de Trabajo")
            if st.button("🌡️ Leer Sensores Térmicos"):
                if modo_simulado:
                    st.error("🚨 ¡SOBRECALENTAMIENTO CRÍTICO!: 78°C.")
                    st.markdown("""
                    ** Solución Obligatoria:**
                    * **¡Desconecta la LiPo de inmediato!** Deja enfriar los componentes.
                    * Coloca un **ventilador de mesa** apuntando directo al dron mientras trabajas. La DJI O4 genera demasiado calor estática.
                    """)
                else:
                    try:
                        st.session_state.ser_conn.write(b'#\n')
                        time.sleep(0.1)
                        st.session_state.ser_conn.read_all()
                        
                        st.session_state.ser_conn.write(b'status\n')
                        time.sleep(0.2)
                        raw_status = st.session_state.ser_conn.read_all().decode('utf-8', errors='ignore')
                        
                        match = re.search(r'Temp=(\d+)', raw_status)
                        if match:
                            temp = int(match.group(1))
                            if temp > 70:
                                st.error(f"🚨 Alerta Térmica Crítica: {temp}°C. ¡Usa refrigeración externa forzada!")
                            else:
                                st.success(f"🟢 Temperatura interna de la FC: {temp}°C")
                        else:
                            st.info("Lectura enviada, pero la placa no devolvió un sensor de temperatura interpretable.")
                        
                        liberar_conexion_por_reinicio()
                    except Exception as e:
                        st.error(f"Error al leer estado térmico: {e}")
