"""
Flask web interface for real-time EMG signal collection and recording.
Progressive 3-page interface: Setup -> Recording -> Results
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import threading
import serial
import numpy as np
import pyedflib
from datetime import datetime
from pathlib import Path
import time
import mne
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO
import base64

app = Flask(__name__)

# Configuration
SERIAL_PORT = "COM9"
BAUD_RATE = 96000
SAMPLING_RATE = 1000

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, "recordings", "raw")
FILTERED_DIR = os.path.join(BASE_DIR, "recordings", "filtered")

# Global state
recording_state = {
    'is_recording': False,
    'elapsed_ms': 0,
    'samples_collected': 0,
    'status': 'idle',
    'raw_path': None,
    'filtered_path': None,
    'serial_connected': False,
    'plot_image': None
}

# Serial reading thread
serial_thread = None
serial_connection = None
edf_writer = None
edf_buffer = []
recording_lock = threading.Lock()

@app.route('/')
def index():
    return render_template('index_emg.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, ''),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/api/check_serial', methods=['POST'])
def check_serial():
    """Check if serial port is available."""
    data = request.json
    port = data.get('port', SERIAL_PORT)

    try:
        test_serial = serial.Serial(port, BAUD_RATE, timeout=1)
        test_serial.close()
        return jsonify({
            'connected': True,
            'message': f'Serial port {port} is available'
        })
    except Exception as e:
        return jsonify({
            'connected': False,
            'message': f'Cannot connect to {port}: {str(e)}'
        }), 400

@app.route('/api/start_recording', methods=['POST'])
def start_recording():
    global recording_state, serial_thread

    if recording_state['is_recording']:
        return jsonify({'error': 'Recording already in progress'}), 400

    data = request.json
    subject_id = data.get('subject_id', 'EMGTest')
    port = data.get('port', SERIAL_PORT)
    duration = int(data.get('duration', 30))

    # Initialize recording
    recording_state['is_recording'] = True
    recording_state['elapsed_ms'] = 0
    recording_state['samples_collected'] = 0
    recording_state['status'] = 'Initializing...'
    recording_state['duration_ms'] = duration * 1000

    # Start recording thread
    thread = threading.Thread(
        target=run_recording,
        args=(subject_id, port, duration)
    )
    thread.start()

    return jsonify({'message': 'Recording started'})

@app.route('/api/stop_recording', methods=['POST'])
def stop_recording():
    global recording_state

    if not recording_state['is_recording']:
        return jsonify({'error': 'No recording in progress'}), 400

    recording_state['is_recording'] = False
    recording_state['status'] = 'Stopping...'

    return jsonify({'message': 'Recording stopped'})

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({
        'is_recording': recording_state['is_recording'],
        'elapsed_ms': recording_state['elapsed_ms'],
        'samples_collected': recording_state['samples_collected'],
        'status': recording_state['status'],
        'raw_path': recording_state['raw_path'],
        'filtered_path': recording_state['filtered_path'],
        'duration_ms': recording_state.get('duration_ms', 0),
        'plot_image': recording_state.get('plot_image')
    })

@app.route('/api/plot', methods=['GET'])
def get_plot():
    """Return the signal visualization plot."""
    if recording_state['plot_image'] is None:
        return jsonify({'error': 'No plot available'}), 404

    return jsonify({'image': recording_state['plot_image']})

def run_recording(subject_id, port, duration_sec):
    global recording_state, serial_connection, edf_writer, edf_buffer

    try:
        # Create directories
        os.makedirs(RAW_DIR, exist_ok=True)
        os.makedirs(FILTERED_DIR, exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime("%b-%d-%Y_%H-%M-%S")
        raw_filename = f"{subject_id}_{timestamp}_raw.edf"
        raw_path = os.path.join(RAW_DIR, raw_filename)

        recording_state['status'] = 'Opening serial connection...'

        # Open serial connection
        serial_connection = serial.Serial(port, BAUD_RATE, timeout=0.01)
        time.sleep(1)  # Allow connection to stabilize

        recording_state['status'] = 'Creating EDF file...'

        # Initialize EDF writer
        edf_writer = pyedflib.EdfWriter(
            raw_path,
            1,
            pyedflib.FILETYPE_EDFPLUS
        )

        edf_writer.setSignalHeaders([{
            'label': 'EMG',
            'dimension': 'uV',
            'sample_frequency': SAMPLING_RATE,
            'physical_min': -5000,
            'physical_max': 5000,
            'digital_min': -32768,
            'digital_max': 32767,
            'transducer': 'EMG Sensor',
            'prefilter': 'None'
        }])

        edf_buffer = []
        recording_state['status'] = 'Recording...'
        recording_state['raw_path'] = raw_path

        start_time = time.time()
        target_samples = duration_sec * SAMPLING_RATE

        # Read samples
        while recording_state['is_recording'] and recording_state['samples_collected'] < target_samples:
            try:
                line = serial_connection.readline().decode(errors='ignore').strip()
                if line:
                    value = float(line)
                    edf_buffer.append(value)
                    recording_state['samples_collected'] += 1

                    # Write buffer to file periodically
                    if len(edf_buffer) >= SAMPLING_RATE:
                        edf_writer.writeSamples([np.array(edf_buffer)])
                        edf_buffer = []

                    # Update elapsed time
                    recording_state['elapsed_ms'] = int((time.time() - start_time) * 1000)

            except ValueError:
                pass  # Ignore bad samples

        # Flush remaining samples
        if edf_buffer:
            edf_writer.writeSamples([np.array(edf_buffer)])

        edf_writer.close()
        serial_connection.close()

        recording_state['status'] = 'Applying bandpass filter...'

        # Apply filtering
        filtered_path = apply_filter(raw_path, subject_id, timestamp)
        recording_state['filtered_path'] = filtered_path

        recording_state['status'] = 'Generating plot...'

        # Generate visualization plot
        plot_image = generate_plot(raw_path, filtered_path)
        recording_state['plot_image'] = plot_image

        recording_state['status'] = 'Complete'

    except Exception as e:
        recording_state['status'] = f'Error: {str(e)}'
        print(f"Recording error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        recording_state['is_recording'] = False
        if serial_connection:
            try:
                serial_connection.close()
            except:
                pass
        if edf_writer:
            try:
                edf_writer.close()
            except:
                pass

def apply_filter(raw_path, subject_id, timestamp):
    """Apply bandpass filter (20-450 Hz) to raw EMG signal."""
    from pyedflib import highlevel

    # Read raw signal
    signals, headers, _ = highlevel.read_edf(raw_path)

    # Apply bandpass filter
    filtered = mne.filter.filter_data(
        signals, SAMPLING_RATE, 20., 450., fir_design='firwin'
    )

    # Create filtered filename
    filtered_filename = f"{subject_id}_{timestamp}_filtered.edf"
    filtered_path = os.path.join(FILTERED_DIR, filtered_filename)

    # Write filtered EDF
    with pyedflib.EdfWriter(
        filtered_path, 1, pyedflib.FILETYPE_EDFPLUS
    ) as fw:
        fw.setSignalHeaders(headers)
        fw.writeSamples([filtered[0]])

    return filtered_path

def generate_plot(raw_path, filtered_path):
    """Generate matplotlib plot comparing raw and filtered signals."""
    from pyedflib import highlevel

    # Bionix color scheme
    COLOR_PRIMARY = '#111111'
    COLOR_ACCENT = '#7e0000'
    COLOR_SECONDARY = '#004749'
    COLOR_TERTIARY = '#b09b72'
    COLOR_BACKGROUND = '#ededed'

    # Read both signals
    raw_signals, _, _ = highlevel.read_edf(raw_path)
    filtered_signals, _, _ = highlevel.read_edf(filtered_path)

    # Create time axis (in seconds)
    time_axis = np.arange(len(raw_signals[0])) / SAMPLING_RATE

    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8))
    fig.patch.set_facecolor(COLOR_BACKGROUND)

    # Plot raw signal
    ax1.plot(time_axis, raw_signals[0], color=COLOR_ACCENT, linewidth=0.6, alpha=0.9)
    ax1.set_title('Raw EMG Signal', color=COLOR_PRIMARY, fontsize=16, fontweight='bold', pad=15)
    ax1.set_xlabel('Time (seconds)', color=COLOR_PRIMARY, fontsize=12, fontweight='600')
    ax1.set_ylabel('Amplitude (µV)', color=COLOR_PRIMARY, fontsize=12, fontweight='600')
    ax1.grid(True, alpha=0.15, color=COLOR_TERTIARY, linestyle='-', linewidth=0.5)
    ax1.set_facecolor('#ffffff')
    ax1.spines['bottom'].set_color(COLOR_TERTIARY)
    ax1.spines['top'].set_color(COLOR_TERTIARY)
    ax1.spines['left'].set_color(COLOR_TERTIARY)
    ax1.spines['right'].set_color(COLOR_TERTIARY)
    ax1.tick_params(colors=COLOR_PRIMARY, labelsize=10)

    # Plot filtered signal
    ax2.plot(time_axis, filtered_signals[0], color=COLOR_SECONDARY, linewidth=0.6, alpha=0.9)
    ax2.set_title('Filtered EMG Signal (20-450 Hz Bandpass)', color=COLOR_PRIMARY, fontsize=16, fontweight='bold', pad=15)
    ax2.set_xlabel('Time (seconds)', color=COLOR_PRIMARY, fontsize=12, fontweight='600')
    ax2.set_ylabel('Amplitude (µV)', color=COLOR_PRIMARY, fontsize=12, fontweight='600')
    ax2.grid(True, alpha=0.15, color=COLOR_TERTIARY, linestyle='-', linewidth=0.5)
    ax2.set_facecolor('#ffffff')
    ax2.spines['bottom'].set_color(COLOR_TERTIARY)
    ax2.spines['top'].set_color(COLOR_TERTIARY)
    ax2.spines['left'].set_color(COLOR_TERTIARY)
    ax2.spines['right'].set_color(COLOR_TERTIARY)
    ax2.tick_params(colors=COLOR_PRIMARY, labelsize=10)

    plt.tight_layout()

    # Convert plot to base64 string
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=120, facecolor=COLOR_BACKGROUND, edgecolor='none')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    plt.close(fig)

    return image_base64

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)

    print("Starting Flask EMG Monitor...")
    print("Open your browser to: http://localhost:5000")

    app.run(debug=True, use_reloader=False)
