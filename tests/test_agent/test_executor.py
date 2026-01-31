"""Unit tests for agent executor."""

import json
import os
import subprocess
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from adw.agent.executor import (
    get_safe_env,
    prompt_claude_code,
    prompt_with_retry,
    SAFE_ENV_VARS,
)
from adw.agent.models import AgentPromptRequest, AgentPromptResponse, RetryCode


class TestGetSafeEnv:
    """Test get_safe_env function."""

    def test_filters_environment_variables(self):
        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "test-key",
                "HOME": "/home/user",
                "PATH": "/usr/bin",
                "DANGEROUS_VAR": "should-not-appear",
                "RANDOM_VAR": "also-filtered",
            },
            clear=True,
        ):
            env = get_safe_env()
            assert "ANTHROPIC_API_KEY" in env
            assert "HOME" in env
            assert "PATH" in env
            assert "PYTHONUNBUFFERED" in env
            assert env["PYTHONUNBUFFERED"] == "1"
            assert "DANGEROUS_VAR" not in env
            assert "RANDOM_VAR" not in env

    def test_includes_all_safe_vars(self):
        with patch.dict(
            os.environ,
            {var: f"value-{var}" for var in SAFE_ENV_VARS},
            clear=True,
        ):
            env = get_safe_env()
            for var in SAFE_ENV_VARS:
                assert var in env

    def test_adds_pythonunbuffered(self):
        env = get_safe_env()
        assert env["PYTHONUNBUFFERED"] == "1"


