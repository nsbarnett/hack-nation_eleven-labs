"""Small OS adapters: aggregate idle time and best-effort capture exclusion."""

import ctypes
import sys


def idle_seconds() -> float:
    try:
        if sys.platform == "win32":
            class LastInput(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
            info = LastInput()
            info.cbSize = ctypes.sizeof(info)
            if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
                # Both counters are unsigned 32-bit ticks; subtraction wraps.
                return ((ctypes.windll.kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000
        elif sys.platform == "darwin":
            lib = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
            function = lib.CGEventSourceSecondsSinceLastEventType
            function.argtypes = [ctypes.c_int, ctypes.c_uint32]
            function.restype = ctypes.c_double
            return function(1, 0xFFFFFFFF)
    except (OSError, AttributeError):
        pass
    # Unknown activity must not be interpreted as permission to interrupt.
    return 0.0


def exclude_window(window_id: int) -> bool:
    if sys.platform != "win32":
        return False
    try:
        function = ctypes.windll.user32.SetWindowDisplayAffinity
        function.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        function.restype = ctypes.c_bool
        return function(window_id, 0x11)
    except (OSError, AttributeError):
        return False
