"""Tests for Claude Code hook guardrails.

These tests verify that the safety guardrails in pre_tool_use.py
correctly block dangerous commands and sensitive file access.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the guardrail functions from the hook script
# We need to add the .claude/hooks directory to the path
HOOKS_DIR = Path(__file__).parent.parent / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))


class TestDangerousCommandDetection:
    """Tests for dangerous command detection patterns."""

    @pytest.fixture
    def hook_module(self):
        """Import the pre_tool_use module."""
        # Import fresh each time to avoid state issues
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "pre_tool_use",
            HOOKS_DIR / "pre_tool_use.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_block_rm_rf_root(self, hook_module):
        """Test blocking rm -rf /."""
        is_dangerous, reason = hook_module.is_dangerous_command("rm -rf /")
        assert is_dangerous is True
        assert "dangerous" in reason.lower() or "pattern" in reason.lower()

    def test_block_rm_rf_home(self, hook_module):
        """Test blocking rm -rf ~."""
        is_dangerous, reason = hook_module.is_dangerous_command("rm -rf ~")
        assert is_dangerous is True

    def test_block_rm_rf_all(self, hook_module):
        """Test blocking rm -rf *."""
        is_dangerous, reason = hook_module.is_dangerous_command("rm -rf *")
        assert is_dangerous is True

    def test_block_fork_bomb(self, hook_module):
        """Test blocking fork bomb."""
        is_dangerous, reason = hook_module.is_dangerous_command(":(){ :|:& };:")
        assert is_dangerous is True

    def test_block_sudo_commands(self, hook_module):
        """Test blocking sudo commands."""
        is_dangerous, reason = hook_module.is_dangerous_command("sudo rm -rf /tmp/test")
        assert is_dangerous is True
        assert "sudo" in reason.lower()

    def test_block_sudo_piped(self, hook_module):
        """Test blocking sudo after pipe."""
        is_dangerous, reason = hook_module.is_dangerous_command("echo 'password' | sudo apt install")
        assert is_dangerous is True

    def test_block_sudo_chained(self, hook_module):
        """Test blocking sudo after &&."""
        is_dangerous, reason = hook_module.is_dangerous_command("cd /tmp && sudo rm -rf test")
        assert is_dangerous is True

    def test_block_rm_etc(self, hook_module):
        """Test blocking rm on /etc."""
        is_dangerous, reason = hook_module.is_dangerous_command("rm -rf /etc/passwd")
        assert is_dangerous is True

    def test_block_rm_usr(self, hook_module):
        """Test blocking rm on /usr."""
        is_dangerous, reason = hook_module.is_dangerous_command("rm -rf /usr/bin")
        assert is_dangerous is True

    def test_block_rm_var(self, hook_module):
        """Test blocking rm on /var."""
        is_dangerous, reason = hook_module.is_dangerous_command("rm -rf /var/log")
        assert is_dangerous is True

    def test_block_write_etc(self, hook_module):
        """Test blocking write redirect to /etc."""
        is_dangerous, reason = hook_module.is_dangerous_command("echo 'test' > /etc/passwd")
        assert is_dangerous is True

    def test_block_shutdown(self, hook_module):
        """Test blocking shutdown command."""
        is_dangerous, reason = hook_module.is_dangerous_command("shutdown -h now")
        assert is_dangerous is True

    def test_block_reboot(self, hook_module):
        """Test blocking reboot command."""
        is_dangerous, reason = hook_module.is_dangerous_command("reboot")
        assert is_dangerous is True

    def test_block_mkfs(self, hook_module):
        """Test blocking mkfs command."""
        is_dangerous, reason = hook_module.is_dangerous_command("mkfs.ext4 /dev/sda1")
        assert is_dangerous is True

    def test_block_dd_to_device(self, hook_module):
        """Test blocking dd to device."""
        is_dangerous, reason = hook_module.is_dangerous_command("dd if=/dev/zero of=/dev/sda")
        assert is_dangerous is True

    def test_allow_safe_commands(self, hook_module):
        """Test allowing safe commands."""
        safe_commands = [
            "ls -la",
            "git status",
            "npm install",
            "python script.py",
            "rm -rf ./node_modules",
            "rm -rf /tmp/test-dir",
            "cat /etc/hosts",  # Reading is allowed, not writing
            "echo 'hello world'",
        ]
        for cmd in safe_commands:
            is_dangerous, reason = hook_module.is_dangerous_command(cmd)
            assert is_dangerous is False, f"Safe command blocked: {cmd} - {reason}"

    def test_allow_rm_project_directory(self, hook_module):
        """Test allowing rm in project directories."""
        safe_rm_commands = [
            "rm -rf ./build",
            "rm -rf ./dist",
            "rm -rf ./node_modules",
            "rm -rf /home/user/project/build",
        ]
        for cmd in safe_rm_commands:
            is_dangerous, reason = hook_module.is_dangerous_command(cmd)
            assert is_dangerous is False, f"Safe rm blocked: {cmd} - {reason}"


class TestSensitiveFileDetection:
    """Tests for sensitive file access detection."""

    @pytest.fixture
    def hook_module(self):
        """Import the pre_tool_use module."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "pre_tool_use",
            HOOKS_DIR / "pre_tool_use.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_block_env_file(self, hook_module):
        """Test blocking .env file access."""
        is_sensitive, reason = hook_module.is_sensitive_file_access(".env")
        assert is_sensitive is True

    def test_block_env_local(self, hook_module):
        """Test blocking .env.local file access."""
        is_sensitive, reason = hook_module.is_sensitive_file_access(".env.local")
        assert is_sensitive is True

    def test_block_env_production(self, hook_module):
        """Test blocking .env.production file access."""
        is_sensitive, reason = hook_module.is_sensitive_file_access(".env.production")
        assert is_sensitive is True

    def test_block_secret_file(self, hook_module):
        """Test blocking files with _SECRET in name."""
        is_sensitive, reason = hook_module.is_sensitive_file_access("API_SECRET.txt")
        assert is_sensitive is True

    def test_block_secret_file_lowercase(self, hook_module):
        """Test blocking files with _secret in name (case insensitive)."""
        is_sensitive, reason = hook_module.is_sensitive_file_access("db_secret.json")
        assert is_sensitive is True

    def test_block_ssh_private_key(self, hook_module):
        """Test blocking SSH private key."""
        is_sensitive, reason = hook_module.is_sensitive_file_access("id_rsa")
        assert is_sensitive is True

    def test_block_ssh_ed25519_key(self, hook_module):
        """Test blocking SSH ed25519 key."""
        is_sensitive, reason = hook_module.is_sensitive_file_access("id_ed25519")
        assert is_sensitive is True

    def test_block_pem_file(self, hook_module):
        """Test blocking PEM files."""
        is_sensitive, reason = hook_module.is_sensitive_file_access("private_key.pem")
        assert is_sensitive is True

    def test_block_credentials_json(self, hook_module):
        """Test blocking credentials.json."""
        is_sensitive, reason = hook_module.is_sensitive_file_access("credentials.json")
        assert is_sensitive is True

    def test_block_aws_credentials(self, hook_module):
        """Test blocking AWS credentials."""
        is_sensitive, reason = hook_module.is_sensitive_file_access(".aws/credentials")
        assert is_sensitive is True

    def test_block_netrc(self, hook_module):
        """Test blocking .netrc."""
        is_sensitive, reason = hook_module.is_sensitive_file_access(".netrc")
        assert is_sensitive is True

    def test_allow_regular_files(self, hook_module):
        """Test allowing regular file access."""
        safe_files = [
            "src/main.py",
            "package.json",
            "README.md",
            ".gitignore",
            "config.json",
            "settings.yaml",
            "api/endpoints.py",
        ]
        for file in safe_files:
            is_sensitive, reason = hook_module.is_sensitive_file_access(file)
            assert is_sensitive is False, f"Safe file blocked: {file} - {reason}"