class TestPromptClaudeCode:
    """Test prompt_claude_code function."""

    @pytest.fixture
    def temp_agent_dir(self, tmp_path):
        """Create temporary agent directory."""
        agent_dir = tmp_path / "agents" / "test1234" / "default"
        agent_dir.mkdir(parents=True)
        return agent_dir

    @pytest.fixture
    def mock_subprocess_success(self):
        """Mock successful subprocess run."""
        mock_result = Mock()
        mock_result.stdout = json.dumps(
            {
                "type": "result",
                "result": "Test output",
                "session_id": "session123",
            }
        )
        mock_result.returncode = 0
        return mock_result

    def test_builds_command_correctly_default(self):
        """Test command building with default parameters."""
        request = AgentPromptRequest(
            prompt="Test prompt",
            adw_id="test1234",
        )

        with patch("adw.agent.executor.subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="", returncode=0)
            prompt_claude_code(request)

            # Check command
            call_args = mock_run.call_args
            cmd = call_args[0][0]
            assert cmd[0] == "claude"
            assert "--output-format" in cmd
            assert "stream-json" in cmd
            assert "--print" in cmd
            assert "Test prompt" in cmd
            assert "--model" not in cmd  # sonnet is default

    def test_builds_command_with_opus_model(self):
        """Test command building with opus model."""
        request = AgentPromptRequest(
            prompt="Test prompt",
            adw_id="test1234",
            model="opus",
        )

        with patch("adw.agent.executor.subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="", returncode=0)
            prompt_claude_code(request)

            call_args = mock_run.call_args
            cmd = call_args[0][0]
            assert "--model" in cmd
            assert "opus" in cmd

    def test_builds_command_with_skip_permissions(self):
        """Test command building with skip permissions."""
        request = AgentPromptRequest(
            prompt="Test prompt",
            adw_id="test1234",
            dangerously_skip_permissions=True,
        )

        with patch("adw.agent.executor.subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="", returncode=0)
            prompt_claude_code(request)

            call_args = mock_run.call_args
            cmd = call_args[0][0]
            assert "--dangerously-skip-permissions" in cmd

    def test_success_response(self, tmp_path):
        """Test successful execution."""
        request = AgentPromptRequest(
            prompt="Test prompt",
            adw_id="test1234",
        )

        jsonl_output = json.dumps({
            "type": "result",
            "result": "Success!",
            "session_id": "session123",
        })

        with patch("adw.agent.executor.get_output_dir") as mock_get_dir:
            mock_get_dir.return_value = tmp_path
            with patch("adw.agent.executor.subprocess.run") as mock_run:
                mock_run.return_value = Mock(stdout=jsonl_output, returncode=0)

                response = prompt_claude_code(request)

                assert response.success is True
                assert response.output == "Success!"
                assert response.session_id == "session123"
                assert response.retry_code == RetryCode.NONE
                assert response.error_message is None

    def test_error_response(self, tmp_path):
        """Test error response from Claude Code."""
        request = AgentPromptRequest(
            prompt="Test prompt",
            adw_id="test1234",
        )

        jsonl_output = json.dumps({
            "type": "error",
            "error": {"message": "Test error"},
        })

        with patch("adw.agent.executor.get_output_dir") as mock_get_dir:
            mock_get_dir.return_value = tmp_path
            with patch("adw.agent.executor.subprocess.run") as mock_run:
                mock_run.return_value = Mock(stdout=jsonl_output, returncode=1)

                response = prompt_claude_code(request)

                assert response.success is False
                assert response.retry_code == RetryCode.EXECUTION_ERROR
                assert response.error_message == "Test error"

    def test_timeout_error(self, tmp_path):
        """Test timeout handling."""
        request = AgentPromptRequest(
            prompt="Test prompt",
            adw_id="test1234",
            timeout=1,
        )

        with patch("adw.agent.executor.get_output_dir") as mock_get_dir:
            mock_get_dir.return_value = tmp_path
            with patch("adw.agent.executor.subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired(
                    cmd="claude", timeout=1
                )

                response = prompt_claude_code(request)

                assert response.success is False
                assert response.retry_code == RetryCode.TIMEOUT_ERROR
                assert "Timeout" in response.error_message

    def test_claude_code_not_found(self, tmp_path):
        """Test handling when Claude Code CLI is not found."""
        request = AgentPromptRequest(
            prompt="Test prompt",
            adw_id="test1234",
        )

        with patch("adw.agent.executor.get_output_dir") as mock_get_dir:
            mock_get_dir.return_value = tmp_path
            with patch("adw.agent.executor.subprocess.run") as mock_run:
                mock_run.side_effect = FileNotFoundError()

                response = prompt_claude_code(request)

                assert response.success is False
                assert response.retry_code == RetryCode.CLAUDE_CODE_ERROR
                assert "not found" in response.error_message

    def test_saves_output_files(self, tmp_path):
        """Test that output files are saved."""
        request = AgentPromptRequest(
            prompt="Test prompt",
            adw_id="test1234",
        )

        jsonl_output = json.dumps({
            "type": "result",
            "result": "Success!",
        })

        with patch("adw.agent.executor.get_output_dir") as mock_get_dir:
            mock_get_dir.return_value = tmp_path
            with patch("adw.agent.executor.subprocess.run") as mock_run:
                mock_run.return_value = Mock(stdout=jsonl_output, returncode=0)

                prompt_claude_code(request)

                # Check files were created
                assert (tmp_path / "cc_raw_output.jsonl").exists()
                assert (tmp_path / "cc_raw_output.json").exists()
                assert (tmp_path / "cc_final_result.txt").exists()

    def test_parses_multiple_jsonl_lines(self, tmp_path):
        """Test parsing multiple JSONL lines."""
        request = AgentPromptRequest(
            prompt="Test prompt",
            adw_id="test1234",
        )

        line1 = json.dumps({"type": "start", "session_id": "session123"})
        line2 = json.dumps({"type": "result", "result": "Final output"})
        jsonl_output = f"{line1}\n{line2}"

        with patch("adw.agent.executor.get_output_dir") as mock_get_dir:
            mock_get_dir.return_value = tmp_path
            with patch("adw.agent.executor.subprocess.run") as mock_run:
                mock_run.return_value = Mock(stdout=jsonl_output, returncode=0)

                response = prompt_claude_code(request)

                assert response.success is True
                assert response.session_id == "session123"
                assert response.output == "Final output"

    def test_uses_working_dir(self):
        """Test that working directory is passed to subprocess."""
        request = AgentPromptRequest(
            prompt="Test prompt",
            adw_id="test1234",
            working_dir="/tmp/test",
        )

        with patch("adw.agent.executor.subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="", returncode=0)
            prompt_claude_code(request)

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["cwd"] == "/tmp/test"


class TestPromptWithRetry:
    """Test prompt_with_retry function."""

    def test_success_on_first_attempt(self):
        """Test successful execution on first attempt."""
        request = AgentPromptRequest(
            prompt="Test prompt",
            adw_id="test1234",
        )

        with patch("adw.agent.executor.prompt_claude_code") as mock_prompt:
            mock_prompt.return_value = AgentPromptResponse(
                output="Success",
                success=True,
            )

            response = prompt_with_retry(request, max_retries=3)

            assert response.success is True
            assert mock_prompt.call_count == 1

    def test_retries_on_failure(self):
        """Test retries on failure."""
        request = AgentPromptRequest(
            prompt="Test prompt",
            adw_id="test1234",
        )

        with patch("adw.agent.executor.prompt_claude_code") as mock_prompt:
            # First two calls fail, third succeeds
            mock_prompt.side_effect = [
                AgentPromptResponse(
                    output="",
                    success=False,
                    retry_code=RetryCode.EXECUTION_ERROR,
                ),
                AgentPromptResponse(
                    output="",
                    success=False,
                    retry_code=RetryCode.EXECUTION_ERROR,
                ),
                AgentPromptResponse(
                    output="Success",
                    success=True,
                ),
            ]

            with patch("time.sleep"):  # Mock sleep to speed up test
                response = prompt_with_retry(request, max_retries=3)

            assert response.success is True
            assert mock_prompt.call_count == 3

    def test_max_retries_exceeded(self):
        """Test behavior when max retries exceeded."""
        request = AgentPromptRequest(
            prompt="Test prompt",
            adw_id="test1234",
        )

        with patch("adw.agent.executor.prompt_claude_code") as mock_prompt:
            mock_prompt.return_value = AgentPromptResponse(
                output="",
                success=False,
                retry_code=RetryCode.EXECUTION_ERROR,
                error_message="Persistent error",
            )

            with patch("time.sleep"):
                response = prompt_with_retry(request, max_retries=2)

            assert response.success is False
            assert mock_prompt.call_count == 3  # Initial + 2 retries

    def test_rate_limit_longer_delay(self):
        """Test rate limit uses longer delay."""
        request = AgentPromptRequest(
            prompt="Test prompt",
            adw_id="test1234",
        )

        with patch("adw.agent.executor.prompt_claude_code") as mock_prompt:
            mock_prompt.side_effect = [
                AgentPromptResponse(
                    output="",
                    success=False,
                    retry_code=RetryCode.RATE_LIMIT,
                ),
                AgentPromptResponse(
                    output="Success",
                    success=True,
                ),
            ]

            with patch("time.sleep") as mock_sleep:
                response = prompt_with_retry(
                    request,
                    max_retries=3,
                    retry_delays=[1, 3, 5],
                )

            assert response.success is True
            # First delay is 1, but rate limit multiplies by 3
            mock_sleep.assert_called_once_with(3)

    def test_custom_retry_delays(self):
        """Test custom retry delays."""
        request = AgentPromptRequest(
            prompt="Test prompt",
            adw_id="test1234",
        )

        with patch("adw.agent.executor.prompt_claude_code") as mock_prompt:
            mock_prompt.side_effect = [
                AgentPromptResponse(
                    output="",
                    success=False,
                    retry_code=RetryCode.EXECUTION_ERROR,
                ),
                AgentPromptResponse(
                    output="",
                    success=False,
                    retry_code=RetryCode.EXECUTION_ERROR,
                ),
                AgentPromptResponse(
                    output="Success",
                    success=True,
                ),
            ]

            with patch("time.sleep") as mock_sleep:
                response = prompt_with_retry(
                    request,
                    max_retries=3,
                    retry_delays=[2, 4, 6],
                )

            assert response.success is True
            # Should use custom delays
            assert mock_sleep.call_count == 2
            calls = [call[0][0] for call in mock_sleep.call_args_list]
            assert calls == [2, 4]

    def test_stops_on_success(self):
        """Test that retries stop on success."""
        request = AgentPromptRequest(
            prompt="Test prompt",
            adw_id="test1234",
        )

        with patch("adw.agent.executor.prompt_claude_code") as mock_prompt:
            mock_prompt.return_value = AgentPromptResponse(
                output="Success",
                success=True,
            )

            with patch("time.sleep") as mock_sleep:
                response = prompt_with_retry(request, max_retries=3)

            assert response.success is True
            mock_sleep.assert_not_called()
            assert mock_prompt.call_count == 1
