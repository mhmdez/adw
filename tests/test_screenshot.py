"""Tests for the screenshot capture module."""

import os
import platform
import socket
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from adw.utils.screenshot import (
    DEV_SERVER_PATTERNS,
    DEV_SERVER_PORTS,
    capture_screenshot,
    cleanup_old_screenshots,
    detect_dev_server_ports,
    extract_port_from_command,
    get_dev_server_url,
    get_screenshots_dir,
    is_dev_server_command,
    is_dev_server_running,
    is_macos,
    list_screenshots,
)


class TestIsMacos:
    """Tests for is_macos()."""

    def test_returns_bool(self):
        """Should return a boolean."""
        result = is_macos()
        assert isinstance(result, bool)

    @patch("platform.system")
    def test_darwin_is_macos(self, mock_system):
        """Should return True for Darwin."""
        mock_system.return_value = "Darwin"
        assert is_macos() is True

    @patch("platform.system")
    def test_linux_is_not_macos(self, mock_system):
        """Should return False for Linux."""
        mock_system.return_value = "Linux"
        assert is_macos() is False

    @patch("platform.system")
    def test_windows_is_not_macos(self, mock_system):
        """Should return False for Windows."""
        mock_system.return_value = "Windows"
        assert is_macos() is False


class TestIsDevServerCommand:
    """Tests for is_dev_server_command()."""

    def test_empty_command(self):
        """Should return False for empty command."""
        assert is_dev_server_command("") is False
        assert is_dev_server_command(None) is False

    @pytest.mark.parametrize("command", [
        "npm run dev",
        "npm start",
        "bun run dev",
        "bun dev",
        "pnpm dev",
        "pnpm run dev",
        "yarn dev",
        "yarn run dev",
        "vite",
        "next dev",
        "nuxt dev",
        "python -m http.server",
        "uvicorn main:app",
        "flask run",
        "gunicorn app:app",
        "fastapi dev",
        "php -S localhost:8000",
        "ng serve",
    ])
    def test_recognizes_dev_server_commands(self, command):
        """Should recognize common dev server commands."""
        assert is_dev_server_command(command) is True

    @pytest.mark.parametrize("command", [
        "npm install",
        "npm test",
        "git status",
        "ls -la",
        "python script.py",
        "echo hello",
        "cd /path/to/dir",
    ])
    def test_rejects_non_dev_server_commands(self, command):
        """Should reject non-dev server commands."""
        assert is_dev_server_command(command) is False

    def test_case_insensitive(self):
        """Should match commands case-insensitively."""
        assert is_dev_server_command("NPM RUN DEV") is True
        assert is_dev_server_command("Npm Run Dev") is True


class TestExtractPortFromCommand:
    """Tests for extract_port_from_command()."""

    @pytest.mark.parametrize("command,expected", [
        ("npm run dev --port 3001", 3001),
        ("npm run dev --port=3001", 3001),
        ("npm run dev -p 5173", 5173),
        ("npm run dev -p=5173", 5173),
        ("python -m http.server 8000", 8000),
        ("PORT=4000 npm start", 4000),
        ("localhost:8080", 8080),
    ])
    def test_extracts_port_correctly(self, command, expected):
        """Should extract port from various command formats."""
        assert extract_port_from_command(command) == expected

    def test_returns_none_for_no_port(self):
        """Should return None when no port found."""
        assert extract_port_from_command("npm run dev") is None
        assert extract_port_from_command("vite") is None

    def test_rejects_invalid_ports(self):
        """Should reject ports outside valid range."""
        # Port too low
        assert extract_port_from_command("--port 80") is None
        # Port too high
        assert extract_port_from_command("--port 70000") is None


class TestGetDevServerUrl:
    """Tests for get_dev_server_url()."""

    def test_default_http(self):
        """Should use http by default."""
        assert get_dev_server_url(3000) == "http://localhost:3000"

    def test_custom_protocol(self):
        """Should support custom protocol."""
        assert get_dev_server_url(3000, "https") == "https://localhost:3000"

    def test_various_ports(self):
        """Should work with various ports."""
        assert get_dev_server_url(5173) == "http://localhost:5173"
        assert get_dev_server_url(8000) == "http://localhost:8000"
        assert get_dev_server_url(8080) == "http://localhost:8080"


class TestIsDevServerRunning:
    """Tests for is_dev_server_running()."""

    def test_closed_port_returns_false(self):
        """Should return False for a closed port."""
        # Use a random high port that's unlikely to be in use
        assert is_dev_server_running(65432) is False

    @patch("socket.socket")
    def test_open_port_returns_true(self, mock_socket_class):
        """Should return True when connection succeeds."""
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 0
        mock_socket_class.return_value = mock_socket

        assert is_dev_server_running(3000) is True
        mock_socket.connect_ex.assert_called_with(("127.0.0.1", 3000))


class TestDetectDevServerPorts:
    """Tests for detect_dev_server_ports()."""

    @patch("adw.utils.screenshot.is_dev_server_running")
    def test_returns_running_ports(self, mock_is_running):
        """Should return list of ports with running servers."""
        mock_is_running.side_effect = lambda p: p in [3000, 5173]

        result = detect_dev_server_ports()

        assert 3000 in result
        assert 5173 in result
        assert 8000 not in result

    @patch("adw.utils.screenshot.is_dev_server_running")
    def test_returns_empty_when_none_running(self, mock_is_running):
        """Should return empty list when no servers running."""
        mock_is_running.return_value = False

        result = detect_dev_server_ports()

        assert result == []


