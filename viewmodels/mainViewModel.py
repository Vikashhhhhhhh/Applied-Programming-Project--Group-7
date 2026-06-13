from PySide6.QtCore import QObject, QTimer, Signal

from models.tcp_client_model import TcpClientModel
from models.signal_processing import SignalProcessor, MODE_ORIGINAL


class MainViewModel(QObject):
    """
    ViewModel for the TCP live plotting application.

    Responsibilities:
    - create the TCP client model and the signal processing service
    - connect/disconnect from the server (port chosen in the GUI)
    - use a QTimer to regularly ask the model for new data
    - apply the selected signal mode (original / RMS / filtered)
    - emit single-channel OR all-channel plot data to the View
    - emit the current signal time and connection status to the View

    The View never touches the TCP socket directly. It only reacts to the
    signals emitted here.
    """

    # x, y for the single selected channel.
    plot_updated = Signal(object, object)
    # x, Y(channels, samples) for the "Plot All Channels" view.
    plot_all_updated = Signal(object, object)

    status_updated = Signal(str)
    signal_time_updated = Signal(float)
    # True when connected/streaming, False otherwise.
    connection_changed = Signal(bool)

    def __init__(self):
        super().__init__()

        self.host = "localhost"
        self.port = 12345
        self.sampling_rate = 2000
        self.channels = 32

        self.model = TcpClientModel(
            host=self.host,
            port=self.port,
            sampling_rate=self.sampling_rate,
            channels=self.channels,
            samples_per_packet=18,
            window_seconds=10,
            selected_channel=0,
        )

        self.processor = SignalProcessor(self.sampling_rate)

        self.is_plotting = False

        # Application state.
        self.selected_channel = 0          # 0-based channel index
        self.signal_mode = MODE_ORIGINAL   # original / rms / filtered
        self.view_mode = "single"          # "single" or "all"

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_plot)

    # ----- state setters -------------------------------------------------

    def set_selected_channel(self, channel_index):
        """Select the channel (0-based) shown in the single-channel view."""
        self.selected_channel = int(channel_index)
        self.model.set_selected_channel(self.selected_channel)

    def set_signal_mode(self, mode):
        """Set the signal mode used for the live plot."""
        self.signal_mode = mode

    def set_view_mode(self, mode):
        """Switch between the single-channel and all-channels live views."""
        if mode in ("single", "all"):
            self.view_mode = mode

    # ----- connection control -------------------------------------------

    def start_plotting(self, port=None):
        """Connect to the server on the given port and start streaming."""
        if self.is_plotting:
            return

        try:
            self.model.connect(port=port)
        except (OSError, ValueError) as error:
            self.status_updated.emit(f"Could not connect to server: {error}")
            self.connection_changed.emit(False)
            return

        self.is_plotting = True
        self.status_updated.emit(
            f"Connected to TCP server on port {self.model.port}."
        )
        self.connection_changed.emit(True)
        self.timer.start(10)

    def stop_plotting(self):
        """Stop streaming and close the TCP connection."""
        if not self.is_plotting:
            return

        self.timer.stop()
        self.model.disconnect()

        self.is_plotting = False
        self.status_updated.emit("Disconnected from TCP server.")
        self.connection_changed.emit(False)

    def _handle_connection_lost(self):
        """Handle the server closing the connection during streaming."""
        self.timer.stop()
        self.is_plotting = False
        self.status_updated.emit("Connection lost. The server closed the stream.")
        self.connection_changed.emit(False)

    # ----- live update ---------------------------------------------------

    def update_plot(self):
        """
        Receive new TCP data, process it, and emit it to the View.

        Called repeatedly by the QTimer while streaming.
        """
        self.model.receive_data()

        # The model disconnects itself if the server closes the stream.
        if self.is_plotting and not self.model.is_connected:
            self._handle_connection_lost()
            return

        if not self.model.has_data():
            return

        if self.view_mode == "all":
            x, y_all = self.model.get_all_window()
            y_all = self.processor.apply(y_all, self.signal_mode)
            self.plot_all_updated.emit(x, y_all)
        else:
            x, y = self.model.get_window()
            y = self.processor.apply(y, self.signal_mode)
            self.plot_updated.emit(x, y)

        signal_time = self.model.get_signal_time_seconds()
        self.signal_time_updated.emit(signal_time)

    # ----- offline inspection -------------------------------------------

    def has_offline_data(self):
        """Return True if there is recorded data to inspect offline."""
        return self.model.has_full_history()

    def get_offline_data(self):
        """
        Return data for the offline Matplotlib view.

        Returns (x, Y) where Y is the full recorded signal with shape
        (channels, samples). The original (unprocessed) signal is returned;
        the offline view applies the chosen signal mode itself.
        """
        return self.model.get_full_history()
