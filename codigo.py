import serial
import time
import csv
import cv2
import numpy as np
from datetime import datetime
from gpiozero import Button, PWMOutputDevice
import tensorflow.lite as tflite
import google.generativeai as genai

# ==========================================
# 1. CONFIGURACION DE LA IA DE POSTURA
# ==========================================
MODEL_PATH  = "model.tflite"
LABELS_PATH = "labels.txt"

with open(LABELS_PATH, 'r') as f:
    labels = [line.strip() for line in f.readlines()]

interpreter = tflite.Interpreter(model_path=MODEL_PATH)
interpreter.allocate_tensors()
input_details  = interpreter.get_input_details()
output_details = interpreter.get_output_details()

def clasificar_postura(frame):
    """Devuelve la etiqueta, si es mala (True/False) y el % de curvatura."""
    img = cv2.resize(frame, (224, 224))
    img = np.expand_dims(img, axis=0)
    img = (np.float32(img) - 127.5) / 127.5
    interpreter.set_tensor(input_details[0]['index'], img)
    interpreter.invoke()

    output_data = interpreter.get_tensor(output_details[0]['index'])

    # El % de curvatura es la probabilidad de la clase 1 (Encorvada/Slouched)
    pct_curvatura = output_data[0][1] * 100

    indice_prediccion = np.argmax(output_data[0])
    etiqueta = labels[indice_prediccion]

    # Comprobamos si es mala postura (incluyendo terminos en ingles)
    etiqueta_min = etiqueta.lower()
    es_mala = any(word in etiqueta_min for word in ["mala", "bad", "slouched", "curved"])

    return etiqueta, es_mala, pct_curvatura

# ==========================================
# 2. CONFIGURACION DE HARDWARE
# ==========================================
btn_verde = Button(22, pull_up=True, bounce_time=0.1)
btn_rojo  = Button(23, pull_up=True, bounce_time=0.1)
altavoz   = PWMOutputDevice(12, initial_value=0)

def reproducir_tono(frecuencia, duracion):
    if frecuencia > 0:
        altavoz.frequency = frecuencia
        altavoz.value = 0.05
        time.sleep(duracion)
        altavoz.value = 0

def pitidos_inicio():
    for _ in range(3):
        reproducir_tono(432, 0.4)
        time.sleep(0.6)
    reproducir_tono(432, 0.8)

try:
    ser = serial.Serial('/dev/ttyACM0', 115200, timeout=0.1)
    ser.flushInput()
    time.sleep(2)
    print("Conexion con Arduino establecida.")
except Exception as e:
    print(f"Error con Arduino: {e}")
    exit()

camara = cv2.VideoCapture(0)
if not camara.isOpened():
    print("Error: no se puede abrir la camara.")
    exit()

# ==========================================
# 3. CONFIGURACION DE GEMINI
# ==========================================
GEMINI_API_KEY = "ADD_YOUR_KEY"
genai.configure(api_key=GEMINI_API_KEY)
modelo_gemini = genai.GenerativeModel('gemini-2.5-flash')  # Una sola instancia, aqui

def generar_resumen_medico(lista_bpm, lista_fsr, malas_posturas, total_muestras, duracion_seg):
    if not lista_bpm:
        print("Sin datos suficientes para el informe.")
        return

    bpm_media = round(sum(lista_bpm) / len(lista_bpm), 1)
    bpm_min   = round(min(lista_bpm), 1)
    bpm_max   = round(max(lista_bpm), 1)
    bpm_rango = round(bpm_max - bpm_min, 1)
    bpm_diffs = [abs(lista_bpm[i] - lista_bpm[i-1]) for i in range(1, len(lista_bpm))]
    hrv_proxy = round(sum(bpm_diffs) / len(bpm_diffs), 2) if bpm_diffs else 0.0

    fsr_media        = round(sum(lista_fsr) / len(lista_fsr), 1) if lista_fsr else 0
    pct_mala_postura = round((malas_posturas / total_muestras) * 100, 1) if total_muestras > 0 else 0

    prompt = f"""Eres un asistente medico especializado en biofeedback.
Redacta un informe clinico breve en INGLES.
Solo texto plano, sin markdown.
DATOS:
- Duration: {duracion_seg}s
- Average BPM: {bpm_media}
- HRV Proxy: {hrv_proxy}
- Bad Posture Time: {pct_mala_postura}%
"""

    print("\nGenerando informe medico con Gemini...")
    try:
        respuesta = modelo_gemini.generate_content(prompt)
        texto_informe = respuesta.text
    except Exception as e:
        texto_informe = f"Error al conectar con Gemini: {e}"

    contenido = f"POSTURE & BIOFEEDBACK REPORT\n{'-'*30}\n{texto_informe}"
    nombre_informe = f"REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(nombre_informe, "w", encoding="utf-8") as f:
        f.write(contenido)
    print("\n" + contenido)

