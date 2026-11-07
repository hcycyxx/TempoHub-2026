"""Test the launcher without loading Qt or touching running desktop apps."""

import ast
import os
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]


def load_function(path, name, namespace):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == name)
    exec(compile(ast.Module(body=[function], type_ignores=[]), path, "exec"), namespace)
    return namespace[name]


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.app_dir = Path(self.directory.name)
        self.executable = self.app_dir / "EDIFIER TempoHub.exe"
        self.executable.touch()
        self.launch = Mock()
        self.api_get = Mock(return_value={"running": False})
        self.clock = SimpleNamespace(monotonic=Mock(return_value=0.0), sleep=Mock())
        tree = ast.parse((ROOT / "ui/lyrics_settings.py").read_text(encoding="utf-8"))
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef)
                        and node.name == "ensure_tempo_hub_running")
        namespace = {"APP_DIR": self.app_dir, "api_get": self.api_get,
                     "subprocess": SimpleNamespace(Popen=self.launch), "time": self.clock}
        exec(compile(ast.Module(body=[function], type_ignores=[]),
                     "lyrics_settings.py", "exec"), namespace)
        self.start = namespace[function.name]

    def test_background_api_does_not_skip_normal_hub_launch(self):
        # Reproduce a --startup instance whose API is already reachable.
        self.api_get.side_effect = lambda *a, **kw: (
            self.assertTrue(self.launch.called) or {"running": False})
        self.assertTrue(self.start())
        self.launch.assert_called_once_with(
            [str(self.executable)], cwd=str(self.app_dir), close_fds=True)

    def test_cold_start_waits_for_api(self):
        self.api_get.side_effect = [OSError("not listening"), {"running": True}]
        self.assertTrue(self.start())
        self.assertEqual(self.launch.call_count, 1)
        self.assertEqual(self.api_get.call_count, 2)
        self.clock.sleep.assert_called_once()

    def test_missing_executable_is_a_failure_even_if_api_responds(self):
        self.executable.unlink()
        self.assertFalse(self.start())
        self.launch.assert_not_called()
        self.api_get.assert_not_called()

    def test_launch_failure_is_reported(self):
        self.launch.side_effect = OSError("access denied")
        self.assertFalse(self.start())
        self.api_get.assert_not_called()

    def test_api_timeout_does_not_launch_multiple_hubs(self):
        self.api_get.side_effect = OSError("not listening")
        self.clock.monotonic.side_effect = [0.0, 0.0, 11.0]
        self.assertFalse(self.start())
        self.assertEqual(self.launch.call_count, 1)

    def test_main_only_opens_the_console(self):
        application, window, thread, hub, netease = (Mock() for _ in range(5))
        namespace = {"QApplication": Mock(return_value=application),
                     "SettingsWindow": Mock(return_value=window),
                     "sys": SimpleNamespace(argv=[], exit=Mock()),
                     "threading": SimpleNamespace(Thread=thread),
                     "ensure_tempo_hub_running": hub, "ensure_netease_running": netease}
        load_function("ui/lyrics_settings.py", "main", namespace)()
        window.show.assert_called_once()
        application.exec.assert_called_once()
        thread.assert_not_called()
        hub.assert_not_called()
        netease.assert_not_called()

    def test_netease_launch_does_not_require_hub_or_restart_music(self):
        executable = self.app_dir / "NetEase/CloudMusic/cloudmusic.exe"
        executable.parent.mkdir(parents=True)
        executable.touch()
        process = Mock()
        namespace = {"Path": Path, "os": os, "subprocess": process,
                     "api_post": Mock(side_effect=AssertionError("Hub must not be contacted"))}
        launch = load_function("ui/lyrics_settings.py", "ensure_netease_running", namespace)
        with patch.dict(os.environ, {"ProgramFiles": str(self.app_dir),
                                     "ProgramFiles(x86)": str(self.app_dir)}):
            self.assertTrue(launch())
        self.assertEqual(process.Popen.call_args[0][0],
                         [str(executable), "--remote-debugging-port=9222"])
        process.run.assert_not_called()
        namespace["api_post"].assert_not_called()

    def test_missing_netease_returns_failure_without_launching(self):
        process = Mock()
        launch = load_function("ui/lyrics_settings.py", "ensure_netease_running",
                               {"Path": Path, "os": os, "subprocess": process})
        with patch.dict(os.environ, {"ProgramFiles": str(self.app_dir),
                                     "ProgramFiles(x86)": str(self.app_dir)}):
            self.assertFalse(launch())
        process.Popen.assert_not_called()

    def test_repeated_progress_failures_never_start_or_restart_netease(self):
        class StopWorker(BaseException):
            pass

        launch, process = Mock(), Mock()
        sleep = Mock(side_effect=[None] * 5 + [StopWorker()])
        read = Mock(side_effect=OSError("NetEase is closed"))
        namespace = {"_read_netease_progress": read, "_NETEASE_PROGRESS_LOCK": threading.Lock(),
                     "_NETEASE_PROGRESS": {}, "_log": Mock(), "_ensure_cdp_lyrics": Mock(),
                     "time": SimpleNamespace(sleep=sleep, time=lambda: 60, monotonic=lambda: 60),
                     "_NETEASE_MODULE_STARTED_AT": 0, "_ensure_netease_running_safe": launch,
                     "subprocess": process}
        worker = load_function("src/app/utils/pixel_lyrics_util.py", "_netease_progress_worker", namespace)
        with self.assertRaises(StopWorker):
            worker()
        self.assertGreaterEqual(read.call_count, 3)
        launch.assert_not_called()
        process.Popen.assert_not_called()
        process.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
