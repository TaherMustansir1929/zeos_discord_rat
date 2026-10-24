"""Capture the microphone of the machine.

Windows offers the same microphone under several host APIs and not every
one of them works. The endpoints of WDM-KS open without an error but never
carry any audio, and MME hands out silence while another program holds the
device. The capture therefore prefers WASAPI, skips the silent endpoints
and keeps one stream open that the voice stream and the recorder share.

Discord wants 48kHz stereo audio, so the blocks of the queue always hold
exactly 20 milliseconds, no matter which rate the device records with.
"""

import queue
import threading
import time
from collections.abc import Callable

import numpy as np
import sounddevice as sd

# The sample rate Discord expects.
TARGET_RATE = 48000

# The number of frames of one block, 20ms of 48kHz audio.
FRAMES_PER_BLOCK = 960

# The size of one stereo block of 20ms in bytes.
BLOCK_SIZE = FRAMES_PER_BLOCK * 2 * 2

# The host APIs in the order they are tried. WASAPI shares the device with
# the other programs, MME does not and hands out silence instead.
API_ORDER = ("Windows WASAPI", "Windows DirectSound", "MME", "Windows WDM-KS")

# The endpoints of these APIs open without an error but never carry audio.
SILENT_APIS = ("Windows WDM-KS",)# The time a device is measured while it is looked for.
PROBE_SECONDS = 0.45

# The seconds at the start of a measurement that are skipped. Every driver
# makes a burst of noise when it is opened, a driver that carries no audio
# at all makes the loudest one.
TRANSIENT_SECONDS = 0.15

# The number of devices that are measured before the best one is used.
MAX_PROBED_DEVICES = 8

# The difference between the loud and the quiet part of a measurement from
# which a device clearly carries audio. The search ends as soon as a device
# reaches it.
GOOD_BURST = 50.0

# The difference from which a device counts as a working microphone. Below
# it the room was simply silent, then the quietest device is used.
BURST_THRESHOLD = 2.0

# The device that was picked, the devices are only measured once.
_chosen_device: tuple[int, int, int] | None = None


def host_api_names() -> dict[int, str]:
    """Return the name of every host API by its index."""
    return {
        index: entry["name"] for index, entry in enumerate(sd.query_hostapis())
    }


def candidate_devices() -> list[tuple[int, dict]]:
    """Return the input devices in the order they should be tried.

    The same microphone shows up under every host API, only the best one
    of them is kept so the search does not measure the same hardware
    three times.
    """
    apis = host_api_names()

    try:
        default_name = sd.query_devices(kind="input")["name"].lower()
    except Exception:
        default_name = ""

    candidates: list[tuple[int, int, int, int, dict]] = []
    seen: set[str] = set()

    for index, info in enumerate(sd.query_devices()):
        if info["max_input_channels"] <= 0:
            continue

        api = apis.get(info["hostapi"], "")

        if api in SILENT_APIS:
            continue

        name = info["name"].lower()

        if name in seen:
            continue

        seen.add(name)

        try:
            api_rank = API_ORDER.index(api)
        except ValueError:
            api_rank = len(API_ORDER)

        # The microphone of the system comes first inside its own API.
        device_rank = 0 if name == default_name else 1

        # A device that records with 48kHz needs no resampling.
        rate_rank = 0 if int(info["default_samplerate"]) == TARGET_RATE else 1

        candidates.append((api_rank, device_rank, rate_rank, index, info))

    candidates.sort(key=lambda item: item[:3])

    return [(index, info) for _, _, _, index, info in candidates]


def open_stream(
    callback: Callable, index: int, rate: int, channels: int
) -> sd.RawInputStream:
    """Open an input device and start the capture."""
    stream = sd.RawInputStream(
        device=index,
        samplerate=rate,
        blocksize=FRAMES_PER_BLOCK,
        channels=channels,
        dtype="int16",
        callback=callback,
    )
    # A stream that is not started never calls the callback.
    stream.start()

    return stream


class DeviceLevel:
    """What a microphone delivered while it was measured.

    A microphone that works is quiet and then bursts when somebody talks
    or moves. A broken driver hums all the time without any change. The
    `burst` value is the difference between the loud and the quiet part,
    the `floor` is the noise of the quiet part.
    """

    def __init__(self, floor: float, burst: float) -> None:
        self.floor = floor
        self.burst = burst

    def __str__(self) -> str:
        return f"floor {self.floor:.2f}, burst {self.burst:.2f}"


