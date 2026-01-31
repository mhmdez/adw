"""Self-update mechanism for ADW."""

from __future__ import annotations

import subprocess
import sys
from typing import NamedTuple

import httpx
from rich.console import Console

from . import __version__

console = Console()

GITHUB_REPO = "mhmdez/adw"
PYPI_PACKAGE = "adw-cli"


class Version(NamedTuple):
    """Semantic version tuple."""

    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, version_str: str) -> Version:
        """Parse a version string like '0.1.0' or 'v0.1.0'.

        Args:
            version_str: Version string to parse.

        Returns:
            Parsed Version tuple.
        """
        # Remove leading 'v' if present
        version_str = version_str.lstrip("v")

        parts = version_str.split(".")
        return cls(
            major=int(parts[0]) if len(parts) > 0 else 0,
            minor=int(parts[1]) if len(parts) > 1 else 0,
            patch=int(parts[2].split("-")[0]) if len(parts) > 2 else 0,
        )

    def __str__(self) -> str:
        """Return version as string."""
        return f"{self.major}.{self.minor}.{self.patch}"


def get_current_version() -> Version:
    """Get the current installed version.

    Returns:
        Current version tuple.
    """
    return Version.parse(__version__)


def fetch_latest_github_release() -> Version | None:
    """Fetch the latest release version from GitHub.

    Returns:
        Latest version tuple, or None if fetch failed.
    """
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()
            tag_name = data.get("tag_name", "")
            return Version.parse(tag_name)
    except (httpx.HTTPError, KeyError, ValueError, IndexError):
        return None


def fetch_latest_pypi_version() -> Version | None:
    """Fetch the latest version from PyPI.

    Returns:
        Latest version tuple, or None if fetch failed.
    """
    try:
        url = f"https://pypi.org/pypi/{PYPI_PACKAGE}/json"
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()
            version_str = data.get("info", {}).get("version", "")
            return Version.parse(version_str)
    except (httpx.HTTPError, KeyError, ValueError, IndexError):
        return None


def update_with_uv() -> bool:
    """Update ADW using uv tool.

    Returns:
        True if update succeeded.
    """
    try:
        result = subprocess.run(
            ["uv", "tool", "upgrade", PYPI_PACKAGE],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def update_with_pipx() -> bool:
    """Update ADW using pipx.

    Returns:
        True if update succeeded.
    """
    try:
        result = subprocess.run(
            ["pipx", "upgrade", PYPI_PACKAGE],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def update_with_pip() -> bool:
    """Update ADW using pip.

    Returns:
        True if update succeeded.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", PYPI_PACKAGE],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def check_for_update() -> tuple[Version, Version | None]:
    """Check if an update is available.

    Returns:
        Tuple of (current_version, latest_version or None if check failed).
    """
    current = get_current_version()

    # Try PyPI first, then GitHub
    latest = fetch_latest_pypi_version()
    if latest is None:
        latest = fetch_latest_github_release()

    return current, latest


def run_update() -> bool:
    """Check for and install updates.

    Returns:
        True if update was successful or not needed.
    """
    console.print("[dim]Checking for updates...[/dim]")

    current, latest = check_for_update()

    if latest is None:
        console.print("[yellow]Could not check for updates. Please try again later.[/yellow]")
        return False

    if latest <= current:
        console.print(f"[green]Already at latest version ({current})[/green]")
        return True

    console.print(f"[cyan]Update available: {current} → {latest}[/cyan]")
    console.print()

    # Try different update methods
    console.print("[dim]Attempting update with uv...[/dim]")
    if update_with_uv():
        console.print(f"[green]Successfully updated to {latest}![/green]")
        return True

    console.print("[dim]Attempting update with pipx...[/dim]")
    if update_with_pipx():
        console.print(f"[green]Successfully updated to {latest}![/green]")
        return True

    console.print("[dim]Attempting update with pip...[/dim]")
    if update_with_pip():
        console.print(f"[green]Successfully updated to {latest}![/green]")
        return True

    console.print("[red]Could not update automatically.[/red]")
    console.print("Try running one of these manually:")
    console.print(f"  uv tool upgrade {PYPI_PACKAGE}")
    console.print(f"  pipx upgrade {PYPI_PACKAGE}")
    console.print(f"  pip install --upgrade {PYPI_PACKAGE}")

    return False
