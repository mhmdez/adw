"""Screenshot capture utilities for ADW.

Provides functions for capturing screenshots of desktop and browser windows,
detecting running dev servers, and attaching screenshots to GitHub PRs.
"""

import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

# Common development server ports
DEV_SERVER_PORTS = [3000, 3001, 5173, 5174, 8000, 8080, 8888, 4200, 4000]

# Patterns that indicate a dev server start command
DEV_SERVER_PATTERNS = [
    r"npm\s+run\s+dev",
    r"npm\s+start",
    r"bun\s+run\s+dev",
    r"bun\s+dev",
    r"pnpm\s+dev",
    r"pnpm\s+run\s+dev",
    r"yarn\s+dev",
    r"yarn\s+run\s+dev",
    r"vite",
    r"next\s+dev",
    r"nuxt\s+dev",
    r"python\s+-m\s+http\.server",
    r"uvicorn\s+",
    r"flask\s+run",
    r"gunicorn\s+",
    r"fastapi\s+dev",
    r"php\s+-[sS]",
    r"ruby\s+.*server",
    r"rails\s+server",
    r"ng\s+serve",
]


def is_macos() -> bool:
    """Check if running on macOS."""
    import platform

    return platform.system() == "Darwin"


def capture_screenshot(
    output_path: str | Path | None = None,
    region: tuple[int, int, int, int] | None = None,
    window_id: int | None = None,
    interactive: bool = False,
    silent: bool = True,
) -> Path:
    """Capture a screenshot using macOS screencapture.

    Args:
        output_path: Path to save the screenshot. If None, uses a temp file.
        region: Optional (x, y, width, height) tuple for capture region.
        window_id: Optional window ID to capture specific window.
        interactive: If True, allows user to select region.
        silent: If True, suppresses the camera shutter sound.

    Returns:
        Path to the captured screenshot.

    Raises:
        RuntimeError: If screencapture fails or not on macOS.
        OSError: If screencapture command not found.
    """
    if not is_macos():
        raise RuntimeError("Screenshot capture is only supported on macOS")

    # Determine output path
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(tempfile.gettempdir()) / f"screenshot-{timestamp}.png"
    else:
        output_path = Path(output_path)

    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build screencapture command
    cmd = ["screencapture"]

    if silent:
        cmd.append("-x")  # No sound

    if interactive:
        cmd.append("-i")  # Interactive selection
    elif window_id is not None:
        cmd.extend(["-l", str(window_id)])  # Capture specific window
    elif region is not None:
        x, y, width, height = region
        cmd.extend(["-R", f"{x},{y},{width},{height}"])  # Capture region

    cmd.append(str(output_path))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise RuntimeError(f"screencapture failed: {result.stderr or 'unknown error'}")

        if not output_path.exists():
            raise RuntimeError("Screenshot file was not created")

        return output_path

    except FileNotFoundError:
        raise OSError("screencapture command not found. Is this macOS?")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Screenshot capture timed out")


