# VitalNode – AI Biofeedback System

VitalNode is a portable biofeedback prototype designed for respiratory rehabilitation, stress management, and posture correction.

The system combines:

* Arduino Uno physiological acquisition
* Raspberry Pi 5 processing
* TensorFlow Lite posture classification
* Real-time serial communication
* Structured CSV medical logging
* Gemini AI automated report generation

## Hardware Components

* PPG Ear-clip sensor
* FSR respiration sensor
* Raspberry Pi 5
* Arduino Uno WiFi
* USB camera
* LCD display
* PWM LED guide
* Speaker and control buttons

## Software Stack

* Python 3
* OpenCV
* TensorFlow Lite
* NumPy
* PySerial
* gpiozero
* Google Generative AI SDK

## Repository Structure

* `/arduino` → Arduino firmware
* `/raspberry_pi` → Raspberry Pi processing scripts
* `/datasets` → Example CSV session data
* `/reports` → Final report and Gemini-generated reports
* `/images` → System diagrams and dashboards
* `/model` → TensorFlow Lite posture model

## Authors

Ana Díaz
Inés Carrilero
