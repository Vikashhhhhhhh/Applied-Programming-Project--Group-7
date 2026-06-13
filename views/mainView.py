from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QLabel,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)

from views.plotView import VisPyPlotWidget, MultiChannelPlotWidget
from views.offlineView import OfflineView, MODE_LABELS


class MainView(QMainWindow):
    """
    Main application window.

    The View owns the visible widgets:
    - TCP port input, connect/disconnect buttons and a connection status label
    - channel selector and signal-mode selector
    - a "Plot All Channels" toggle and an offline-inspection button
    - y-scale input
    - a stacked plot area (single-channel and all-channels VisPy widgets)

    The View does not receive TCP data directly. It only connects ViewModel
    signals to the visible widgets and forwards user actions to the ViewModel.
    """

    def __init__(self, view_model):
        super().__init__()

        self.view_model = view_model
        self.offline_window = None

        self.setWindowTitle("TCP EMG Viewer")
        self.resize(1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        self.time_label = QLabel("Signal time: 0.00 s")
        self.time_label.setStyleSheet("font-size: 18px; font-weight: bold;")

        content_layout = QHBoxLayout()
        content_layout.setSpacing(8)

        control_layout = QVBoxLayout()
        control_layout.setSpacing(8)

        # --- TCP connection controls ---
        control_layout.addWidget(QLabel("TCP port"))
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(self.view_model.port)
        control_layout.addWidget(self.port_input)

        self.connect_button = QPushButton("Connect")
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setEnabled(False)
        control_layout.addWidget(self.connect_button)
        control_layout.addWidget(self.disconnect_button)

        self.status_label = QLabel("Status: not connected")
        self.status_label.setWordWrap(True)
        control_layout.addWidget(self.status_label)

        # --- channel and signal-mode selection ---
        control_layout.addWidget(QLabel("Channel"))
        self.channel_input = QSpinBox()
        self.channel_input.setRange(1, self.view_model.channels)
        self.channel_input.setValue(self.view_model.selected_channel + 1)
        control_layout.addWidget(self.channel_input)

        control_layout.addWidget(QLabel("Signal mode"))
        self.mode_input = QComboBox()
        self.mode_input.addItems(MODE_LABELS.keys())
        control_layout.addWidget(self.mode_input)

        # --- y scale ---
        self.y_scale_label = QLabel("Y scale")
        self.y_scale_input = QDoubleSpinBox()
        self.y_scale_input.setRange(0.01, 100000.0)
        self.y_scale_input.setValue(300.0)
        self.y_scale_input.setSingleStep(50.0)
        self.y_scale_input.setDecimals(2)
        control_layout.addWidget(self.y_scale_label)
        control_layout.addWidget(self.y_scale_input)

        # --- view toggles ---
        self.plot_all_button = QPushButton("Plot All Channels")
        control_layout.addWidget(self.plot_all_button)

        self.offline_button = QPushButton("Show Offline Plot")
        control_layout.addWidget(self.offline_button)

        control_layout.addStretch()

        self.info_label = QLabel("Enter the port and press Connect.")
        self.info_label.setWordWrap(True)
        control_layout.addWidget(self.info_label)

        # --- plot area: single-channel and all-channels stacked ---
        self.plot_widget = VisPyPlotWidget(
            visible_duration_seconds=10.0,
            y_scale=self.y_scale_input.value(),
        )
        self.multi_plot_widget = MultiChannelPlotWidget(
            num_channels=self.view_model.channels,
            visible_duration_seconds=10.0,
            y_scale=self.y_scale_input.value(),
        )

        self.plot_stack = QStackedWidget()
        self.plot_stack.addWidget(self.plot_widget)        # index 0: single
        self.plot_stack.addWidget(self.multi_plot_widget)  # index 1: all

        content_layout.addLayout(control_layout, stretch=0)
        content_layout.addWidget(self.plot_stack, stretch=1)

        main_layout.addWidget(self.time_label)
        main_layout.addLayout(content_layout)

        # --- wire user actions to the ViewModel ---
        self.connect_button.clicked.connect(self.connect_to_server)
        self.disconnect_button.clicked.connect(self.view_model.stop_plotting)
        self.channel_input.valueChanged.connect(self.change_channel)
        self.mode_input.currentTextChanged.connect(self.change_mode)
        self.plot_all_button.clicked.connect(self.toggle_view_mode)
        self.offline_button.clicked.connect(self.open_offline_view)

        self.y_scale_input.valueChanged.connect(self.plot_widget.set_y_scale)
        self.y_scale_input.valueChanged.connect(self.multi_plot_widget.set_y_scale)

        # --- wire ViewModel signals to the visible widgets ---
        self.view_model.plot_updated.connect(self.plot_widget.update_plot)
        self.view_model.plot_all_updated.connect(self.multi_plot_widget.update_plot)
        self.view_model.status_updated.connect(self.info_label.setText)
        self.view_model.status_updated.connect(self.update_status)
        self.view_model.signal_time_updated.connect(self.update_signal_time)
        self.view_model.signal_time_updated.connect(self.plot_widget.set_signal_time)
        self.view_model.connection_changed.connect(self.on_connection_changed)

    # ----- user actions --------------------------------------------------

    def connect_to_server(self):
        """Read the port from the GUI and ask the ViewModel to connect."""
        port = self.port_input.value()
        self.view_model.start_plotting(port=port)

    def change_channel(self, value):
        """The spin box is 1-based; the ViewModel uses 0-based indices."""
        self.view_model.set_selected_channel(value - 1)

    def change_mode(self, label):
        self.view_model.set_signal_mode(MODE_LABELS[label])

    def toggle_view_mode(self):
        """Switch between the single-channel and all-channels live views."""
        if self.view_model.view_mode == "single":
            self.view_model.set_view_mode("all")
            self.plot_stack.setCurrentIndex(1)
            self.plot_all_button.setText("Plot Single Channel")
            self.channel_input.setEnabled(False)
        else:
            self.view_model.set_view_mode("single")
            self.plot_stack.setCurrentIndex(0)
            self.plot_all_button.setText("Plot All Channels")
            self.channel_input.setEnabled(True)

    def open_offline_view(self):
        """Open the Matplotlib offline inspection window."""
        if not self.view_model.has_offline_data():
            self.info_label.setText("No data available for offline plotting.")
            return

        x, data = self.view_model.get_offline_data()
        self.offline_window = OfflineView(
            x=x,
            data=data,
            processor=self.view_model.processor,
            parent=self,
        )
        self.offline_window.show()

    # ----- ViewModel reactions ------------------------------------------

    def on_connection_changed(self, is_connected):
        """Enable/disable controls based on the connection state."""
        self.connect_button.setEnabled(not is_connected)
        self.disconnect_button.setEnabled(is_connected)
        self.port_input.setEnabled(not is_connected)

    def update_status(self, text):
        self.status_label.setText(f"Status: {text}")

    def update_signal_time(self, signal_time_seconds):
        self.time_label.setText(f"Signal time: {signal_time_seconds:.2f} s")