class TestWriteContentCheck:
    """Tests for Write tool content checking."""

    @pytest.fixture
    def hook_module(self):
        """Import the pre_tool_use module."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "pre_tool_use",
            HOOKS_DIR / "pre_tool_use.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_block_rsa_private_key(self, hook_module):
        """Test blocking content with RSA private key."""
        content = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA...
-----END RSA PRIVATE KEY-----"""
        should_block, reason = hook_module.check_write_content({"content": content})
        assert should_block is True

    def test_block_openssh_private_key(self, hook_module):
        """Test blocking content with OpenSSH private key."""
        content = """-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAA...
-----END OPENSSH PRIVATE KEY-----"""
        should_block, reason = hook_module.check_write_content({"content": content})
        assert should_block is True

    def test_block_ec_private_key(self, hook_module):
        """Test blocking content with EC private key."""
        content = """-----BEGIN EC PRIVATE KEY-----
MHQCAQEEIOf...
-----END EC PRIVATE KEY-----"""
        should_block, reason = hook_module.check_write_content({"content": content})
        assert should_block is True

    def test_allow_normal_content(self, hook_module):
        """Test allowing normal file content."""
        content = """
def hello_world():
    print("Hello, World!")

if __name__ == "__main__":
    hello_world()
"""
        should_block, reason = hook_module.check_write_content({"content": content})
        assert should_block is False


