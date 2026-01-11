import sys
import serial
import numpy as np
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtGui import QFont
import pyqtgraph as pg
import pyedflib
from datetime import datetime
import os
import mne

# Configuration
SERIAL_PORT = "COM9"
BAUD_RATE = 96000
SAMPLING_RATE = 1000
WINDOW_SECONDS = 5
VERSION = "v2.1"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EDF_DIR = os.path.join(BASE_DIR, "recordings") # Directory for EDF files
RAW_DIR = os.path.join(BASE_DIR, "recordings", "raw")
FILTERED_DIR = os.path.join(BASE_DIR, "recordings", "filtered")

MAX_SAMPLES = SAMPLING_RATE * WINDOW_SECONDS

# Serial Thread
class SerialThread(QtCore.QThread):
    data_received = QtCore.pyqtSignal(float)

    def __init__(self, port, baud):
        super().__init__()
        self.port = port
        self.baud = baud
        self.running = True

    def run(self):
        try:
            ser = serial.Serial(self.port, self.baud, timeout=0.01)
            while self.running:
                line = ser.readline().decode(errors="ignore").strip()
                try:
                    self.data_received.emit(float(line))
                except ValueError:
                    pass
            ser.close()
        except Exception as e:
            print("Serial error:", e)

    def stop(self):
        self.running = False
        self.wait()

