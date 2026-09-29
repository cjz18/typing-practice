"""Accept files dragged onto a Tk window on Windows."""

from __future__ import annotations

import sys
import ctypes
from ctypes import wintypes

WM_DROPFILES = 0x0233
GWLP_WNDPROC = -4


def install_drop(widget, callback, kept: list) -> bool:
    """Call callback with a list of dropped paths. Return False if it cannot be installed."""
    if sys.platform != "win32":
        return False
    try:
        widget.update_idletasks()
        hwnd = widget.winfo_id()
    except Exception:
        return False
    if not hwnd:
        return False

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    result = ctypes.c_ssize_t
    wndproc = ctypes.WINFUNCTYPE(result, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

    user32.GetWindowLongPtrW.restype = ctypes.c_void_p
    user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetWindowLongPtrW.restype = ctypes.c_void_p
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    user32.CallWindowProcW.restype = result
    user32.CallWindowProcW.argtypes = [
        ctypes.c_void_p,
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
    shell32.DragQueryFileW.restype = wintypes.UINT
    shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
    shell32.DragFinish.argtypes = [wintypes.HANDLE]

    previous = user32.GetWindowLongPtrW(hwnd, GWLP_WNDPROC)
    if not previous:
        return False

    def _proc(window, message, wparam, lparam):
        if message == WM_DROPFILES:
            count = shell32.DragQueryFileW(wparam, 0xFFFFFFFF, None, 0)
            paths = []
            for index in range(count):
                size = shell32.DragQueryFileW(wparam, index, None, 0)
                buf = ctypes.create_unicode_buffer(size + 1)
                shell32.DragQueryFileW(wparam, index, buf, size + 1)
                if buf.value:
                    paths.append(buf.value)
            shell32.DragFinish(wparam)
            widget.after(1, lambda found=paths: callback(found))
            return 0
        return user32.CallWindowProcW(previous, window, message, wparam, lparam)

    proc = wndproc(_proc)
    kept.append(proc)
    user32.SetWindowLongPtrW(hwnd, GWLP_WNDPROC, ctypes.cast(proc, ctypes.c_void_p))
    shell32.DragAcceptFiles(hwnd, True)
    return True
