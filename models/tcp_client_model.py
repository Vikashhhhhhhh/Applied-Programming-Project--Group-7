import socket
import numpy as np


class TcpClientModel:
    """
    Simple TCP client model for receiving EMG data.

    Expected server data:
    - 32 channels
    - 18 samples per packet
    - float64 values
    - raw bytes sent with current_window.tobytes()

    The model stores a rolling 10-second buffer.
    Older samples are removed when new samples arrive.
    """

    def __init__(
        self,
        host,
        port,
        sampling_rate,
        channels,
        samples_per_packet,
        window_seconds,
        selected_channel,
    ):
        self.host = host
        self.port = port
        self.sampling_rate = sampling_rate
        self.channels = channels
        self.samples_per_packet = samples_per_packet
        self.window_seconds = window_seconds
        self.selected_channel = selected_channel

        # IMPORTANT:
        # This must match the dtype used by the server before calling .tobytes().
        self.dtype = np.float64

        self.socket = None
        self.is_connected = False

        self.packet_size = self.channels * self.samples_per_packet
        self.packet_size_bytes = self.packet_size * np.dtype(self.dtype).itemsize

        self.window_size = int(self.sampling_rate * self.window_seconds)

        self.byte_buffer = bytearray()
        self.data_buffer = np.empty((self.channels, 0), dtype=self.dtype)

        # Full (un-trimmed) history of every received sample.
        # This is used for the offline Matplotlib inspection after streaming
        # has stopped. The rolling data_buffer above only keeps the visible
        # 10-second window for the live plot.
        self.full_data_buffer = np.empty((self.channels, 0), dtype=self.dtype)

        # Counts how many samples were received in total.
        # This is used to calculate the signal time.
        self.total_samples_received = 0

    def set_selected_channel(self, channel_index):
        """Select which channel (0-based) the live single-channel plot shows."""
        if 0 <= channel_index < self.channels:
            self.selected_channel = channel_index

    def reset_buffers(self):
        """Clear all buffers so a new streaming session starts cleanly."""
        self.byte_buffer = bytearray()
        self.data_buffer = np.empty((self.channels, 0), dtype=self.dtype)
        self.full_data_buffer = np.empty((self.channels, 0), dtype=self.dtype)
        self.total_samples_received = 0

    def connect(self, port=None):
        """Connect to the TCP server.

        An optional port can be supplied (e.g. from the GUI port input field).
        Buffers are reset so each new connection starts from a clean state.
        """
        if self.is_connected:
            return

        if port is not None:
            self.port = int(port)

        self.reset_buffers()

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))

        # Non-blocking means recv() will not freeze the GUI if no data is available.
        self.socket.setblocking(False)

        self.is_connected = True

    def disconnect(self):
        """Close the TCP connection."""
        self.is_connected = False

        if self.socket is not None:
            self.socket.close()
            self.socket = None

    def receive_data(self):
        """
        Receive all currently available TCP data.

        TCP is a byte stream. This means one recv() call does not necessarily
        contain exactly one packet. Therefore, we first collect bytes and then
        extract complete packets of the expected size.
        """
        if not self.is_connected or self.socket is None:
            return

        while True:
            try:
                new_bytes = self.socket.recv(4096)

                if not new_bytes:
                    self.disconnect()
                    return

                self.byte_buffer.extend(new_bytes)

            except BlockingIOError:
                # No more data is available right now.
                break

        self._extract_packets_from_buffer()

    def _extract_packets_from_buffer(self):
        """Convert complete byte packets into NumPy arrays."""
        packets = []

        while len(self.byte_buffer) >= self.packet_size_bytes:
            packet_bytes = self.byte_buffer[:self.packet_size_bytes]
            del self.byte_buffer[:self.packet_size_bytes]

            packet = np.frombuffer(packet_bytes, dtype=self.dtype)
            packet = packet.reshape(self.channels, self.samples_per_packet)

            packets.append(packet)

        if len(packets) == 0:
            return

        new_data = np.concatenate(packets, axis=1)

        self.data_buffer = np.concatenate(
            (self.data_buffer, new_data),
            axis=1,
        )

        # Keep the complete history for offline inspection.
        self.full_data_buffer = np.concatenate(
            (self.full_data_buffer, new_data),
            axis=1,
        )

        # Count all received samples.
        # new_data.shape[1] is the number of new samples per channel.
        self.total_samples_received += new_data.shape[1]

        # Keep only the newest 10 seconds for plotting.
        if self.data_buffer.shape[1] > self.window_size:
            self.data_buffer = self.data_buffer[:, -self.window_size:]

    def has_data(self):
        """Return True if enough data is available for plotting."""
        return self.data_buffer.shape[1] >= 2

    def get_window(self):
        """
        Return x and y data for plotting.

        x is a relative time axis for the visible rolling window.
        y is one selected EMG channel.
        """
        y = self.data_buffer[self.selected_channel, :]

        number_of_samples = y.shape[0]
        x = np.arange(number_of_samples) / self.sampling_rate

        return x, y

    def get_all_window(self):
        """
        Return x and y data for all channels in the rolling window.

        x is a relative time axis. y is a 2D array of shape
        (channels, samples) used by the "Plot All Channels" view.
        """
        y = self.data_buffer
        number_of_samples = y.shape[1]
        x = np.arange(number_of_samples) / self.sampling_rate
        return x, y

    def has_full_history(self):
        """Return True if any data was received for offline inspection."""
        return self.full_data_buffer.shape[1] >= 2

    def get_full_history(self):
        """
        Return the complete received signal for offline inspection.

        Returns an absolute time axis and the full (channels, samples) array.
        """
        y = self.full_data_buffer
        number_of_samples = y.shape[1]
        x = np.arange(number_of_samples) / self.sampling_rate
        return x, y

    def get_signal_time_seconds(self):
        """
        Return the signal time in seconds.

        Formula:
            signal_time = total_samples_received / sampling_rate

        This is equivalent to:
            signal_time = number_of_chunks * samples_per_packet / sampling_rate
        """
        return self.total_samples_received / self.sampling_rate
