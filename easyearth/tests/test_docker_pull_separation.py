"""Tests for the separated docker pull / docker run logic in plugin.py."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch, call, PropertyMock

# Ensure project root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Stub out QGIS / PyQt modules so the plugin can be imported without QGIS
_qgis_mods = [
    'qgis', 'qgis.core', 'qgis.gui', 'qgis.utils',
    'qgis.PyQt', 'qgis.PyQt.QtWidgets', 'qgis.PyQt.QtCore', 'qgis.PyQt.QtGui',
    'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets',
    'PyQt5.QtNetwork', 'PyQt5.QtXml',
    'easyearth_plugin.core',
]
for _mod in _qgis_mods:
    sys.modules.setdefault(_mod, MagicMock())

from easyearth_plugin.plugin import EasyEarthPlugin


def _make_plugin():
    """Create a minimally initialised EasyEarthPlugin with mocked QGIS deps."""
    iface = MagicMock()
    with patch.object(EasyEarthPlugin, '__init__', lambda self, _iface: None):
        plugin = EasyEarthPlugin(iface)

    # Set the attributes that docker_pull / docker_run / start_server use
    plugin.iface = iface
    plugin.docker_path = 'docker'
    plugin.docker_hub_image_name = 'maverickmiaow/easyearth'
    plugin.docker_running = False
    plugin.base_dir = '/tmp/easyearth_base'
    plugin.cache_dir = '/tmp/easyearth_cache'
    plugin.docker_mode_button = MagicMock()
    plugin.docker_mode_button.isChecked.return_value = True
    plugin.local_mode_button = MagicMock()
    plugin.local_mode_button.isChecked.return_value = False
    return plugin


class TestDockerPullCalledBeforeRun(unittest.TestCase):
    """docker pull must finish successfully before docker run is invoked."""

    @patch('easyearth_plugin.plugin.subprocess.run')
    def test_pull_called_before_run(self, mock_run):
        """Verify the ordering: rm -> pull -> run."""
        plugin = _make_plugin()

        # All subprocess calls succeed
        mock_run.return_value = MagicMock(returncode=0, stdout='Pulling from ...', stderr='')

        plugin.start_server()

        # Collect the first arg of each subprocess.run call
        commands = [c[0][0] for c in mock_run.call_args_list]

        # Find the pull and run calls
        pull_indices = [i for i, cmd in enumerate(commands) if 'pull' in cmd]
        run_indices = [i for i, cmd in enumerate(commands) if 'run' in cmd]

        self.assertTrue(len(pull_indices) > 0, "docker pull was not called")
        self.assertTrue(len(run_indices) > 0, "docker run was not called")
        self.assertLess(pull_indices[0], run_indices[0],
                        "docker pull must be called before docker run")


class TestDockerPullFailure(unittest.TestCase):
    """When docker pull fails, docker run must NOT be called."""

    @patch('easyearth_plugin.plugin.subprocess.run')
    def test_run_not_called_when_pull_fails(self, mock_run):
        plugin = _make_plugin()

        def side_effect(cmd, **kwargs):
            result = MagicMock()
            if 'pull' in cmd:
                result.returncode = 1
                result.stdout = ''
                result.stderr = 'Error: pull access denied'
            else:
                result.returncode = 0
                result.stdout = ''
                result.stderr = ''
            return result

        mock_run.side_effect = side_effect

        plugin.start_server()

        commands = [c[0][0] for c in mock_run.call_args_list]
        run_calls = [cmd for cmd in commands if 'run' in cmd]
        self.assertEqual(len(run_calls), 0,
                         "docker run should not be called when pull fails")

    @patch('easyearth_plugin.plugin.subprocess.run')
    def test_critical_message_on_pull_failure(self, mock_run):
        plugin = _make_plugin()

        def side_effect(cmd, **kwargs):
            result = MagicMock()
            if 'pull' in cmd:
                result.returncode = 1
                result.stdout = ''
                result.stderr = 'network error'
            else:
                result.returncode = 0
                result.stdout = ''
                result.stderr = ''
            return result

        mock_run.side_effect = side_effect

        plugin.start_server()

        # Gather all pushMessage calls
        messages = [c[0][0] for c in plugin.iface.messageBar().pushMessage.call_args_list]
        critical_msgs = [m for m in messages if 'failed' in m.lower() or 'aborting' in m.lower()]
        self.assertTrue(len(critical_msgs) > 0,
                        "A critical/failure message should be shown when pull fails")


class TestDockerPullImageUpToDate(unittest.TestCase):
    """When the image is already up to date, an informational message is shown."""

    @patch('easyearth_plugin.plugin.subprocess.run')
    def test_up_to_date_message(self, mock_run):
        plugin = _make_plugin()

        def side_effect(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stderr = ''
            if 'pull' in cmd:
                result.stdout = 'Status: Image is up to date for maverickmiaow/easyearth:latest'
            else:
                result.stdout = ''
            return result

        mock_run.side_effect = side_effect

        plugin.start_server()

        messages = [c[0][0] for c in plugin.iface.messageBar().pushMessage.call_args_list]
        up_to_date = [m for m in messages if 'up to date' in m.lower()]
        self.assertTrue(len(up_to_date) > 0,
                        "An 'up to date' message should be shown when image is current")


class TestDockerPullNewImage(unittest.TestCase):
    """When a new image is downloaded, a success message is shown."""

    @patch('easyearth_plugin.plugin.subprocess.run')
    def test_new_image_message(self, mock_run):
        plugin = _make_plugin()

        def side_effect(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stderr = ''
            if 'pull' in cmd:
                result.stdout = 'Status: Downloaded newer image for maverickmiaow/easyearth:latest'
            else:
                result.stdout = ''
            return result

        mock_run.side_effect = side_effect

        plugin.start_server()

        messages = [c[0][0] for c in plugin.iface.messageBar().pushMessage.call_args_list]
        download_msgs = [m for m in messages if 'downloaded' in m.lower() or 'new' in m.lower()]
        self.assertTrue(len(download_msgs) > 0,
                        "A success message should be shown when a new image is downloaded")


class TestDockerPullUsesListArgs(unittest.TestCase):
    """subprocess calls must use list-based args (no shell=True)."""

    @patch('easyearth_plugin.plugin.subprocess.run')
    def test_pull_uses_list_args(self, mock_run):
        plugin = _make_plugin()
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')

        plugin.docker_pull()

        pull_call = mock_run.call_args_list[0]
        cmd_arg = pull_call[0][0]
        self.assertIsInstance(cmd_arg, list,
                              "docker pull should use a list of args, not a string")
        # shell=True should NOT be in kwargs
        self.assertFalse(pull_call[1].get('shell', False),
                         "docker pull must not use shell=True")

    @patch('easyearth_plugin.plugin.subprocess.run')
    def test_run_uses_list_args(self, mock_run):
        plugin = _make_plugin()
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')

        plugin.docker_run()

        run_call = mock_run.call_args_list[0]
        cmd_arg = run_call[0][0]
        self.assertIsInstance(cmd_arg, list,
                              "docker run should use a list of args, not a string")
        self.assertFalse(run_call[1].get('shell', False),
                         "docker run must not use shell=True")


if __name__ == '__main__':
    unittest.main()
