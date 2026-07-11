"""Python ↔ Arduino serial bridge, with a transparent mock mode.

PROTOCOL (Python → Arduino)
    "A <m> <steps> <dir> <speed>\\n"   move motor m by <steps> steps in <dir>
                                       (+1/-1) at <speed> steps/sec (angle/steps)
    "R <m> <dir> <speed>\\n"           run motor m continuously (speed mode)
    "S <m>\\n"                          stop motor m
    "X\\n"                              stop ALL motors (emergency)
    "P\\n"                              ping

Arduino → Python
    "R\\n" ready   "A\\n" ack   "D <m>\\n" done (motor m finished a move)   "O\\n" pong

If no Arduino is found we drop into MOCK MODE: commands are logged and move
completions are simulated on a timer, so the UI behaves identically without
hardware.
"""

import threading
import queue
import time

from config import (
    SERIAL_PORT,
    SERIAL_BAUD,
    SERIAL_AUTODETECT_PATTERNS,
    MIN_SPEED,
    MAX_SPEED,
)

try:
    import serial
    import serial.tools.list_ports as list_ports
    _HAVE_PYSERIAL = True
except ImportError:      # pragma: no cover - pyserial optional for pure mock
    _HAVE_PYSERIAL = False


def _clamp_speed(speed):
    return max(MIN_SPEED, min(MAX_SPEED, int(speed)))


class SerialController:
    def __init__(self):
        self._serial = None
        self._connected = False
        self._mock = True
        self._connecting = False

        self._done_events = queue.Queue()      # motor indices that finished a move
        self._write_queue = queue.Queue()      # outgoing command strings
        self._mock_timers = []                 # (deadline, motor_index) for mock completion
        self._lock = threading.Lock()
        self._stop_threads = threading.Event()
        self._reader = None
        self._writer = None

    # ── connection ─────────────────────────────────────────────────────────
    def connect_async(self):
        """Connect on a background thread so the UI never blocks on the serial
        handshake (which can take up to 5s). Until it resolves, status is
        'Connecting…' and commands go to mock."""
        self._connecting = True

        def _worker():
            try:
                self.connect()
            finally:
                self._connecting = False

        threading.Thread(target=_worker, daemon=True).start()

    def connect(self):
        """Try to open the Arduino; fall back to mock mode. Returns True if real."""
        if not _HAVE_PYSERIAL:
            self._enter_mock("pyserial not installed")
            return False

        port = SERIAL_PORT or self._autodetect_port()
        if port is None:
            self._enter_mock("no serial port found")
            return False

        try:
            self._serial = serial.Serial(port, SERIAL_BAUD, timeout=0.1)
        except Exception as exc:      # pragma: no cover - hardware dependent
            self._enter_mock(f"open failed on {port}: {exc}")
            return False

        # Wait up to 5s for the firmware's "R" ready line.
        deadline = time.time() + 5.0
        ready = False
        while time.time() < deadline:
            line = self._serial.readline().decode(errors="ignore").strip()
            if line == "R":
                ready = True
                break
        if not ready:
            self._serial.close()
            self._serial = None
            self._enter_mock(f"no ready handshake on {port}")
            return False

        self._connected = True
        self._mock = False
        self._start_threads()
        print(f"[SERIAL] Connected on {port} @ {SERIAL_BAUD}")
        return True

    def _autodetect_port(self):
        for p in list_ports.comports():
            name = (p.device or "").lower() + " " + (p.description or "").lower()
            if any(pat.lower() in name for pat in SERIAL_AUTODETECT_PATTERNS):
                # Skip debug/console ports.
                if "debug" in name or "console" in name:
                    continue
                return p.device
        return None

    def _enter_mock(self, reason):
        self._mock = True
        self._connected = False
        print(f"[MOCK] Mock mode — {reason}")

    def _start_threads(self):
        self._stop_threads.clear()
        self._writer = threading.Thread(target=self._write_loop, daemon=True)
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._writer.start()
        self._reader.start()

    # ── background threads (real serial only) ───────────────────────────────
    def _write_loop(self):
        while not self._stop_threads.is_set():
            try:
                cmd = self._write_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                if self._serial:
                    self._serial.write(cmd.encode())
            except Exception as exc:      # pragma: no cover - hardware dependent
                if self._stop_threads.is_set():
                    break               # benign: we're shutting down
                print(f"[SERIAL] write error: {exc}; dropping to mock")
                self._enter_mock("write error")

    def _read_loop(self):
        while not self._stop_threads.is_set():
            try:
                if not self._serial:
                    break
                line = self._serial.readline().decode(errors="ignore").strip()
            except Exception as exc:      # pragma: no cover - hardware dependent
                if self._stop_threads.is_set():
                    break               # benign: we're shutting down
                print(f"[SERIAL] read error: {exc}; dropping to mock")
                self._enter_mock("read error")
                break
            if not line:
                continue
            if line.startswith("D"):
                parts = line.split()
                if len(parts) == 2 and parts[1].isdigit():
                    self._done_events.put(int(parts[1]))

    # ── status ───────────────────────────────────────────────────────────
    def is_connected(self):
        return self._connected and not self._mock

    def status_text(self):
        if self._connecting:
            return "Connecting…"
        return "Connected" if self.is_connected() else "Mock mode"

    # ── commands ───────────────────────────────────────────────────────────
    def _send(self, cmd):
        if self._mock:
            print(f"[MOCK] {cmd.strip()}")
        else:
            self._write_queue.put(cmd)

    def move(self, m, steps, direction, speed):
        speed = _clamp_speed(speed)
        self._send(f"A {m} {steps} {direction} {speed}\n")
        if self._mock:
            duration = steps / float(speed) if speed else 0.0
            with self._lock:
                self._mock_timers.append((time.time() + duration, m))

    def run(self, m, direction, speed):
        speed = _clamp_speed(speed)
        self._send(f"R {m} {direction} {speed}\n")
        # Continuous run: no completion event (in mock or real).

    def stop(self, m):
        self._send(f"S {m}\n")
        if self._mock:
            self._cancel_mock_timers(m)

    def stop_all(self):
        self._send("X\n")
        if self._mock:
            with self._lock:
                self._mock_timers.clear()

    def ping(self):
        self._send("P\n")

    def _cancel_mock_timers(self, m):
        with self._lock:
            self._mock_timers = [t for t in self._mock_timers if t[1] != m]

    # ── per-frame pump ───────────────────────────────────────────────────
    def poll(self):
        """Call each frame. Returns a list of motor indices that just finished."""
        done = []

        # Mock completions on a timer.
        if self._mock:
            now = time.time()
            with self._lock:
                fired = [t for t in self._mock_timers if t[0] <= now]
                self._mock_timers = [t for t in self._mock_timers if t[0] > now]
            done.extend(m for _, m in fired)

        # Real completions from the read thread.
        while True:
            try:
                done.append(self._done_events.get_nowait())
            except queue.Empty:
                break
        return done

    def close(self):
        # Stop the threads and let them exit their current read/write BEFORE we
        # close the port, so shutdown doesn't race into "bad file descriptor".
        self._stop_threads.set()
        for th in (self._writer, self._reader):
            if th is not None and th.is_alive():
                th.join(timeout=0.6)
        try:
            if self._serial:
                self._serial.close()
        except Exception:
            pass
        self._serial = None
