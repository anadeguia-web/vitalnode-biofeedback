#include <Wire.h>
#include "rgb_lcd.h"

rgb_lcd lcd;

// --- PINES ---
#define PPG_PIN A0
#define FSR_PIN A1
#define LED_PIN 8

// --- UMBRAL Y DETECCION DE PULSO ---
int threshold     = 520;
bool beat_detected = false;
unsigned long last_beat_time = 0;
float bpm_actual  = 0;

// --- FASES DE RESPIRACION ---
unsigned long phase_start    = 0;
int phase                    = 0;
int duration_breath          = 4000;
int duration_pause           = 1000;
String nombreFase            = "START     ";

// --- REFRESCO INTELIGENTE DE LCD ---
String fase_mostrada = "";
int    bpm_mostrado  = -1;

// --- ENVIO CONTINUO AL SERIAL ---
// Mandamos datos cada INTERVALO_SERIAL ms aunque no haya latido nuevo.
// Asi Python siempre tiene datos frescos del sensor PPG y FSR.
unsigned long ultimo_envio_serial = 0;
const unsigned long INTERVALO_SERIAL = 1000; // 50ms = 20 envios por segundo

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);

  lcd.begin(16, 2);
  lcd.setRGB(0, 150, 255);
  lcd.print("  Serenity Box  ");
  delay(2000);
  lcd.clear();

  phase_start = millis();
}

void loop() {
  unsigned long current_time = millis();

  // --- 1. CONTROL LED Y FASES DE RESPIRACION ---
  unsigned long elapsed      = current_time - phase_start;
  int current_target         = (phase == 0 || phase == 2) ? duration_breath : duration_pause;

  if (elapsed > current_target) {
    phase       = (phase + 1) % 4;
    phase_start = current_time;

    if      (phase == 0) nombreFase = "INHALE    ";
    else if (phase == 1) nombreFase = "HOLD      ";
    else if (phase == 2) nombreFase = "EXHALE    ";
    else if (phase == 3) nombreFase = "HOLD      ";
  }

  // Brillo del LED suave
  float progress = (float)(current_time - phase_start) / current_target;
  int brightness = 0;
  if      (phase == 0) brightness = (int)(progress * 255);
  else if (phase == 1) brightness = 255;
  else if (phase == 2) brightness = (int)((1.0 - progress) * 255);
  else if (phase == 3) brightness = 0;
  analogWrite(LED_PIN, brightness);

  // --- 2. DETECCION DE LATIDO (solo actualiza bpm_actual) ---
  int ppg = analogRead(PPG_PIN);

  if (ppg > threshold && !beat_detected) {
    unsigned long duration = current_time - last_beat_time;
    if (duration > 300 && duration < 1500) {
      // Latido valido: actualizamos BPM
      bpm_actual = 60000.0 / duration;
    }
    last_beat_time = current_time;
    beat_detected  = true;
  }
  if (ppg < (threshold - 10)) {
    beat_detected = false;
  }

  // --- 3. ENVIO CONTINUO AL SERIAL ---
  // Se ejecuta cada INTERVALO_SERIAL ms INDEPENDIENTEMENTE de si hubo latido.
  // Formato: bpm,fsr,fase,ppg_raw
  // El campo ppg_raw permite a Python ver la senal cruda del sensor
  // y detectar si el sensor esta bien colocado.
  if (current_time - ultimo_envio_serial >= INTERVALO_SERIAL) {
    int rawFSR = analogRead(FSR_PIN);

    String faseSerial = nombreFase;
    faseSerial.trim();

    Serial.print(bpm_actual, 1);   // BPM con 1 decimal
    Serial.print(",");
    Serial.print(rawFSR);          // Valor bruto del sensor de respiracion
    Serial.print(",");
    Serial.println(faseSerial);      // Fase actual de respiracion
    //Serial.print(",");
    //Serial.println(ppg);           // Valor bruto del PPG (util para depurar)

    ultimo_envio_serial = current_time;
  }

  // --- 4. REFRESCO INTELIGENTE DE LCD ---
  if (nombreFase != fase_mostrada) {
    lcd.setCursor(0, 1);
    lcd.print("Phase: ");
    lcd.print(nombreFase);
    fase_mostrada = nombreFase;
  }

  if ((int)bpm_actual != bpm_mostrado) {
    lcd.setCursor(0, 0);
    lcd.print("BPM: ");
    lcd.print((int)bpm_actual);
    lcd.print("    ");
    bpm_mostrado = (int)bpm_actual;
  }

  delay(20);
}