# Main Window 
class EMGMonitor(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Real-Time EMG Monitor")
        self.setGeometry(100, 100, 900, 700)
        self.setStyleSheet("background-color: #0e0e0e; color: white;")

        self.data = np.zeros(MAX_SAMPLES)
        self.ptr = 0

        self.edf = None
        self.edf_path = None
        self.edf_buffer = []

        self.init_ui()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)

        self.serial_thread = None

        self.elapsed_ms = 0
        self.timer.timeout.connect(self.update_plot)

    # EDF 
    def init_edf(self):
        os.makedirs(RAW_DIR, exist_ok=True)
        os.makedirs(FILTERED_DIR, exist_ok=True)

        # Create RAW filename
        name = self.edit_name.text().strip()
        ts = datetime.now().strftime("%b-%d-%Y_%H-%M-%S-%f")[:-3]

        if name:
            raw_name = f"{name}_{ts}edf"
        else:
            raw_name = f"EMGTest_{ts}.edf"

        self.raw_edf_path = os.path.join(RAW_DIR, raw_name)

        # Open RAW EDF for writing
        self.edf = pyedflib.EdfWriter(
            self.raw_edf_path,
            1,
            pyedflib.FILETYPE_EDFPLUS
        )

        self.edf.setSignalHeaders([{
            "label": "EMG",
            "dimension": "uV",
            "sample_frequency": SAMPLING_RATE,
            "physical_min": -5000,
            "physical_max": 5000,
            "digital_min": -32768,
            "digital_max": 32767,
            "transducer": "EMG Sensor",
            "prefilter": "None"
        }])

        self.edf_buffer.clear()

    # UI 
    def init_ui(self):
        title = QtWidgets.QLabel("Real-Time EMG Monitor")
        title.setFont(QFont("Arial", 22, QFont.Bold))

        self.timer_label = QtWidgets.QLabel("00:00.000")
        self.timer_label.setFont(QFont("Arial", 12))


        subtitle = QtWidgets.QLabel(f"Version {VERSION}")
        subtitle.setStyleSheet("color: #aaaaaa;")

        self.plot = pg.PlotWidget()
        self.plot.setBackground("k")
        self.plot.hideAxis("left")
        self.plot.hideAxis("bottom")
        self.curve = self.plot.plot(pen=pg.mkPen("#00ffff", width=2))

        self.start_btn = QtWidgets.QPushButton("Start")
        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.view_btn = QtWidgets.QPushButton("View EDF")
        self.edit_name = QtWidgets.QLineEdit()

        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)
        self.view_btn.clicked.connect(self.view_edf)
        self.edit_name.returnPressed.connect(lambda: self.change_name())

        self.start_btn.setStyleSheet("background:#1db954; font-size:16px; padding:8px;")
        self.stop_btn.setStyleSheet("background:#e63946; font-size:16px; padding:8px;")
        self.view_btn.setStyleSheet("background:#457b9d; font-size:16px; padding:8px;")

        btns = QtWidgets.QHBoxLayout()
        btns.addWidget(self.start_btn)
        btns.addWidget(self.stop_btn)
        btns.addWidget(self.view_btn)

        name = QtWidgets.QHBoxLayout()
        name.addWidget(QtWidgets.QLabel("ID:"))
        name.addWidget(self.edit_name)


        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(self.timer_label)
        layout.addWidget(subtitle)
        layout.addWidget(self.plot)
        layout.addLayout(btns)
        layout.addLayout(name)

        container = QtWidgets.QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    # Controls 
    def start(self):
        self.data[:] = 0
        self.ptr = 0
        self.elapsed_ms = 0
        self.timer_label.setText("00:00.000")

        self.init_edf()

        self.serial_thread = SerialThread(SERIAL_PORT, BAUD_RATE)
        self.serial_thread.data_received.connect(self.on_data)
        self.serial_thread.start()

        self.timer.start(30)

    def stop(self):
        if self.serial_thread:
            self.serial_thread.stop()
            self.serial_thread = None

        # Flush remaining RAW samples
        if self.edf and self.edf_buffer:
            self.edf.writeSamples([np.array(self.edf_buffer)])
            self.edf_buffer.clear()

        if self.edf:
            self.edf.close()
            self.edf = None

        self.timer.stop()

        # Create filtered EDF
        try:
            from pyedflib import highlevel

            signals, headers, _ = highlevel.read_edf(self.raw_edf_path)

            # Apply bandpass filter (20–450 Hz)
            filtered = mne.filter.filter_data(
                signals, SAMPLING_RATE, 20., 450., fir_design='firwin'
            )

            # Create filtered filename
            base = os.path.basename(self.raw_edf_path).replace("_raw.edf", "")
            self.filtered_edf_path = os.path.join(
                FILTERED_DIR, f"{base}.edf"
            )

            # Write filtered EDF
            with pyedflib.EdfWriter(
                self.filtered_edf_path, 1, pyedflib.FILETYPE_EDFPLUS
            ) as fw:
                fw.setSignalHeaders(headers)
                fw.writeSamples([filtered[0]])

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Filtering Error", str(e))
            return

        QtWidgets.QMessageBox.information(
            self,
            "Recording Saved",
            f"RAW:\n{self.raw_edf_path}\n\nFILTERED:\n{self.filtered_edf_path}"
        )


    # Data Handling
    def on_data(self, value):
        if self.edf is None:
            return

        self.data[self.ptr % MAX_SAMPLES] = value
        self.ptr += 1
        self.edf_buffer.append(value)

        if len(self.edf_buffer) >= SAMPLING_RATE:
            self.edf.writeSamples([np.array(self.edf_buffer)])
            self.edf_buffer.clear()

    def update_plot(self):
        idx = self.ptr % MAX_SAMPLES
        self.curve.setData(np.roll(self.data, -idx))

        # Update timer label
        self.elapsed_ms += self.timer.interval()
        minutes = self.elapsed_ms // 60000
        seconds = (self.elapsed_ms % 60000) // 1000
        millis = self.elapsed_ms % 1000

        self.timer_label.setText(f"{minutes:02}:{seconds:02}.{millis:03}")

    # EDF Viewer 
    def view_edf(self):
        if not self.raw_edf_path or not os.path.exists(self.raw_edf_path):
            QtWidgets.QMessageBox.warning(self, "No File", "No RAW EDF file to display.")
            return

        try:
            from pyedflib import highlevel
            import matplotlib.pyplot as plt

            # Display raw EDF
            raw_signals, raw_headers, _ = highlevel.read_edf(self.raw_edf_path)

            fig, ax = plt.subplots(figsize=(12, 4))
            ax.plot(raw_signals[0], linewidth=0.8)
            ax.set_title("Recorded RAW EMG Signal")
            ax.set_xlabel("Samples")
            ax.set_ylabel("Amplitude (µV)")
            ax.grid(True, alpha=0.3)

            # Display filtered EDF
            if self.filtered_edf_path and os.path.exists(self.filtered_edf_path):
                filt_signals, filt_headers, _ = highlevel.read_edf(self.filtered_edf_path)

                fig, ax = plt.subplots(figsize=(12, 4))
                ax.plot(filt_signals[0], linewidth=0.8)
                ax.set_title("Recorded FILTERED EMG Signal")
                ax.set_xlabel("Samples")
                ax.set_ylabel("Amplitude (µV)")
                ax.grid(True, alpha=0.3)

            plt.tight_layout()
            plt.show()

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "EDF Viewer Error", str(e))


    def change_name(self):
        new_name = self.edit_name.text()
        ts = datetime.now().strftime("%b-%d-%Y_%H-%M-%S")
        self.edf_path = os.path.join(EDF_DIR, f"{new_name}_{ts}.edf")
        

# Run Application
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = EMGMonitor()
    win.show()
    sys.exit(app.exec_())