# ==========================================
# 4. VARIABLES DE SESION
# ==========================================
sesion_activa        = False
guardando_datos      = False
tiempo_inicio_sesion = 0.0
DURACION_MAXIMA      = 60

lista_bpm = []
lista_fsr = []
ultimo_guardado = 0.0
FRECUENCIA_MUESTREO = 0.05

contador_malas_posturas = 0
total_muestras_postura  = 0
INTERVALO_POSTURA = 0.5
ultimo_analisis_pos = 0.0

postura_actual = "Unknown"
pct_actual = 0.0
nombre_csv = ""

informe_generado = False  # FIX: flag para evitar llamadas multiples a Gemini

print("Sistema listo (432Hz Mode). Pulsa VERDE para iniciar.")

try:
    while True:
        ret, frame = camara.read()

        if btn_verde.is_pressed and not sesion_activa:
            print("\nIniciando sesion zen...")
            pitidos_inicio()
            sesion_activa        = True
            guardando_datos      = True
            informe_generado     = False  # FIX: reset del flag al iniciar sesion nueva
            tiempo_inicio_sesion = time.time()
            ultimo_guardado      = tiempo_inicio_sesion
            ultimo_analisis_pos  = tiempo_inicio_sesion

            lista_bpm.clear()
            lista_fsr.clear()
            contador_malas_posturas = 0
            total_muestras_postura  = 0

            nombre_csv = f"SESSION_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            with open(nombre_csv, 'w', newline='') as f:
                csv.writer(f).writerow(["Timestamp", "BPM", "HRV_Index", "Respiration_Raw", "Posture_State", "Device_Status"])
            print(f"{'Time(ms)':>10} | {'BPM':>6} | {'Curvature':>12}")

        if btn_rojo.is_pressed and sesion_activa:
            guardando_datos = not guardando_datos
            reproducir_tono(432, 0.3)
            print(f"\n--- {'RESUMED' if guardando_datos else 'PAUSED'} ---\n")
            time.sleep(0.4)

        if sesion_activa:
            ahora   = time.time()
            elapsed = ahora - tiempo_inicio_sesion
            ms_trans = int(elapsed * 1000)

            # FIX: condicion con flag para llamar a Gemini una sola vez
            if elapsed >= DURACION_MAXIMA and not informe_generado:
                sesion_activa    = False
                informe_generado = True
                generar_resumen_medico(
                    lista_bpm, lista_fsr,
                    contador_malas_posturas,
                    total_muestras_postura,
                    round(elapsed)
                )
                continue

            # Analisis de postura con % de curvatura
            if ret and (ahora - ultimo_analisis_pos >= INTERVALO_POSTURA):
                postura_actual, postura_es_mala, pct_actual = clasificar_postura(frame)
                total_muestras_postura += 1
                if postura_es_mala:
                    contador_malas_posturas += 1
                ultimo_analisis_pos = ahora

            # Lectura Serial
            while ser.in_waiting > 0:
                try:
                    linea = ser.readline().decode('utf-8', errors='ignore').strip()
                    if not linea:
                        continue
                    datos = linea.split(',')
                    if len(datos) < 2:
                        continue

                    bpm_val = float(datos[0])
                    fsr_val = float(datos[1])

                    if guardando_datos and (ahora - ultimo_guardado >= FRECUENCIA_MUESTREO):
                        with open(nombre_csv, 'a', newline='') as f:
                            csv.writer(f).writerow([ms_trans, bpm_val, 45.0, fsr_val, postura_actual, "OK"])
                        lista_bpm.append(bpm_val)
                        lista_fsr.append(fsr_val)
                        ultimo_guardado = ahora
                        print(f"{ms_trans:>10} | {bpm_val:>6.1f} | {pct_actual:>10.1f}% ({postura_actual})")
                except Exception:
                    continue

except KeyboardInterrupt:
    print("\nDetenido.")
finally:
    altavoz.value = 0
    ser.close()
    camara.release()

