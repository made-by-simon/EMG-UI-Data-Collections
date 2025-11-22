import sys
import time
import csv
import serial
from PyQt5 import QtCore, QtWidgets
import pyqtgraph as pg
import mne
import pyedflib
import numpy as np
from scipy.signal import butter, lfilter
from PyQt5.QtGui import QFont

#
# Configurations
#
EDF_file = "EMG_data_edf.edf"
serial_port = "COM3"  # Change as per your system
baud_rate = 96000 # Number of signal events per second
sampling_rate = 1000  # Number of samples per second
activation_threshold = 0.1  # Decides when a muscle is considered active

#
# Class object of the main window
#
class EMGMonitor(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        # Setting the window title and size
        self.setWindowTitle("EMG Monitor")
        self.setStyleSheet("background-color: black; color: white;")
        self.setGeometry(100, 100, 800, 800)

        # Data buffers
        self.raw_data = []
        self.filtered_data = []
        self.time_stamps = []
        self.start_time = time.time()

        # Serial setup
        self.serial = serial.Serial(serial_port, baud_rate)
        self.serial.timeout = 0.01 # If no data is received in 10ms, move on

        # EDF setup
        self.edf_filename = "emg_data.edf"
        self.edf_writer = pyedflib.EdfWriter(self.edf_filename, 1, file_type = pyedflib.FILETYPE_EDFPLUS)

        channel_info = {
        'label': 'EMG',
        'dimension': 'uV',
        'sample_frequency': sampling_rate,
        'physical_min': -5000,
        'physical_max': 5000,
        'digital_min': -32768,
        'digital_max': 32767,
        'transducer': 'EMG Sensor',
        'prefilter': 'Bandpass 20-450Hz'
        }

        self.edf_writer.setSignalHeaders([channel_info])
        self.edf_buffer = []

        # Title
        self.title = QtWidgets.QLabel("Real-Time EMG Monitor", font = QFont('Arial', 24))
        self.title.setAlignment(QtCore.Qt.AlignBottom)
        self.creators = QtWidgets.QLabel("for Alberta Bionix", font = QFont('Arial', 12))
        self.creators.setAlignment(QtCore.Qt.AlignBottom | QtCore.Qt.AlignLeft)

        # Plot electrode 1
        self.plot_widget_e1 = pg.PlotWidget()
        self.plot_widget_e1.setLabel('left', 'Amplitude', color='blue', size='20pt')
        self.plot_widget_e1.setLabel('bottom', 'Time (s)\n', color='blue', size='20pt')
        self.plot_widget_e1.hideAxis('left')
        self.plot_widget_e1.hideAxis('bottom')
        self.hLine_e1 = pg.InfiniteLine(angle = 0, movable = False, pen = pg.mkPen('w', width = 2))
        self.plot_widget_e1.addItem(self.hLine_e1)
        self.raw_curve_e1 = self.plot_widget_e1.plot(pen = 'y', color = 'red')
        self.filtered_curve_e1 = self.plot_widget_e1.plot(pen = 'c', color = 'blue')

        # Plot electrode 2
        self.plot_widget_e2 = pg.PlotWidget()
        self.plot_widget_e2.setLabel('left', 'Amplitude', color = 'blue', size = '20pt')
        self.plot_widget_e2.setLabel('bottom', 'Time (s)', color = 'blue', size = '20pt')
        self.plot_widget_e2.hideAxis('left')
        self.plot_widget_e2.hideAxis('bottom')
        self.hLine_e2 = pg.InfiniteLine(angle = 0, movable = False, pen = pg.mkPen('w', width = 2))
        self.plot_widget_e2.addItem(self.hLine_e2)
        self.raw_curve_e2 = self.plot_widget_e2.plot(pen = 'y', color = 'red')
        self.filtered_curve_e2 = self.plot_widget_e2.plot(pen = 'c', color = 'blue')

        # Buttons
        self.start_button = QtWidgets.QPushButton("Start")
        self.stop_button = QtWidgets.QPushButton("Stop")
        self.save_button = QtWidgets.QPushButton("Save Settings")
        self.start_button.clicked.connect(self.start_recording)
        self.stop_button.clicked.connect(self.stop_recording)
        self.save_button.clicked.connect(self.save_changes)

        # Serial port edit
        self.serial_port = QtWidgets.QLineEdit(f"{serial_port}", font = QFont('Arial', 12))
        serial_layout = QtWidgets.QHBoxLayout()
        serial_title = QtWidgets.QLabel("Serial Port:")
        serial_title.setFont(QFont('Arial', 12))
        serial_layout.addWidget(serial_title)
        serial_layout.addWidget(self.serial_port)

        # Baud rate edit
        self.baud_rate = QtWidgets.QLineEdit(f"{baud_rate}", font = QFont('Arial', 12))
        baud_layout = QtWidgets.QHBoxLayout()
        baud_title = QtWidgets.QLabel("Baud Rate:")
        baud_title.setFont(QFont('Arial', 12))
        baud_layout.addWidget(baud_title)
        baud_layout.addWidget(self.baud_rate)

        # Sampling rate edit
        self.sampling_rate = QtWidgets.QLineEdit(f"{sampling_rate}", font = QFont('Arial', 12))
        sampling_layout = QtWidgets.QHBoxLayout()
        sampling_title = QtWidgets.QLabel("Sampling Rate:")
        sampling_title.setFont(QFont('Arial', 12))
        sampling_layout.addWidget(sampling_title)
        sampling_layout.addWidget(self.sampling_rate)

        # Timer
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_data)

        # Main layout
        title_layout = QtWidgets.QHBoxLayout()
        title_layout.addWidget(self.title)
        title_layout.addWidget(self.creators)
        title_layout.addWidget(self.timer) 
        
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addLayout(title_layout)
        main_layout.addWidget(self.plot_widget_e1)  
        main_layout.addWidget(self.plot_widget_e2) 
        main_layout.addWidget(self.start_button)
        main_layout.addWidget(self.stop_button)
        main_layout.addLayout(serial_layout)
        main_layout.addLayout(baud_layout)
        main_layout.addLayout(sampling_layout)
        main_layout.addWidget(self.save_button)

        container = QtWidgets.QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # Add design elements
        self.design_elements()

    def start_recording(self):
        self.timer.start(1)  # Update every 10 ms   
    
    def stop_recording(self):
        self.timer.stop()
        self.edf_writer.close()
        self.serial.close()

    def save_changes(self):
        global serial_port, baud_rate, sampling_rate
        serial_port = self.serial_port.text()
        baud_rate = int(self.baud_rate.text())
        sampling_rate = int(self.sampling_rate.text())
        self.serial.close()
        self.serial = serial.Serial(serial_port, baud_rate)

    def update_data(self):
        try:
            line = self.serial.readline().decode('utf-8').strip()
            emg_value = float(line)
        except:
            return

        t = time.time() - self.start_time
        self.time_stamps.append(t)
        self.raw_data.append(emg_value)

        filtered = bandpass_filter(np.array(self.raw_data))[-1]
        self.filtered_data.append(filtered)

        activation = 1 if abs(filtered) > activation_threshold else 0

        # Save to EDF
        self.edf_buffer.append(filtered)

        if len(self.edf_buffer) >= sampling_rate:
            self.edf_writer.writeSamples([np.array(self.edf_buffer)])
            self.edf_buffer = []

        # Plot update
        self.raw_curve.setData(self.time_stamps, self.raw_data)
        self.filtered_curve.setData(self.time_stamps, self.filtered_data)
    
    def design_elements(self):
        self.plot_widget_e1.setBackground('black')
        self.start_button.setStyleSheet("background-color: green; color: white; font-size: 16px;")
        self.stop_button.setStyleSheet("background-color: red; color: white; font-size: 16px;")
        self.raw_curve_e1.setPen(pg.mkPen(color='blue', width=2))
        self.filtered_curve_e1.setPen(pg.mkPen(color='cyan', width=2))
        self.raw_curve_e2.setPen(pg.mkPen(color='blue', width=2))
        self.filtered_curve_e2.setPen(pg.mkPen(color='cyan', width=2))
        self.plot_widget_e1.setStyleSheet(
            """
            border: 2px solid pink;
            background-color: black;
            """
        )
        self.plot_widget_e2.setStyleSheet(
            """
            border: 2px solid purple;
            background-color: black;
            """
        )
        self.save_button.setStyleSheet("background-color: gray; color: white; font-size: 16px;")

#
# Filter the raw EMG data 
#
def bandpass_filter(data, lowcut=20, highcut=450, fs=1000, order=4):
    nyq = 0.5 * fs
    b, a = butter(order, [lowcut/nyq, highcut/nyq], btype='band')
    return lfilter(b, a, data)

#
# Run the application
#
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = EMGMonitor()
    window.show()
    sys.exit(app.exec_())