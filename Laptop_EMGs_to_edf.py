import serial
import time
import numpy as np
from pyedflib import EdfWriter

#This first part has to be setup 
#------------------------------------------------------------------------------
PORT = "COM3"       #Change 'COM' to whichever correct one
BAUD = 115200
SAMPLE_RATE = 1000  #measured in Hz (must match Arduino's sampleRate)
DURATION_SEC = 10   #Duration of EMG edf (measured in s)
EDF_FILENAME = "emg_raw.edf"
# -----------------------------------------------------------------------------

num_samples = SAMPLE_RATE * DURATION_SEC #gives amount of samples edf should have for our desired time interval and frequency
raw_samples = []

# Open serial
ser = serial.Serial(PORT, BAUD)
time.sleep(2)  #must match Arduino delay()

print("Recording", DURATION_SEC, "seconds of EMG...")

## Step1: Fill 'raw_samples' with samples taken from Arduino
while len(raw_samples) < num_samples:
    try:
        line = ser.readline().decode().strip() #interprets Arduino serial info in way Python can understand. Gives an str
        value = int(line) 
        raw_samples.append(value) #appends a single sample to 'raw_samples' list
    except:
        pass  #Ignore any bad lines

ser.close() 


## Step2: Create an edf file from raw_samples using EdfWiter library
#Convert list to numpy array because that's what EdfWriter library works with
raw_samples = np.array(raw_samples, dtype=float)

writer = EdfWriter(
    EDF_FILENAME,
    n_channels=1,
    file_type=EdfWriter.EDFLIB_FILETYPE_EDFPLUS
)

# Required EDF header fields
channel_info = {
    'label': 'EMG',
    'dimension': 'uV',
    'sample_frequency': SAMPLE_RATE,
    'physical_min': 0,
    'physical_max': 1023,
    'digital_min': 0,
    'digital_max': 1023,
    'transducer': 'EMG sensor',
    'prefilter': 'None'
}

writer.setSignalHeader(0, channel_info)

# Write data
writer.writePhysicalSamples(raw_samples)
writer.close()

print("Saved:", EDF_FILENAME)
print("Samples collected:", len(raw_samples))



