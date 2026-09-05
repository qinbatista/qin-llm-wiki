import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "hidden_process.py"
SPEC = importlib.util.spec_from_file_location("hidden_process_under_test", SCRIPT)
hidden_process = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hidden_process)


class FakeStartupInfo:
    def __init__(self):
        self.dwFlags = 0
        self.wShowWindow = 1
        self.hStdInput = None
        self.hStdOutput = None
        self.hStdError = None
        self.lpAttributeList = None


WINDOWS_API = SimpleNamespace(
    CREATE_NO_WINDOW=0x08000000,
    CREATE_NEW_CONSOLE=0x00000010,
    DETACHED_PROCESS=0x00000008,
    CREATE_NEW_PROCESS_GROUP=0x00000200,
    STARTF_USESHOWWINDOW=0x00000001,
    STARTF_USESTDHANDLES=0x00000100,
    SW_HIDE=0,
    STARTUPINFO=FakeStartupInfo,
)


class HiddenProcessOptionsTests(unittest.TestCase):
    def windows_options(self, **options):
        with patch.object(hidden_process, "sys", SimpleNamespace(platform="win32")), patch.object(hidden_process, "subprocess", WINDOWS_API):
            return hidden_process.hidden_process_options(**options)

    def test_windows_creates_hidden_console_options(self):
        options = self.windows_options()
        self.assertEqual(options["creationflags"], WINDOWS_API.CREATE_NO_WINDOW)
        self.assertEqual(options["startupinfo"].dwFlags, WINDOWS_API.STARTF_USESHOWWINDOW)
        self.assertEqual(options["startupinfo"].wShowWindow, WINDOWS_API.SW_HIDE)

    def test_windows_preserves_compatible_flags_and_caller_startup(self):
        startup = FakeStartupInfo()
        startup.dwFlags = WINDOWS_API.STARTF_USESTDHANDLES
        startup.hStdInput, startup.hStdOutput, startup.hStdError = 11, 22, 33
        startup.lpAttributeList = {"handle_list": [44]}
        flags = WINDOWS_API.CREATE_NEW_PROCESS_GROUP | 0x00004000
        options = self.windows_options(creationflags=flags, startupinfo=startup)
        copied = options["startupinfo"]
        self.assertIsNot(copied, startup)
        self.assertEqual(options["creationflags"], flags | WINDOWS_API.CREATE_NO_WINDOW)
        self.assertEqual(copied.dwFlags, WINDOWS_API.STARTF_USESTDHANDLES | WINDOWS_API.STARTF_USESHOWWINDOW)
        self.assertEqual((copied.hStdInput, copied.hStdOutput, copied.hStdError), (11, 22, 33))
        self.assertEqual(copied.lpAttributeList, {"handle_list": [44]})
        self.assertEqual(startup.dwFlags, WINDOWS_API.STARTF_USESTDHANDLES)
        self.assertEqual(startup.wShowWindow, 1)

    def test_windows_rejects_flags_that_disable_no_window(self):
        for flags in (WINDOWS_API.CREATE_NEW_CONSOLE, WINDOWS_API.DETACHED_PROCESS, WINDOWS_API.CREATE_NEW_CONSOLE | WINDOWS_API.CREATE_NEW_PROCESS_GROUP):
            with self.subTest(flags=flags), self.assertRaisesRegex(ValueError, "new or detached console"):
                self.windows_options(creationflags=flags)

    def test_repeated_calls_do_not_share_startup_state(self):
        first = self.windows_options()
        second = self.windows_options()
        self.assertIsNot(first["startupinfo"], second["startupinfo"])

    def test_macos_linux_do_not_touch_windows_api_or_forward_windows_options(self):
        for platform in ("darwin", "linux"):
            with self.subTest(platform=platform), patch.object(hidden_process, "sys", SimpleNamespace(platform=platform)), patch.object(hidden_process, "subprocess", SimpleNamespace()):
                self.assertEqual(hidden_process.hidden_process_options(creationflags=WINDOWS_API.CREATE_NEW_PROCESS_GROUP, startupinfo=FakeStartupInfo()), {})


class HiddenProcessRuntimeTests(unittest.TestCase):
    def test_unicode_arguments_and_both_streams_are_preserved(self):
        argument = "folder with spaces/设计 & $(literal)"
        source = "import json, sys; print(json.dumps(sys.argv[1:])); print('diagnostic', file=sys.stderr)"
        result = subprocess.run(
            [sys.executable, "-B", "-c", source, argument],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
            shell=False,
            **hidden_process.hidden_process_options(),
        )
        self.assertEqual(json.loads(result.stdout), [argument])
        self.assertEqual(result.stderr.strip(), "diagnostic")

    def test_nonzero_status_and_check_error_are_preserved(self):
        command = [sys.executable, "-B", "-c", "import sys; print('failed'); sys.exit(7)"]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10, **hidden_process.hidden_process_options())
        self.assertEqual(result.returncode, 7)
        with self.assertRaises(subprocess.CalledProcessError) as captured:
            subprocess.run(command, capture_output=True, text=True, timeout=10, check=True, **hidden_process.hidden_process_options())
        self.assertEqual(captured.exception.returncode, 7)
        self.assertEqual(captured.exception.stdout.strip(), "failed")

    def test_timeout_remains_a_timeout(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            subprocess.run(
                [sys.executable, "-B", "-c", "import time; time.sleep(5)"],
                capture_output=True,
                timeout=0.2,
                **hidden_process.hidden_process_options(),
            )

    def test_popen_preserves_stdin_and_explicit_lifecycle(self):
        with subprocess.Popen(
            [sys.executable, "-B", "-c", "import sys; sys.stdout.write(sys.stdin.read().upper())"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            **hidden_process.hidden_process_options(),
        ) as process:
            stdout, stderr = process.communicate("bounded input", timeout=10)
        self.assertEqual((process.returncode, stdout, stderr), (0, "BOUNDED INPUT", ""))

    @unittest.skipUnless(sys.platform == "win32", "requires native Windows console API")
    def test_native_windows_child_has_no_console_window(self):
        source = "import ctypes, json; kernel = ctypes.WinDLL('kernel32', use_last_error=True); kernel.GetConsoleWindow.restype = ctypes.c_void_p; print(json.dumps({'console_window': kernel.GetConsoleWindow()}))"
        result = subprocess.run(
            [sys.executable, "-B", "-c", source],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
            **hidden_process.hidden_process_options(),
        )
        self.assertIsNone(json.loads(result.stdout)["console_window"])


if __name__ == "__main__":
    unittest.main()
