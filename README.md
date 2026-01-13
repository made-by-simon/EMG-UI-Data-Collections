# EMG Data Collection & EDF Converter

A Python application for collecting EMG data from Arduino and saving it in EDF format with real-time visualization.

## Requirements

- Python 3.x
- Arduino with Gravity Analog EMG sensor module

## Installation

Install required packages:
```bash
pip install mne PyQt5 pyqtgraph pyEDFlib numpy
```

## Arduino Setup

1. Upload this code to your Arduino:

```cpp
#define SENSOR_PIN A0
const int sampleRate = 1000;
unsigned long nextSampleTime = 0;

void setup() {
  Serial.begin(115200);
  delay(2000);
  nextSampleTime = micros();
}

void loop() {
  unsigned long now = micros();
  if (now >= nextSampleTime) {
    int rawValue = analogRead(SENSOR_PIN);
    Serial.println(rawValue);
    nextSampleTime += 1000000 / sampleRate;
  }
}
```

2. Note the COM port (e.g., COM3) that Arduino is connected to

## Usage

1. Update the COM port in the application code if needed
2. Run the application
3. Enter the subject ID
4. Press Start to begin data collection

Data will be saved as EDF files with timestamps.