class TestHookIntegration:
    """Integration tests for hook execution."""

    @pytest.fixture
    def hook_script(self):
        """Get path to pre_tool_use.py."""
        return HOOKS_DIR / "pre_tool_use.py"

    def run_hook(self, hook_script: Path, hook_input: dict, env: dict = None) -> int:
        """Run hook script with given input and return exit code."""
        test_env = {
            "CLAUDE_PROJECT_DIR": str(Path(__file__).parent.parent),
            "CLAUDE_SESSION_ID": "test-session-123",
        }
        if env:
            test_env.update(env)

        result = subprocess.run(
            ["uv", "run", str(hook_script)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, **test_env},
        )
        return result.returncode

    def test_block_dangerous_bash(self, hook_script):
        """Test that dangerous bash command is blocked."""
        hook_input = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
        }
        exit_code = self.run_hook(hook_script, hook_input)
        assert exit_code == 1

    def test_allow_safe_bash(self, hook_script):
        """Test that safe bash command is allowed."""
        hook_input = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
        }
        exit_code = self.run_hook(hook_script, hook_input)
        assert exit_code == 0

    def test_block_env_file_read(self, hook_script):
        """Test that reading .env file is blocked."""
        hook_input = {
            "tool_name": "Read",
            "tool_input": {"file_path": ".env"},
        }
        exit_code = self.run_hook(hook_script, hook_input)
        assert exit_code == 1

    def test_allow_regular_file_read(self, hook_script):
        """Test that reading regular file is allowed."""
        hook_input = {
            "tool_name": "Read",
            "tool_input": {"file_path": "src/main.py"},
        }
        exit_code = self.run_hook(hook_script, hook_input)
        assert exit_code == 0


class TestBlockedLogging:
    """Tests for blocked attempt logging."""

    @pytest.fixture
    def hook_module(self):
        """Import the pre_tool_use module."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "pre_tool_use",
            HOOKS_DIR / "pre_tool_use.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_blocked_log_created(self, hook_module, tmp_path):
        """Test that blocked attempts are logged."""
        with patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            hook_module.log_blocked_attempt(
                tool_name="Bash",
                reason="Test block",
                details={"command": "test"},
            )

            log_file = tmp_path / ".adw" / "blocked.log"
            assert log_file.exists()

            content = log_file.read_text()
            log_entry = json.loads(content.strip())
            assert log_entry["tool_name"] == "Bash"
            assert log_entry["reason"] == "Test block"


class TestPostToolUseLogging:
    """Tests for post_tool_use.py logging functionality."""

    @pytest.fixture
    def hook_module(self):
        """Import the post_tool_use module."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "post_tool_use",
            HOOKS_DIR / "post_tool_use.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_sanitize_params_redacts_content(self, hook_module):
        """Test that content is redacted in logs."""
        params = {"content": "a" * 1000, "file_path": "test.py"}
        sanitized = hook_module.sanitize_params(params)
        assert "<1000 chars>" in sanitized["content"]
        assert sanitized["file_path"] == "test.py"

    def test_sanitize_params_truncates_long_commands(self, hook_module):
        """Test that long commands are truncated."""
        params = {"command": "x" * 300}
        sanitized = hook_module.sanitize_params(params)
        assert len(sanitized["command"]) < 210  # 200 + "..."

    def test_summarize_result_error(self, hook_module):
        """Test error result summarization."""
        result = {"error": "Something went wrong" * 10}
        summary = hook_module.summarize_result(result)
        assert "error:" in summary
        assert len(summary) < 120

    def test_summarize_result_content(self, hook_module):
        """Test content result summarization."""
        result = {"content": "x" * 200}
        summary = hook_module.summarize_result(result)
        assert "content:" in summary
        assert "200 chars" in summary


class TestSessionCompletionLogging:
    """Tests for stop.py / session_complete.py logging."""

    @pytest.fixture
    def hook_module(self):
        """Import the stop module."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "stop",
            HOOKS_DIR / "stop.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_calculate_duration(self, hook_module):
        """Test duration calculation."""
        start = "2024-01-01T10:00:00"
        end = "2024-01-01T10:05:30"
        duration = hook_module.calculate_duration(start, end)
        assert duration == 330.0  # 5 minutes 30 seconds

    def test_calculate_duration_none_start(self, hook_module):
        """Test duration with None start time."""
        duration = hook_module.calculate_duration(None, "2024-01-01T10:05:30")
        assert duration == 0.0
