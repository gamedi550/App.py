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

# Validar si el usuario está corriendo esto en la nube por error
es_nube = "streamlit.app" in st.get_option("browser.serverAddress")

# Columnas principales
col_config, col_status = st.columns([1, 3])

with col_config:
    st.subheader("🔌 Conexión USB")
    
    if es_nube:
        st.error("🚨 **¡ESTÁS EN LA NUBE!** Esta página web no puede ver los puertos USB de tu computadora. Sigue las instrucciones de abajo para correrlo en tu PC.")
    
    # Checkbox para probar sin hardware
    modo_simulado = st.checkbox("🤖 Modo Simulado (Probar sin dron)", value=False)
    
    # Botón para