class TestGetScreenshotsDir:
    """Tests for get_screenshots_dir()."""

    def test_creates_directory(self, tmp_path):
        """Should create directory if it doesn't exist."""
        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            result = get_screenshots_dir()

            assert result.exists()
            assert result.is_dir()
            assert result == tmp_path / ".adw" / "screenshots"

    def test_task_specific_directory(self, tmp_path):
        """Should create task-specific directory when task_id provided."""
        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            result = get_screenshots_dir("abc12345")

            assert result.exists()
            assert result == tmp_path / "agents" / "abc12345" / "screenshots"


class TestCaptureScreenshot:
    """Tests for capture_screenshot()."""

    @patch("adw.utils.screenshot.is_macos")
    def test_raises_on_non_macos(self, mock_is_macos):
        """Should raise RuntimeError on non-macOS."""
        mock_is_macos.return_value = False

        with pytest.raises(RuntimeError, match="only supported on macOS"):
            capture_screenshot()

    @patch("adw.utils.screenshot.is_macos")
    @patch("subprocess.run")
    def test_builds_correct_command(self, mock_run, mock_is_macos, tmp_path):
        """Should build correct screencapture command."""
        mock_is_macos.return_value = True
        mock_run.return_value = MagicMock(returncode=0)
        output_path = tmp_path / "test.png"

        # Create the file to simulate successful capture
        output_path.touch()

        result = capture_screenshot(output_path=output_path)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "screencapture" in cmd
        assert "-x" in cmd  # Silent flag
        assert str(output_path) in cmd

    @patch("adw.utils.screenshot.is_macos")
    @patch("subprocess.run")
    def test_includes_region_flags(self, mock_run, mock_is_macos, tmp_path):
        """Should include region flags when specified."""
        mock_is_macos.return_value = True
        mock_run.return_value = MagicMock(returncode=0)
        output_path = tmp_path / "test.png"
        output_path.touch()

        capture_screenshot(output_path=output_path, region=(100, 100, 800, 600))

        cmd = mock_run.call_args[0][0]
        assert "-R" in cmd
        assert "100,100,800,600" in cmd

    @patch("adw.utils.screenshot.is_macos")
    @patch("subprocess.run")
    def test_handles_failure(self, mock_run, mock_is_macos):
        """Should raise RuntimeError on screencapture failure."""
        mock_is_macos.return_value = True
        mock_run.return_value = MagicMock(returncode=1, stderr="error")

        with pytest.raises(RuntimeError, match="screencapture failed"):
            capture_screenshot()


class TestListScreenshots:
    """Tests for list_screenshots()."""

    def test_empty_directory(self, tmp_path):
        """Should return empty list for empty directory."""
        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            result = list_screenshots()
            assert result == []

    def test_finds_screenshots(self, tmp_path):
        """Should find screenshot files."""
        screenshots_dir = tmp_path / ".adw" / "screenshots"
        screenshots_dir.mkdir(parents=True)

        # Create test files
        (screenshots_dir / "screenshot-20260101_120000.png").touch()
        (screenshots_dir / "screenshot-20260102_120000.png").touch()
        (screenshots_dir / "other_file.txt").touch()  # Should be ignored

        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            result = list_screenshots()

            assert len(result) == 2
            assert all("screenshot-" in p.name for p in result)

    def test_sorted_by_mtime(self, tmp_path):
        """Should sort by modification time, newest first."""
        screenshots_dir = tmp_path / ".adw" / "screenshots"
        screenshots_dir.mkdir(parents=True)

        # Create files with different times
        older = screenshots_dir / "screenshot-older.png"
        newer = screenshots_dir / "screenshot-newer.png"
        older.touch()
        newer.touch()

        # Ensure newer has later mtime
        import time
        time.sleep(0.1)
        newer.touch()

        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            result = list_screenshots()

            assert result[0].name == "screenshot-newer.png"


class TestCleanupOldScreenshots:
    """Tests for cleanup_old_screenshots()."""

    def test_removes_old_files(self, tmp_path):
        """Should remove files older than max_age_days."""
        screenshots_dir = tmp_path / ".adw" / "screenshots"
        screenshots_dir.mkdir(parents=True)

        old_file = screenshots_dir / "screenshot-old.png"
        old_file.touch()

        # Make file appear old by modifying mtime
        old_time = (datetime.now() - timedelta(days=10)).timestamp()
        os.utime(old_file, (old_time, old_time))

        new_file = screenshots_dir / "screenshot-new.png"
        new_file.touch()

        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            deleted = cleanup_old_screenshots(max_age_days=7)

            assert deleted == 1
            assert not old_file.exists()
            assert new_file.exists()

    def test_returns_count(self, tmp_path):
        """Should return count of deleted files."""
        screenshots_dir = tmp_path / ".adw" / "screenshots"
        screenshots_dir.mkdir(parents=True)

        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            deleted = cleanup_old_screenshots()
            assert deleted == 0


class TestDevServerPatterns:
    """Tests for DEV_SERVER_PATTERNS constant."""

    def test_patterns_are_valid_regex(self):
        """Should have valid regex patterns."""
        import re
        for pattern in DEV_SERVER_PATTERNS:
            try:
                re.compile(pattern)
            except re.error as e:
                pytest.fail(f"Invalid regex pattern: {pattern} - {e}")


class TestDevServerPorts:
    """Tests for DEV_SERVER_PORTS constant."""

    def test_contains_common_ports(self):
        """Should contain common dev server ports."""
        assert 3000 in DEV_SERVER_PORTS  # React, Next.js default
        assert 5173 in DEV_SERVER_PORTS  # Vite default
        assert 8000 in DEV_SERVER_PORTS  # Python http.server, Django
        assert 8080 in DEV_SERVER_PORTS  # Common alternative

    def test_all_valid_ports(self):
        """Should only contain valid port numbers."""
        for port in DEV_SERVER_PORTS:
            assert 1024 <= port <= 65535
