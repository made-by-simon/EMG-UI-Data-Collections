// Make Arduino read raw EMGs from Gravity Analog EMG module and send it live
// to laptop through a serial


// Reads EMG analog data from pin A0 and sends raw samples to the laptop.
#define SENSOR_PIN A0
const int sampleRate = 1000;              // measured in Hz
unsigned long nextSampleTime = 0;         // measured in μs

void setup() {
  Serial.begin(115200);
  delay(2000); // Allow time for connection (measured in ms)
  nextSampleTime = micros();
}

void loop() {
  unsigned long now = micros();

  // Wait until it's time for the next sample
  if (now >= nextSampleTime) {

    int rawValue = analogRead(SENSOR_PIN);   // 0–1023 EMG voltage reading
    Serial.println(rawValue);                // Send sample to laptop

    // Schedule next sample
    nextSampleTime += 1000000 / sampleRate;  // microseconds per sample
  }
}