def measure_device(index: int, rate: int, channels: int) -> DeviceLevel | None:
    """Open a device briefly and describe what it captured.

    Every driver makes a short burst of noise when it is opened, and a
    driver that carries no audio at all makes the loudest one. Those
    first moments are skipped, otherwise a dead microphone would look
    like the best one.

    Returns None when the device could not be opened.
    """
    blocks: list[bytes] = []

    def collect(indata, frames, time_info, status) -> None:
        blocks.append(bytes(indata))

    try:
        stream = open_stream(collect, index, rate, channels)
    except Exception:
        return None

    try:
        time.sleep(PROBE_SECONDS)
    finally:
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass

    if not blocks:
        return DeviceLevel(0.0, 0.0)

    samples = np.frombuffer(b"".join(blocks), dtype=np.int16)

    if samples.size == 0:
        return DeviceLevel(0.0, 0.0)

    # The burst of noise that every driver makes when it opens is skipped.
    skip = int(rate * TRANSIENT_SECONDS)

    if samples.size > skip:
        samples = samples[skip:]

    if samples.size == 0:
        return DeviceLevel(0.0, 0.0)

    # The level of every block of the recording.
    frame_count = max(1, len(samples) // FRAMES_PER_BLOCK)
    usable = samples[: frame_count * FRAMES_PER_BLOCK].reshape(
        frame_count, FRAMES_PER_BLOCK
    )
    levels = np.sqrt(np.mean(np.square(usable.astype(np.float64)), axis=1))

    levels = np.sort(levels)
    quiet = levels[: max(1, len(levels) // 2)]
    loud = levels[max(0, len(levels) - max(1, len(levels) // 4)) :]

    floor = float(np.mean(quiet))
    burst = float(np.mean(loud)) - floor

    return DeviceLevel(floor, burst)


def probe_device(
    index: int, info: dict
) -> tuple[tuple[int, int], DeviceLevel] | None:
    """Return the first working rate and channel count of a device.

    The second value describes what the device delivered while it was
    measured. Returns None when the device cannot be opened at all.
    """
    rates = list(dict.fromkeys([TARGET_RATE, int(info["default_samplerate"])]))
    max_channels = int(info["max_input_channels"])

    # Some endpoints only open with the channel count of the hardware.
    channel_counts = [
        count for count in (1, 2, max_channels) if count <= max_channels
    ]

    for rate in rates:
        for channels in dict.fromkeys(channel_counts):
            level = measure_device(index, rate, channels)

            if level is None:
                continue

            return (rate, channels), level

    return None


def choose_input_device() -> tuple[int, int, int]:
    """Pick the input device that really captures audio.

    Some machines default to a microphone driver that carries no sound at
    all while a second microphone works. Every candidate is measured
    before it is used.

    A microphone that works is quiet and then bursts when somebody talks,
    a broken driver hums all the time without any change. The device
    with the strongest bursts wins. When no device bursts at all, for
    example in a silent room, the quietest one is used, a broken driver
    hums louder than a real microphone does.

    The result is remembered, the devices are only measured once.
    """
    global _chosen_device

    if _chosen_device is not None:
        return _chosen_device

    best: tuple[int, int, int] | None = None
    best_level: DeviceLevel | None = None
    quietest: tuple[int, int, int] | None = None
    quietest_level: DeviceLevel | None = None
    fallback: tuple[int, int, int] | None = None
    errors: list[str] = []
    probed = 0

    for index, info in candidate_devices():
        if probed >= MAX_PROBED_DEVICES:
            break

        result = probe_device(index, info)

        if result is None:
            errors.append(f"{info['name']}: could not be opened")
            continue

        (rate, channels), level = result
        probed += 1

        if fallback is None:
            fallback = (index, rate, channels)

        if best_level is None or level.burst > best_level.burst:
            best_level = level
            best = (index, rate, channels)

        if quietest_level is None or level.floor < quietest_level.floor:
            quietest_level = level
            quietest = (index, rate, channels)

        # A device with a clear signal is good enough, the rest is skipped.
        if level.burst >= GOOD_BURST:
            break

        # The devices are opened one after the other, a short pause keeps
        # the drivers from refusing the next one.
        time.sleep(0.05)

    if best is None or quietest is None or fallback is None:
        raise RuntimeError(
            "No microphone could be opened. " + "; ".join(errors)
        )

    # The bursts tell a working microphone from a broken driver, but only
    # when there is something to hear. In a silent room the quietest
    # device is the one that is not humming.
    chosen = best if best_level.burst >= BURST_THRESHOLD else quietest

    # The driver needs a moment before the device is opened again.
    time.sleep(0.2)

    _chosen_device = chosen
    return chosen


class Resampler:
    """Turns the blocks of a device into blocks of 48kHz."""

    def __init__(self, source_rate: int, target_rate: int = TARGET_RATE) -> None:
        # The number of samples of the device that one sample of the target
        # rate needs.
        self.ratio = source_rate / target_rate
        self.buffer = np.zeros(0, dtype=np.float32)
        self.position = 0.0

    def process(self, samples: np.ndarray) -> np.ndarray:
        """Return the next block of 20ms in 16 bit samples."""
        self.buffer = np.concatenate((self.buffer, samples.astype(np.float32)))

        positions = self.position + np.arange(FRAMES_PER_BLOCK) * self.ratio
        # The positions that reach beyond the buffer are held at its edge,
        # that only happens when the device delivers less than expected.
        clipped = np.clip(positions, 0, max(self.buffer.size - 1, 0))

        if self.buffer.size:
            block = np.interp(clipped, np.arange(self.buffer.size), self.buffer)
        else:
            block = np.zeros(FRAMES_PER_BLOCK, dtype=np.float32)

        # The samples that were used are dropped from the buffer.
        self.position += FRAMES_PER_BLOCK * self.ratio
        consumed = int(self.position)

        if consumed > 0:
            self.buffer = self.buffer[consumed:]
            self.position -= consumed

        return np.round(block).astype(np.int16)


class MicrophoneCapture:
    """Keeps the microphone open and shares the audio with the features."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.blocks: queue.Queue[bytes] = queue.Queue(maxsize=100)
        self.recorded = bytearray()
        self.recording = False
        self.peak = 0
        self.index = -1
        self.rate = TARGET_RATE
        self.channels = 1
        self.resampler = Resampler(TARGET_RATE)
        self.stream: sd.RawInputStream | None = None

        self.open()

    def open(self) -> None:
        """Open the microphone and start the capture."""
        self.index, self.rate, self.channels = choose_input_device()
        self.stream = open_stream(
            self._callback, self.index, self.rate, self.channels
        )
        self.resampler = Resampler(self.rate)

    def _callback(self, indata, frames, time_info, status) -> None:
        """Move a captured block into the queue and into the recording."""
        if status:
            print(f"Microphone status: {status}")

        samples = np.frombuffer(bytes(indata), dtype=np.int16)

        # A microphone with more than one channel only needs the first one.
        if self.channels > 1:
            samples = samples.reshape(-1, self.channels)[:, 0]

        block = self.resampler.process(samples)

        with self.lock:
            if self.recording:
                self.recorded.extend(samples.tobytes())

            if block.size:
                self.peak = max(self.peak, int(np.max(np.abs(block))))

        try:
            self.blocks.put_nowait(np.repeat(block, 2).tobytes())
        except queue.Full:
            # The voice client cannot keep up, the oldest block is dropped.
            pass

    def read_block(self) -> bytes:
        """Return the next block of 20ms of stereo audio."""
        try:
            return self.blocks.get(timeout=1.0)
        except queue.Empty:
            return b"\x00" * BLOCK_SIZE

    def start_recording(self) -> bool:
        """Collect the samples that are captured from now on.

        Returns False when a recording is already running.
        """
        with self.lock:
            if self.recording:
                return False

            self.recorded = bytearray()
            self.recording = True

        return True

    def stop_recording(self) -> np.ndarray:
        """Stop the recording and return the samples that were captured."""
        with self.lock:
            self.recording = False
            data = bytes(self.recorded)
            self.recorded = bytearray()

        return np.frombuffer(data, dtype=np.int16)

    @property
    def level(self) -> int:
        """The loudest sample that was captured so far."""
        return self.peak

    @property
    def name(self) -> str:
        """The name of the microphone that is used."""
        try:
            return str(sd.query_devices(self.index)["name"])
        except Exception:
            return f"device {self.index}"

    def close(self) -> None:
        """Close the microphone."""
        if self.stream is None:
            return

        try:
            self.stream.stop()
            self.stream.close()
        except Exception as exc:
            print(f"Could not close the microphone: {exc}")

        self.stream = None


# The capture that is shared by the voice stream and the recorder.
_capture: MicrophoneCapture | None = None
_capture_lock = threading.Lock()


def ensure_capture() -> MicrophoneCapture:
    """Return the shared capture and open the microphone when needed."""
    global _capture

    with _capture_lock:
        if _capture is None:
            _capture = MicrophoneCapture()

        return _capture


def close_capture() -> None:
    """Close the shared capture."""
    global _capture

    with _capture_lock:
        if _capture is not None:
            _capture.close()
            _capture = None


def current_capture() -> MicrophoneCapture | None:
    """Return the shared capture when the microphone is open."""
    return _capture
