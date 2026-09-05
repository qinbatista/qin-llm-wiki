"""Options for console-free child processes without changing subprocess semantics."""

import copy
import subprocess
import sys


def hidden_process_options(*, creationflags=0, startupinfo=None):
    """Keep Windows console children hidden; leave other platforms unchanged.

    Pass the result to subprocess.run or subprocess.Popen. Streams, timeouts,
    process ownership, and cancellation stay with the caller. GUI programs
    still require their own headless/background mode.
    """
    if sys.platform == "win32":
        incompatible = subprocess.CREATE_NEW_CONSOLE | subprocess.DETACHED_PROCESS
        if creationflags & incompatible:
            raise ValueError("Hidden processes cannot request a new or detached console")
        hidden_startup = copy.copy(startupinfo) if startupinfo is not None else subprocess.STARTUPINFO()
        hidden_startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        hidden_startup.wShowWindow = subprocess.SW_HIDE
        return {
            "creationflags": creationflags | subprocess.CREATE_NO_WINDOW,
            "startupinfo": hidden_startup,
        }
    return {}
