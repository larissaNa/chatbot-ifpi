"""
Buffer de logs em memória: intercepta sys.stdout para capturar todos os
prints do sistema e disponibilizá-los via rota admin sem acesso ao Docker CLI.
"""

import sys
import threading
from collections import deque
from datetime import datetime

_MAX_LINES = 2000
_buffer: deque[str] = deque(maxlen=_MAX_LINES)
_lock = threading.Lock()
_installed = False


class _LogInterceptor:
    def __init__(self, original):
        self._original = original

    def write(self, text: str):
        self._original.write(text)
        text = text.rstrip("\n")
        if text:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            line = f"[{ts}] {text}"
            with _lock:
                _buffer.append(line)

    def flush(self):
        self._original.flush()

    def fileno(self):
        return self._original.fileno()

    def isatty(self):
        return False


def install():
    global _installed
    if _installed:
        return
    sys.stdout = _LogInterceptor(sys.stdout)
    _installed = True


def get_lines(n: int = _MAX_LINES) -> list[str]:
    with _lock:
        lines = list(_buffer)
    return lines[-n:] if n < len(lines) else lines


def clear():
    with _lock:
        _buffer.clear()
