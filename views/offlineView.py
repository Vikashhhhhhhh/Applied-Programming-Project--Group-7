"""
Offline inspection view (Matplotlib).

This window is opened after streaming has stopped or the connection was
closed. It lets the user inspect the recorded signal without live updates:

- choose any channel
- switch between original, RMS and filtered signal

It belongs to the View layer. It receives already-recorded data and a
SignalProcessor from the ViewModel; it does no TCP work itself.
"""

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
from matplotlib.figure import Figure

from models.signal_processing import (
    MODE_FILTERED,
    MODE_ORIGINAL,
    MODE_RMS,
)


# Maps the user-facing combo box text to the internal signal mode keys.
MODE_LABELS = {
    "Original": MODE_ORIGINAL,
    "RMS": MODE_RMS,
    "Filtered": MODE_FILTERED,
}


class OfflineView(QDialog):
    """Modeless dialog showing one channel of the recorded signal."""

    def __init__(self, x, data, processor, parent=None):
        super().__init__(parent)

        self.x = x
        self.data = data            # shape: (channels, samples), original
        self.processor = processor
        self.num_channels = data.shape[0]

        self.setWindowTitle("Offline Signal Inspection")
        self.resize(900, 600)

        layout = QVBoxLayout(self)

        # --- controls ---
        controls = QHBoxLayout()

        controls.addWidget(QLabel("Channel:"))
        self.channel_input = QSpinBox()
        self.channel_input.setRange(1, self.num_channels)
        self.channel_input.setValue(1)
        controls.addWidget(self.channel_input)

        controls.addWidget(QLabel("Signal mode:"))
        self.mode_input = QComboBox()
        self.mode_input.addItems(MODE_LABELS.keys())
        controls.addWidget(self.mode_input)

        controls.addStretch()
        layout.addLayout(controls)

        # --- matplotlib canvas ---
        self.figure = Figure(figsize=(8, 5))
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.axes = self.figure.add_subplot(111)

        layout.addWidget(NavigationToolbar2QT(self.canvas, self))
        layout.addWidget(self.canvas)

        # Redraw whenever the user changes channel or mode.
        self.channel_input.valueChanged.connect(self.redraw)
        self.mode_input.currentTextChanged.connect(self.redraw)

        self.redraw()

    def redraw(self):
        """Apply the selected mode to the selected channel and plot it."""
        channel_index = self.channel_input.value() - 1
        mode = MODE_LABELS[self.mode_input.currentText()]

        y = self.processor.apply(self.data[channel_index], mode)

        self.axes.clear()
        self.axes.plot(self.x, y, color="tab:blue", linewidth=0.8)
        self.axes.set_title(
            f"Channel {channel_index + 1} - {self.mode_input.currentText()} signal"
        )
        self.axes.set_xlabel("Time (s)")
        self.axes.set_ylabel("Amplitude")
        self.axes.grid(True, alpha=0.3)
        self.figure.tight_layout()
        self.canvas.draw_idle()
