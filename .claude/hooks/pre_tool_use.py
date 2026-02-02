#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Safety guardrails for Claude Code tool execution.

Blocks dangerous commands and sensitive file access.
Exit code 0 = allow, 1 = block.
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path


# Dangerous command patterns
DANGEROUS_COMMANDS = [
    # Destructive file operations
    r"rm\s+-rf\s+/(?!\w)",  # rm -rf / (root)
    r"rm\s+-rf\s+~",        # rm -rf ~ (home)
    r"rm\s+-rf\s+\*",       # rm -rf * (all files)
    r"rm\s+-rf\s+\.(?:\s|$)",  # rm -rf . (current dir, but not ./subdir)
    # Fork bomb
    r":\(\)\s*\{\s*:\|\:\s*&\s*\}\s*;:",
    # System directory modifications (strict)
    r"rm\s+.*\s+/etc(?:/|$)",
    r"rm\s+.*\s+/usr(?:/|$)",
    r"rm\s+.*\s+/var(?:/|$)",
    r"rm\s+.*\s+/boot(?:/|$)",
    r"rm\s+.*\s+/bin(?:/|$)",
    r"rm\s+.*\s+/sbin(?:/|$)",
    r"rm\s+.*\s+/lib(?:/|$)",
    # Dangerous writes to system directories
    r">\s*/etc/",
    r">\s*/usr/",
    r">\s*/var/",
    r">\s*/boot/",
    # Shutdown/reboot
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bhalt\b",
    r"\bpoweroff\b",
    # Disk operations
    r"\bmkfs\b",
    r"\bfdisk\b",
    r"\bdd\s+.*of=/dev/",
]

# Sudo command patterns - block by default
SUDO_PATTERNS = [
    r"^\s*sudo\s+",         # sudo at start
    r"&&\s*sudo\s+",        # sudo after &&
    r"\|\s*sudo\s+",        # sudo after pipe
    r";\s*sudo\s+",         # sudo after semicolon
]

# Sensitive file patterns
SENSITIVE_FILE_PATTERNS = [
    r"\.env(?:\.|$)",           # .env, .env.local, .env.production, etc.
    r".*_SECRET.*",             # Any file with _SECRET in name
    r".*\.pem$",                # PEM private keys
    r"id_rsa(?:\.pub)?$",       # SSH keys
    r"id_ed25519(?:\.pub)?$",   # SSH keys
    r"id_ecdsa(?:\.pub)?$",     # SSH keys
    r"known_hosts$",            # SSH known hosts
    r"authorized_keys$",        # SSH authorized keys
    r"credentials\.json$",      # API credentials
    r"\.aws/credentials$",      # AWS credentials
    r"\.aws/config$",           # AWS config
    r"\.netrc$",                # FTP/Git credentials
    r"\.npmrc$",                # npm auth tokens (can contain tokens)
    r"\.pypirc$",               # PyPI auth tokens
]

# Allowed sudo commands (empty by default, can be configured)
ALLOWED_SUDO_COMMANDS: list[str] = []


def get_adw_dir() -> Path:
    """Get .adw directory, creating if needed."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    adw_dir = Path(project_dir) / ".adw"
    adw_dir.mkdir(parents=True, exist_ok=True)
    return adw_dir


def log_blocked_attempt(
    tool_name: str,
    reason: str,
    details: dict,
) -> None:
    """Log a blocked attempt to .adw/blocked.log."""
    log_file = get_adw_dir() / "blocked.log"

    entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": os.environ.get("CLAUDE_SESSION_ID", "unknown"),
        "tool_name": tool_name,
        "reason": reason,
        "details": details,
    }

    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def is_dangerous_command(command: str) -> tuple[bool, str]:
    """Check if a command matches dangerous patterns.

    Returns:
        Tuple of (is_dangerous, reason)
    """
    # Normalize command for matching
    cmd_lower = command.lower().strip()

    # Check dangerous patterns
    for pattern in DANGEROUS_COMMANDS:
        if re.search(pattern, cmd_lower, re.IGNORECASE):
            return True, f"Matches dangerous pattern: {pattern}"

    # Check sudo patterns
    for pattern in SUDO_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            # Check if it's an allowed sudo command
            for allowed in ALLOWED_SUDO_COMMANDS:
                if allowed in command:
                    return False, ""
            return True, "sudo command blocked (add to ALLOWED_SUDO_COMMANDS to allow)"

    return False, ""


def is_sensitive_file_access(file_path: str) -> tuple[bool, str]:
    """Check if accessing a sensitive file.

    Returns:
        Tuple of (is_sensitive, reason)
    """
    if not file_path:
        return False, ""

    # Normalize path
    path_str = str(file_path).lower()
    path_basename = os.path.basename(file_path)

    # Check sensitive patterns
    for pattern in SENSITIVE_FILE_PATTERNS:
        if re.search(pattern, path_str, re.IGNORECASE):
            return True, f"Sensitive file access: {pattern}"
        if re.search(pattern, path_basename, re.IGNORECASE):
            return True, f"Sensitive file access: {pattern}"

    return False, ""


def check_bash_command(tool_input: dict) -> tuple[bool, str]:
    """Check Bash command for dangerous operations.

    Returns:
        Tuple of (should_block, reason)
    """
    command = tool_input.get("command", "")
    if not command:
        return False, ""

    # Check for dangerous commands
    is_dangerous, reason = is_dangerous_command(command)
    if is_dangerous:
        return True, reason

    return False, ""


def check_file_access(tool_name: str, tool_input: dict) -> tuple[bool, str]:
    """Check file access for sensitive files.

    Returns:
        Tuple of (should_block, reason)
    """
    file_path = tool_input.get("file_path", "")
    if not file_path:
        return False, ""

    # For Read, Write, Edit tools
    is_sensitive, reason = is_sensitive_file_access(file_path)
    if is_sensitive:
        return True, reason

    return False, ""


def check_write_content(tool_input: dict) -> tuple[bool, str]:
    """Check Write tool content for potential secrets.

    Returns:
        Tuple of (should_block, reason)
    """
    content = tool_input.get("content", "")
    if not content:
        return False, ""

    # Check if content looks like credentials (very basic check)
    # This is intentionally not too strict to avoid false positives
    secret_patterns = [
        r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
    ]

    for pattern in secret_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return True, "Content appears to contain private key"

    return False, ""


def main() -> None:
    """Main hook handler."""
    # Read hook input from stdin
    try:
        stdin_data = sys.stdin.read()
        hook_input = json.loads(stdin_data) if stdin_data else {}
    except json.JSONDecodeError:
        hook_input = {}

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    # Check based on tool type
    should_block = False
    reason = ""

    if tool_name == "Bash":
        should_block, reason = check_bash_command(tool_input)

    elif tool_name in ("Read", "Write", "Edit"):
        should_block, reason = check_file_access(tool_name, tool_input)
        if not should_block and tool_name == "Write":
            should_block, reason = check_write_content(tool_input)

    # Log and block if needed
    if should_block:
        log_blocked_attempt(tool_name, reason, {"tool_input": tool_input})
        # Print reason for debugging (optional, can be removed for stealth)
        print(f"BLOCKED: {reason}", file=sys.stderr)
        sys.exit(1)

    # Allow the operation
    sys.exit(0)


if __name__ == "__main__":
    main()
