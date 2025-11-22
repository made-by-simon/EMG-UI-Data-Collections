import sys
import time
import csv
from PyQt5 import QtWidgets
import pyqtgraph as pg
import mne

#
# Configurations
#

CSV_file = "EMG_data.csv"
Serial_port = "COM3"  # Change as per your system
Baud_rate = 96000 # Number of signal events per second
Sampling_rate = 1000  # Number of samples per second
Activation_threshold = 0.1  # Decides when a muscle is considered active

#
# Class object of the main window
#
class EMGMonitor(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        # Setting the window title and size
        self.setWindowTitle("EMG Monitor")
        self.setStyleSheet("background-color: black; color: white;")
        self.setGeometry(100, 100, 800, 600)

        # Data buffers
        self.raw_data = []
        self.filtered_data = []
        self.time_stamps = []
        self.start_time = time.time()

        # CSV setup
        self.csv_file = open(CSV_file, 'w', newline = "")
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(['Time', 'Raw EMG', 'Filtered EMG'])

        # Plot
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setTitle("EMG Signal")
        self.plot_widget.setLabel('left', 'Amplitude')
        self.plot_widget.setLabel('bottom', 'Time (s)')
        self.raw_curve = self.plot_widget.plot(pen='y')
        self.filtered_curve = self.plot_widget.plot(pen='c')

        # Buttons
        self.start_button = QtWidgets.QPushButton("Start")
        self.stop_button = QtWidgets.QPushButton("Stop")
        self.start_button.clicked.connect(self.start_recording)
        self.stop_button.clicked.connect(self.stop_recording)

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.plot_widget)
        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)

        container = QtWidgets.QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Timer
        self.timer = pg.QtCore.QTimer()
        self.timer.timeout.connect(self.update_data)

        # Add design elements
        self.design_elements()

    def design_elements(self):
        self.start_button.setStyleSheet("background-color: green; color: white; font-size: 16px;")
        self.stop_button.setStyleSheet("background-color: red; color: white; font-size: 16px;")

    def start_recording(self):
        self.timer.start(10)  # Update every 10 ms   
    
    def stop_recording(self):
        self.timer.stop()
        self.csv_file.close()

    def update_data(self):
        # Simulate reading raw EMG data
        raw_emg = self.read_emg_data()
        filtered_emg = self.filter_emg_data(raw_emg)

        current_time = time.time() - self.start_time
        self.time_stamps.append(current_time)
        self.raw_data.append(raw_emg)
        self.filtered_data.append(filtered_emg)

        # Write to CSV
        self.csv_writer.writerow([current_time, raw_emg, filtered_emg])

        # Update plots
        self.raw_curve.setData(self.time_stamps, self.raw_data)
        self.filtered_curve.setData(self.time_stamps, self.filtered_data)

#
# Filter the raw EMG data 
#
def filter_emg_data(self, raw_emg):
    raw_emg.filter(l_freq=0.1, h_freq=50.0) # Apply bandpass filter
    raw_emg.notch_filter(freqs = [50, 60])
    return raw_emg

#
# Run the application
#
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = EMGMonitor()
    window.show()
    sys.exit(app.exec_())