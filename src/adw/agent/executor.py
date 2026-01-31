"""Agent execution engine."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from .models import AgentPromptRequest, AgentPromptResponse, RetryCode
from .utils import generate_adw_id, get_output_dir


# Environment variables safe to pass to subprocess
SAFE_ENV_VARS = [
    "ANTHROPIC_API_KEY",
    "HOME", "USER", "PATH", "SHELL", "TERM", "LANG",
]


def get_safe_env() -> dict[str, str]:
    """Get filtered environment for subprocess."""
    env = {k: v for k, v in os.environ.items() if k in SAFE_ENV_VARS and v}
    env["PYTHONUNBUFFERED"] = "1"
    return env


def prompt_claude_code(request: AgentPromptRequest) -> AgentPromptResponse:
    """Execute a prompt with Claude Code CLI."""
    start_time = time.time()
    output_dir = get_output_dir(request.adw_id, request.agent_name)

    # Build command
    cmd = ["claude"]
    if request.model != "sonnet":
        cmd.extend(["--model", request.model])
    if request.dangerously_skip_permissions:
        cmd.append("--dangerously-skip-permissions")
    cmd.extend(["--output-format", "stream-json"])
    cmd.extend(["--print", request.prompt])

    try:
        result = subprocess.run(
            cmd,
            cwd=request.working_dir,
            capture_output=True,
            text=True,
            timeout=request.timeout,
            env=get_safe_env(),
        )

        duration = time.time() - start_time

        # Save raw output
        (output_dir / "cc_raw_output.jsonl").write_text(result.stdout)

        # Parse JSONL
        messages = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        # Save parsed
        (output_dir / "cc_raw_output.json").write_text(
            json.dumps(messages, indent=2)
        )

        # Extract result
        result_text = ""
        session_id = None
        has_error = False
        error_msg = None

        for msg in messages:
            if msg.get("session_id"):
                session_id = msg["session_id"]
            if msg.get("type") == "result":
                result_text = msg.get("result", "")
            if msg.get("type") == "error":
                has_error = True
                error_msg = msg.get("error", {}).get("message", "Unknown error")

        # Save final result
        (output_dir / "cc_final_result.txt").write_text(result_text)

        if has_error:
            return AgentPromptResponse(
                output=result_text,
                success=False,
                session_id=session_id,
                retry_code=RetryCode.EXECUTION_ERROR,
                error_message=error_msg,
                duration_seconds=duration,
            )

        return AgentPromptResponse(
            output=result_text,
            success=True,
            session_id=session_id,
            duration_seconds=duration,
        )

    except subprocess.TimeoutExpired:
        return AgentPromptResponse(
            output="",
            success=False,
            retry_code=RetryCode.TIMEOUT_ERROR,
            error_message=f"Timeout after {request.timeout}s",
            duration_seconds=request.timeout,
        )
    except FileNotFoundError:
        return AgentPromptResponse(
            output="",
            success=False,
            retry_code=RetryCode.CLAUDE_CODE_ERROR,
            error_message="Claude Code CLI not found",
            duration_seconds=0,
        )
    except Exception as e:
        return AgentPromptResponse(
            output="",
            success=False,
            retry_code=RetryCode.CLAUDE_CODE_ERROR,
            error_message=str(e),
            duration_seconds=time.time() - start_time,
        )


def prompt_with_retry(
    request: AgentPromptRequest,
    max_retries: int = 3,
    retry_delays: list[int] | None = None,
) -> AgentPromptResponse:
    """Execute prompt with automatic retry."""
    if retry_delays is None:
        retry_delays = [1, 3, 5]

    last_response = None

    for attempt in range(max_retries + 1):
        response = prompt_claude_code(request)
        last_response = response

        if response.success or response.retry_code == RetryCode.NONE:
            return response

        if attempt < max_retries:
            delay = retry_delays[min(attempt, len(retry_delays) - 1)]
            if response.retry_code == RetryCode.RATE_LIMIT:
                delay *= 3
            time.sleep(delay)

    return last_response or AgentPromptResponse(
        output="",
        success=False,
        error_message="Max retries exceeded",
    )
