# Applied-Programming-Project--Group-7

**Final Project — TCP Signal Visualization Application**
Applied Programming 2026, Group 7.

A PySide6 desktop application for live visualization and offline inspection of
streamed EMG signal data. The application is the **client** for the TCP server
provided in Exercise 5. It is built with an **MVVM** architecture.

---

## Team members and responsibilities

| Member | Responsibility |
|--------|----------------|
| _Member 1_ | TCP / backend (model, buffering, server integration) |
| _Member 2_ | Visualization / frontend (VisPy live plots, GUI) |
| _Member 3_ | Documentation / integration (offline view, README, testing) |

> Please replace the member names above with the actual team members.

---

## Features

- Connect to the TCP server using a port entered in the GUI; streaming starts
  automatically after connecting.
- Live single-channel plot with VisPy (rolling 10 s window, axes and moving
  time labels).
- **Channel selection** (channels 1–32).
- **Plot All Channels** button: shows all 32 channels at once with a vertical
  offset between them.
- **Signal modes**: original, RMS and filtered — for both the live VisPy plot
  and the offline Matplotlib plot.
- **Offline inspection** with Matplotlib after disconnecting (channel and mode
  selection).
- Connection status display and basic error handling.

---

## Installation

A clean Python 3.11 environment is recommended.

```powershell
pip install -r requirements.txt
```

Dependencies (`requirements.txt`):

```
pyside6
vispy
matplotlib
numpy<2
scipy
```

> NumPy is pinned to `<2` because the pre-built `matplotlib`/`vispy` wheels are
> compiled against NumPy 1.x. NumPy 2.x causes an import-time crash.

---

## Running the application

The application needs the TCP server running first.

**1. Start the server** (provided in `TCP_Server/`):

```powershell
python TCP_Server/main.py
```

The server loads `recording.pkl`. It looks for the file automatically next to
or inside the project folder. If your file is elsewhere, pass the path:

```python
EMGTCPServer(pkl_file="path/to/recording.pkl")
```

**2. Start the client application:**

```powershell
python main.py
```

---

## How to use the GUI

1. **Connect** — enter the TCP **port** (default `12345`) and press
   **Connect**. The status label shows the connection state and streaming
   starts automatically.
2. **Live plot** — the selected channel is drawn in a rolling 10 second window.
   Adjust **Y scale** to change the vertical zoom.
3. **Switch channels** — use the **Channel** selector (1–32).
4. **Signal mode** — choose **Original**, **RMS** or **Filtered** from the
   **Signal mode** dropdown. This applies to the live plot.
5. **Plot All Channels** — press the button to show all 32 channels stacked
   with a vertical offset. Press again to return to the single-channel view.
6. **Disconnect** — press **Disconnect** to stop streaming.
7. **Offline plot** — press **Show Offline Plot** to open a Matplotlib window
   for the recorded signal, where you can change channel and signal mode.

---

## Signal processing parameters

Defined in [models/signal_processing.py](models/signal_processing.py):

- **RMS**: moving root-mean-square with a **50 ms** window
  (`sqrt(moving_average(signal**2))`).
- **Filter**: **4th-order Butterworth band-pass**, **20 Hz – 450 Hz**,
  applied with zero-phase `filtfilt`.

These parameters are typical for surface EMG and can be changed in the
`SignalProcessor` constructor.

---

## Data format

Each TCP chunk contains **32 channels × 18 samples** of `float64` values sent
as raw bytes (`32 × 18 × 8 = 4608 bytes` per packet). The client collects the
byte stream, reconstructs whole packets, and keeps a rolling 10 second window
for the live plot plus a full history for offline inspection.

---

## Project structure (MVVM)

```
Applied-Programming-Project--Group-7/
├── main.py                     # application entry point
├── README.md
├── requirements.txt
├── models/                     # Model / service layer (no GUI code)
│   ├── tcp_client_model.py     # TCP receiving, buffering, rolling window
│   └── signal_processing.py    # RMS and band-pass filtering
├── viewmodels/
│   └── mainViewModel.py        # state, timer, connects GUI actions to data
├── views/                      # View layer (GUI + plotting)
│   ├── mainView.py             # main window and controls
│   ├── plotView.py             # VisPy single- and multi-channel widgets
│   └── offlineView.py          # Matplotlib offline inspection window
└── TCP_Server/
    └── main.py                 # provided server (Exercise 5)
```

**Responsibility split:**

- **Models** handle TCP communication, buffering and signal processing. They
  contain no GUI code.
- The **ViewModel** owns the application state (selected channel, signal mode,
  view mode, connection state), drives the `QTimer`, applies signal processing
  and emits Qt signals.
- **Views** contain only GUI and plotting widgets. They never read the TCP
  socket directly — they react to ViewModel signals and forward user actions.

---

## Error handling

The application reports problems via the GUI status message instead of
crashing, including:

- server not running / wrong port (connection refused)
- connection lost while streaming (server closes the stream)
- no data available for offline plotting
- channel and signal-mode inputs constrained to valid values
