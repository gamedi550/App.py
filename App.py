import streamlit as st
import serial
import re
import time

# ==========================================
# 1. MÓDULO OSD: DIAGNÓSTICO Y SOLUCIONES
# ==========================================
def analizar_osd_y_video(ser):
    """Verifica la configuración del OSD para sistemas digitales como DJI O4"""
    try:
        ser.write(b'#')
        time.sleep(0.1)
        ser.read_all()
        
        # Pedimos el sistema de video configurado
        ser.write(b'get osd_video_system\n')
        time.sleep(0.15)
        res_osd = ser.read_all().decode('utf-8', errors='ignore')
        
        ser.write(b'exit\n')
        return res_osd
    except Exception as e:
        return f"Error: {e}"

# ==========================================
# 2. MÓDULO TÉRMICO: DETECCIÓN DE TEMPERATURA
# ==========================================
def analizar_temperaturas(ser):
    """Lee el estado del procesador (MCU) para detectar sobrecalentamiento"""
    try:
        ser.write(b'#')
        time.sleep(0.1)
        ser.read_all()
        
        # El comando 'status' nos da la temperatura de la FC si el hardware lo soporta
        ser.write(b'status\n')
        time.sleep(0.2)
        res_status = ser.read_all().decode('utf-8', errors='ignore')
        
        ser.write(b'exit\n')
        return res_status
    except Exception as e:
        return f"Error: {e}"


# --- INTERFAZ EN STREAMLIT (Añadir al panel principal si st.session_state.conectado) ---
if st.session_state.conectado and st.session_state.ser_conn:
    ser_actual = st.session_state.ser_conn
    
    st.markdown("---")
    tab1, tab2 = st.tabs(["📺 Diagnóstico OSD / Pantalla", "🔥 Monitor de Temperatura Crítica"])
    
    # ----------------------------------------------------------------
    # PESTAÑA 1: DIAGNÓSTICO OSD
    # ----------------------------------------------------------------
    with tab1:
        st.subheader("🔍 Verificación del Canvas OSD (DJI O4 / Digital)")
        st.write("Si tus gafas DJI no muestran los elementos del OSD (voltaje, modos, RSSI), suele ser por un error de formato en Betaflight.")
        
        if st.button("🔧 Escanear Configuración OSD"):
            with st.spinner("Analizando parámetros de video..."):
                raw_osd = analizar_osd_y_video(ser_actual)
                
                # Buscar el valor de osd_video_system en la respuesta
                # Ejemplo de salida: osd_video_system = HD
                match = re.search(r'osd_video_system\s*=\s*(\w+)', raw_osd)
                
                if match:
                    sistema_actual = match.group(1).upper()
                    st.metric(label="Formato de Video Actual", value=sistema_actual)
                    
                    if sistema_actual in ["PAL", "NTSC"]:
                        st.error(f"❌ **Error Detectado:** Tu OSD está configurado en **{sistema_actual}** (Analógico).")
                        st.markdown("""
                        **Causa:** La DJI O4 Air Unit es un sistema de Alta Definición (HD). Si Betaflight le envía una señal PAL/NTSC, los elementos gráficos se cortarán, se verán gigantes o simplemente no aparecerán en los goggles.
                        """)
                        
                        # Solución interactiva automatizada
                        st.info("💡 **Solución sugerida:** Cambiar el formato a **HD** para compatibilidad con DJI O4.")
                        st.code("set osd_video_system = HD\nsave", language="bash")
                        
                    elif sistema_actual in ["HD", "AUTO"]:
                        st.success(f"🟢 **OSD Correcto ({sistema_actual}):** El formato es compatible con sistemas digitales HD.")
                        st.write("Si sigues sin ver telemetría, asegúrate de haber activado los elementos que deseas ver en la pestaña 'OSD' de Betaflight Configurator.")
                else:
                    st.warning("⚠️ No se pudo determinar el formato automático del OSD. Revisa los datos crudos abajo.")
                
                with st.expander("Ver respuesta CLI"):
                    st.code(raw_osd)

    # ----------------------------------------------------------------
    # PESTAÑA 2: MONITOR DE TEMPERATURA
    # ----------------------------------------------------------------
    with tab2:
        st.subheader("🌡️ Alertas de Estrés Térmico (FC y Componentes)")
        st.write("Ideal para pruebas prolongadas en el banco de trabajo donde no hay flujo de viento.")
        
        if st.button("🌡️ Medir Temperatura de la Placa"):
            with st.spinner("Leyendo sensores térmicos integrados..."):
                raw_status = analizar_temperaturas(ser_actual)
                
                # Expresión regular para buscar la temperatura en el string de 'status'
                # Ej: "Temp=43degC" o "Temp=51C"
                match_temp = re.search(r'Temp=(\d+)(?:degC|C)', raw_status, re.IGNORECASE)
                
                if match_temp:
                    temp_mcu = int(match_temp.group(1))
                    
                    # Definir estados por colores según temperatura
                    if temp_mcu < 60:
                        st.success(f"🟢 **Temperatura Normal:** {temp_mcu}°C. El procesador central está operando de forma segura.")
                    elif 60 <= temp_mcu < 75:
                        st.warning(f"⚠️ **Temperatura Elevada:** {temp_mcu}°C. La placa se está calentando.")
                        st.markdown("""
                        **Solución inmediata:** * Evita dejar la batería conectada mucho tiempo en la mesa de taller si no estás haciendo pruebas críticas.
                        * Si tienes la DJI O4 encendida al mismo tiempo, el calor de la Air Unit se transfiere por conducción a través del frame hacia la FC.
                        """)
                    else:
                        st.error(f"🚨 **¡ALERTA DE SOBRECALENTAMIENTO!: {temp_mcu}°C**")
                        st.markdown(f"""
                        **¡Peligro de daño físico o congelamiento del procesador (Hardware Freeze)!**
                        
                        **🛠️ Solución Obligatoria:**
                        1. **¡Desconecta la LiPo de inmediato!** Deja enfriar el dron.
                        2. Coloca un **ventilador de mesa** apuntando directo al dron mientras trabajes con él conectado en la computadora.
                        3. Verifica si hay un corto circuito menor o si algún chip regulador de voltaje de la FC (ej. el de 9V o 5V) está hirviendo al tacto.
                        4. **Para la DJI O4:** Asegúrate de activar el **'Pit Mode'** desde tu radio para que transmita a los mínimos milivatios posibles (25mW) mientras configuras en la mesa.
                        """)
                else:
                    st.info("ℹ️ Tu controladora de vuelo no cuenta con un sensor de temperatura interno reportable o el firmware actual tiene desactivado el ADC de temperatura.")
                
                with st.expander("Ver salida detallada del sistema (CLI status)"):
                    st.code(raw_status)
