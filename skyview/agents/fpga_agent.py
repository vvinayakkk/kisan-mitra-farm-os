import logging
import math
import mmap
import os
import struct
import threading
import time

from skyview.utils.config import get_settings

logger = logging.getLogger(__name__)


class HardwareUnavailable(RuntimeError):
    pass


class RegisterWindow:
    def __init__(self, path: str, base: int, span: int = 0x1000):
        if base < 0 or span < 0x2C:
            raise ValueError("Invalid FPGA register range")
        page = mmap.PAGESIZE
        aligned = base - base % page
        self._delta = base - aligned
        self._span = span
        self._fd = os.open(path, os.O_RDWR | getattr(os, "O_SYNC", 0))
        try:
            self._map = mmap.mmap(
                self._fd,
                self._delta + span,
                access=mmap.ACCESS_WRITE,
                offset=aligned,
            )
        except BaseException:
            os.close(self._fd)
            raise

    def read(self, offset: int) -> int:
        if offset < 0 or offset % 4 or offset + 4 > self._span:
            raise ValueError("Invalid FPGA register offset")
        return struct.unpack_from("<I", self._map, self._delta + offset)[0]

    def write(self, offset: int, value: int) -> None:
        if offset < 0 or offset % 4 or offset + 4 > self._span:
            raise ValueError("Invalid FPGA register offset")
        struct.pack_into("<I", self._map, self._delta + offset, value & 0xFFFFFFFF)

    def close(self) -> None:
        self._map.close()
        os.close(self._fd)


class FPGABridge:
    VERSION = 0x00010000

    def __init__(self, path: str, base: int, timeout_ms: int = 100):
        self._window = RegisterWindow(path, base)
        self._lock = threading.Lock()
        self._timeout = timeout_ms / 1000
        try:
            version = self._window.read(0x24)
            if version != self.VERSION:
                raise HardwareUnavailable(
                    f"FPGA version mismatch: expected 0x{self.VERSION:08x}, got 0x{version:08x}"
                )
        except BaseException:
            self._window.close()
            raise

    def close(self) -> None:
        self._window.close()

    def get_status(self) -> dict:
        try:
            version = self._window.read(0x24)
            return {
                "connected": version == self.VERSION,
                "version": f"0x{version:08x}",
                "register_status": self._window.read(0x04),
            }
        except (OSError, ValueError) as exc:
            return {"connected": False, "error": str(exc)}

    @staticmethod
    def _q88(value: float) -> int:
        if not math.isfinite(value) or not 0 <= value <= 100:
            raise ValueError("FPGA fusion inputs must be between 0 and 100")
        return round(value * 256)

    def send_fusion(self, soil: float, temp: float, humid: float, light: float) -> dict:
        values = [self._q88(v) for v in (soil, temp, humid, light)]
        with self._lock:
            if not self.get_status()["connected"]:
                raise HardwareUnavailable("FPGA register window is unavailable")
            for offset, value in zip((0x08, 0x0C, 0x10, 0x14), values):
                self._window.write(offset, value)
            before = self._window.read(0x20)
            self._window.write(0x00, 1)
            deadline = time.monotonic() + self._timeout
            while time.monotonic() < deadline:
                status = self._window.read(0x04)
                stamp = self._window.read(0x20)
                if (status & 0xF) == 2 and stamp != before:
                    return {
                        "fusion_score": self._window.read(0x18) / 256,
                        "stress_index": self._window.read(0x1C) / 256,
                        "alert_level": (status >> 4) & 0x7,
                        "timestamp": int(time.time() * 1000),
                        "hardware_timestamp_ticks": stamp,
                    }
                time.sleep(0.001)
            raise HardwareUnavailable("FPGA fusion timed out")

    def send_rain_prediction(self, *_args: float) -> dict:
        raise HardwareUnavailable("Rain accelerator is not commissioned through this register map")


class DisconnectedBridge:
    def __init__(self, reason: str):
        self.reason = reason

    def get_status(self) -> dict:
        return {"connected": False, "reason": self.reason}

    def send_fusion(self, *_args: float) -> dict:
        raise HardwareUnavailable(self.reason)

    def send_rain_prediction(self, *_args: float) -> dict:
        raise HardwareUnavailable(self.reason)


_bridge = None
_bridge_lock = threading.Lock()


def get_fpga_bridge():
    global _bridge
    settings = get_settings()
    if not settings.ENABLE_FPGA:
        return DisconnectedBridge("FPGA is disabled")
    with _bridge_lock:
        if isinstance(_bridge, FPGABridge) and _bridge.get_status()["connected"]:
            return _bridge
        if isinstance(_bridge, FPGABridge):
            _bridge.close()
            _bridge = None
        try:
            if not settings.FPGA_MMIO_PATH or settings.FPGA_FUSION_BASE is None:
                raise HardwareUnavailable("FPGA register path and base address are required")
            _bridge = FPGABridge(
                settings.FPGA_MMIO_PATH,
                settings.FPGA_FUSION_BASE,
                settings.FPGA_TIMEOUT_MS,
            )
        except (HardwareUnavailable, OSError, ValueError) as exc:
            logger.warning("FPGA unavailable: %s", exc)
            return DisconnectedBridge(str(exc))
        return _bridge


def is_real_hardware() -> bool:
    return get_fpga_bridge().get_status()["connected"]
