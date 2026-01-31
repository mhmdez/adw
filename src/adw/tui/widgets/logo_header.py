"""Custom header widget with ASCII logo."""

from __future__ import annotations

from textual.widgets import Static
from textual.app import ComposeResult


# ASCII art logo for ADW
ADW_LOGO = """
 █████╗ ██████╗ ██╗    ██╗
██╔══██╗██╔══██╗██║    ██║
███████║██║  ██║██║ █╗ ██║
██╔══██║██║  ██║██║███╗██║
██║  ██║██████╔╝╚███╔███╔╝
╚═╝  ╚═╝╚═════╝  ╚══╝╚══╝
""".strip()

# Compact single-line logo
ADW_LOGO_COMPACT = "▄▀█ █▀▄ █ █ █"


class LogoHeader(Static):
    """Header widget with ADW ASCII logo."""

    DEFAULT_CSS = """
    LogoHeader {
        dock: top;
        width: 100%;
        height: 3;
        background: $primary;
        color: $text;
        content-align: center middle;
        text-style: bold;
    }
    """

    def __init__(self, version: str = "", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.version = version

    def compose(self) -> ComposeResult:
        """Compose the header content."""
        return []

    def render(self) -> str:
        """Render the header content."""
        title = "█▀█ █▀▄ █ █ █  ADW"
        subtitle = "AI Developer Workflow"
        if self.version:
            return f"{title}  v{self.version}  •  {subtitle}"
        return f"{title}  •  {subtitle}"
