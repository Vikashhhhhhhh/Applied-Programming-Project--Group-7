"""
Signal processing service.

This module belongs to the Model/Service layer of the MVVM structure.
It contains no GUI code and no TCP code. It only transforms signal arrays.

It provides three signal representations required by the project:

- original signal  (unchanged)
- RMS signal       (moving root-mean-square envelope)
- filtered signal  (Butterworth band-pass filter)

All functions work on the last axis of the input array, so they accept
either a single channel (shape: (samples,)) or many channels at once
(shape: (channels, samples)).
"""

import numpy as np
from scipy.signal import butter, filtfilt


# Signal mode identifiers used across the application.
MODE_ORIGINAL = "original"
MODE_RMS = "rms"
MODE_FILTERED = "filtered"

SIGNAL_MODES = (MODE_ORIGINAL, MODE_RMS, MODE_FILTERED)


class SignalProcessor:
    """
    Compute original, RMS and band-pass filtered versions of a signal.

    Default parameters (documented in the README):
    - RMS window:        50 ms moving window
    - Band-pass filter:  4th order Butterworth, 20 Hz - 450 Hz
    """

    def __init__(
        self,
        sampling_rate,
        rms_window_ms=50.0,
        filter_lowcut_hz=20.0,
        filter_highcut_hz=450.0,
        filter_order=4,
    ):
        self.sampling_rate = float(sampling_rate)
        self.rms_window_ms = float(rms_window_ms)
        self.filter_lowcut_hz = float(filter_lowcut_hz)
        self.filter_highcut_hz = float(filter_highcut_hz)
        self.filter_order = int(filter_order)

        self._design_filter()

    def _design_filter(self):
        """Pre-compute the Butterworth band-pass filter coefficients."""
        nyquist = 0.5 * self.sampling_rate

        # Normalised cut-off frequencies must stay inside (0, 1).
        low = self.filter_lowcut_hz / nyquist
        high = self.filter_highcut_hz / nyquist
        low = min(max(low, 1e-4), 0.99)
        high = min(max(high, low + 1e-3), 0.999)

        self._filter_b, self._filter_a = butter(
            self.filter_order, [low, high], btype="band"
        )

    def rms_window_samples(self):
        """Return the RMS moving-window length in samples (at least 1)."""
        return max(1, int(round(self.rms_window_ms * 1e-3 * self.sampling_rate)))

    def apply(self, data, mode):
        """
        Apply the selected signal mode to the data.

        Parameters
        ----------
        data : np.ndarray
            Signal array. The last axis is the time/sample axis.
        mode : str
            One of MODE_ORIGINAL, MODE_RMS, MODE_FILTERED.
        """
        if mode == MODE_RMS:
            return self.compute_rms(data)
        if mode == MODE_FILTERED:
            return self.bandpass_filter(data)
        # Default / MODE_ORIGINAL: return the data unchanged.
        return np.asarray(data, dtype=float)

    def compute_rms(self, data):
        """
        Moving root-mean-square envelope along the last axis.

        RMS is computed as sqrt(moving_average(signal**2)) using a uniform
        window of `rms_window_samples()` samples.
        """
        data = np.asarray(data, dtype=float)
        window = self.rms_window_samples()
        kernel = np.ones(window) / window
        squared = data ** 2

        if data.ndim == 1:
            mean_square = np.convolve(squared, kernel, mode="same")
        else:
            # Convolve each channel (row) independently along the time axis.
            mean_square = np.apply_along_axis(
                lambda row: np.convolve(row, kernel, mode="same"),
                axis=-1,
                arr=squared,
            )

        return np.sqrt(mean_square)

    def bandpass_filter(self, data):
        """
        Zero-phase Butterworth band-pass filter along the last axis.

        filtfilt needs a minimum number of samples. If there are not enough
        samples yet (e.g. right after connecting), the original data is
        returned unchanged so the application never crashes.
        """
        data = np.asarray(data, dtype=float)
        num_samples = data.shape[-1]

        # Minimum length required by filtfilt for the chosen filter.
        min_length = 3 * (max(len(self._filter_a), len(self._filter_b)) - 1)
        if num_samples <= min_length:
            return data

        return filtfilt(self._filter_b, self._filter_a, data, axis=-1)