def capture_browser_screenshot(
    url: str,
    output_path: str | Path | None = None,
    width: int = 1280,
    height: int = 720,
    wait_time: float = 2.0,
    full_page: bool = False,
) -> Path:
    """Capture a screenshot of a web page using Playwright.

    Requires playwright to be installed: pip install playwright

    Args:
        url: URL to capture.
        output_path: Path to save the screenshot. If None, uses a temp file.
        width: Viewport width in pixels.
        height: Viewport height in pixels.
        wait_time: Seconds to wait for page to load.
        full_page: If True, captures the full scrollable page.

    Returns:
        Path to the captured screenshot.

    Raises:
        ImportError: If playwright is not installed.
        RuntimeError: If screenshot capture fails.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ImportError(
            "Playwright is required for browser screenshots. "
            "Install with: pip install playwright && playwright install chromium"
        )

    # Determine output path
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(tempfile.gettempdir()) / f"screenshot-{timestamp}.png"
    else:
        output_path = Path(output_path)

    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": width, "height": height})

            # Navigate to URL
            page.goto(url, wait_until="networkidle", timeout=30000)

            # Additional wait for dynamic content
            if wait_time > 0:
                page.wait_for_timeout(int(wait_time * 1000))

            # Capture screenshot
            page.screenshot(path=str(output_path), full_page=full_page)

            browser.close()

        return output_path

    except Exception as e:
        raise RuntimeError(f"Failed to capture browser screenshot: {e}")


def is_dev_server_running(port: int) -> bool:
    """Check if a development server is running on the specified port.

    Args:
        port: Port number to check.

    Returns:
        True if a server is listening on the port.
    """
    if is_macos():
        # Use lsof on macOS
        try:
            result = subprocess.run(
                ["lsof", "-i", f":{port}", "-P", "-n"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # lsof returns 0 if something is found
            return result.returncode == 0 and "LISTEN" in result.stdout
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    # Fallback: try to connect
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        connect_result = sock.connect_ex(("127.0.0.1", port))
        return connect_result == 0
    finally:
        sock.close()


def detect_dev_server_ports() -> list[int]:
    """Detect which common dev server ports have servers running.

    Returns:
        List of ports with running servers.
    """
    running_ports = []
    for port in DEV_SERVER_PORTS:
        if is_dev_server_running(port):
            running_ports.append(port)
    return running_ports


def get_dev_server_url(port: int, protocol: str = "http") -> str:
    """Get the localhost URL for a dev server.

    Args:
        port: Port number.
        protocol: Protocol to use (http or https).

    Returns:
        Full URL string.
    """
    return f"{protocol}://localhost:{port}"


def is_dev_server_command(command: str) -> bool:
    """Check if a command is likely starting a development server.

    Args:
        command: The bash command being executed.

    Returns:
        True if the command looks like it starts a dev server.
    """
    if not command:
        return False

    command_lower = command.lower()
    for pattern in DEV_SERVER_PATTERNS:
        if re.search(pattern, command_lower):
            return True
    return False


def extract_port_from_command(command: str) -> int | None:
    """Try to extract the port number from a dev server command.

    Args:
        command: The command string.

    Returns:
        Port number if found, None otherwise.
    """
    # Common port flag patterns
    port_patterns = [
        r"--port[=\s]+(\d+)",
        r"-p[=\s]+(\d+)",
        r"-P[=\s]+(\d+)",
        r":(\d{4,5})\b",  # Port in URL-like format
        r"PORT=(\d+)",
        r"\.server\s+(\d+)",  # python -m http.server PORT
    ]

    for pattern in port_patterns:
        match = re.search(pattern, command)
        if match:
            port = int(match.group(1))
            if 1024 <= port <= 65535:  # Valid port range
                return port

    return None


def get_screenshots_dir(task_id: str | None = None) -> Path:
    """Get the directory for storing screenshots.

    Args:
        task_id: Optional task ID to create task-specific directory.

    Returns:
        Path to screenshots directory.
    """
    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))

    if task_id:
        screenshots_dir = project_dir / "agents" / task_id / "screenshots"
    else:
        screenshots_dir = project_dir / ".adw" / "screenshots"

    screenshots_dir.mkdir(parents=True, exist_ok=True)
    return screenshots_dir


def capture_dev_server_screenshot(
    port: int,
    task_id: str | None = None,
    wait_time: float = 3.0,
    use_browser: bool = True,
) -> Path | None:
    """Capture a screenshot of a running dev server.

    Args:
        port: Port the dev server is running on.
        task_id: Optional task ID for organizing screenshots.
        wait_time: Time to wait for the server/page to be ready.
        use_browser: If True, use Playwright; otherwise use screencapture.

    Returns:
        Path to screenshot if successful, None otherwise.
    """
    # Wait for server to be fully ready
    import time

    time.sleep(wait_time)

    # Verify server is running
    if not is_dev_server_running(port):
        return None

    # Determine output path
    screenshots_dir = get_screenshots_dir(task_id)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = screenshots_dir / f"screenshot-{timestamp}.png"

    url = get_dev_server_url(port)

    if use_browser:
        try:
            return capture_browser_screenshot(
                url=url,
                output_path=output_path,
                wait_time=1.0,  # Additional wait after navigation
            )
        except ImportError:
            # Fall back to desktop capture if Playwright not available
            pass
        except RuntimeError:
            # Playwright failed, try desktop capture
            pass

    # Fallback to desktop capture (less reliable but doesn't need Playwright)
    if is_macos():
        try:
            return capture_screenshot(output_path=output_path)
        except (RuntimeError, OSError):
            pass

    return None


def attach_screenshots_to_pr(
    pr_number: int,
    screenshots: list[Path],
    owner: str | None = None,
    repo: str | None = None,
) -> bool:
    """Attach screenshots to a GitHub PR.

    Uploads screenshots and adds them to the PR body or as a comment.

    Args:
        pr_number: GitHub PR number.
        screenshots: List of screenshot file paths.
        owner: Repository owner. If None, detected from git remote.
        repo: Repository name. If None, detected from git remote.

    Returns:
        True if successful, False otherwise.
    """
    if not screenshots:
        return True  # Nothing to do

    # Filter to existing files
    existing_screenshots = [p for p in screenshots if p.exists()]
    if not existing_screenshots:
        return False

    # Detect owner/repo from git if not provided
    if not owner or not repo:
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                cwd=os.getcwd(),
            )
            if result.returncode == 0:
                remote_url = result.stdout.strip()
                # Parse owner/repo from git URL
                match = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", remote_url)
                if match:
                    owner = owner or match.group(1)
                    repo = repo or match.group(2)
        except subprocess.SubprocessError:
            pass

    if not owner or not repo:
        return False

    # Build comment body with screenshots
    # Note: GitHub doesn't support direct image upload via API for comments
    # We need to either:
    # 1. Upload to GitHub releases/assets
    # 2. Use an external image hosting service
    # 3. Commit images to the repo and reference them

    # For now, we'll create a comment with local paths as a placeholder
    # In production, this would upload to a proper image host

    comment_body = "## Screenshots\n\n"
    for i, screenshot in enumerate(existing_screenshots, 1):
        # In a real implementation, we'd upload the image and get a URL
        # For now, include the filename as a reference
        comment_body += f"**Screenshot {i}:** `{screenshot.name}`\n\n"

    # Use gh CLI to add comment (most reliable way)
    try:
        result = subprocess.run(
            [
                "gh",
                "pr",
                "comment",
                str(pr_number),
                "--repo",
                f"{owner}/{repo}",
                "--body",
                comment_body,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        # gh CLI not available
        pass

    return False


def list_screenshots(task_id: str | None = None) -> list[Path]:
    """List all screenshots for a task or project.

    Args:
        task_id: Optional task ID to filter screenshots.

    Returns:
        List of screenshot file paths, sorted by modification time.
    """
    screenshots_dir = get_screenshots_dir(task_id)

    if not screenshots_dir.exists():
        return []

    screenshots = list(screenshots_dir.glob("screenshot-*.png"))
    screenshots.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return screenshots


def cleanup_old_screenshots(
    max_age_days: int = 7,
    task_id: str | None = None,
) -> int:
    """Remove screenshots older than max_age_days.

    Args:
        max_age_days: Maximum age in days before deletion.
        task_id: Optional task ID to clean specific task's screenshots.

    Returns:
        Number of screenshots deleted.
    """
    from datetime import timedelta

    screenshots_dir = get_screenshots_dir(task_id)
    if not screenshots_dir.exists():
        return 0

    cutoff = datetime.now() - timedelta(days=max_age_days)
    deleted = 0

    for screenshot in screenshots_dir.glob("screenshot-*.png"):
        mtime = datetime.fromtimestamp(screenshot.stat().st_mtime)
        if mtime < cutoff:
            screenshot.unlink()
            deleted += 1

    return deleted
