"""Splash screen for ADW startup."""

from textual.app import ComposeResult
from textual.containers import Container, Vertical, Center
from textual.screen import Screen
from textual.widgets import Static
from rich.text import Text
from rich.align import Align
import asyncio

from ..branding import LOGO, TAGLINE, SUBTITLE, COLORS, GRADIENT, get_loading_message


class SplashScreen(Screen):
    """Beautiful animated splash screen."""

    CSS = """
    SplashScreen {
        align: center middle;
        background: #0a0a0a;
    }

    #splash-container {
        width: auto;
        height: auto;
        padding: 2 4;
    }

    #logo {
        text-align: center;
    }

    #tagline {
        text-align: center;
        margin-top: 1;
    }

    #loading {
        text-align: center;
        margin-top: 2;
    }

    #progress-bar {
        width: 40;
        height: 1;
        margin: 1 0;
    }

    #version {
        text-align: center;
        margin-top: 1;
        color: #444;
    }
    """

    def __init__(self, version: str = "0.2.0"):
        super().__init__()
        self._version = version
        self._frame = 0
        self._progress = 0.0
        self._loading_msg = get_loading_message()

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="splash-container"):
                yield Static(id="logo")
                yield Static(id="tagline")
                yield Static(id="loading")
                yield Static(id="progress-bar")
                yield Static(id="version")

    async def on_mount(self) -> None:
        self._render_logo()
        self._render_tagline()
        self._render_version()
        
        # Start animation
        self.set_interval(0.1, self._animate)
        
        # Simulate loading
        asyncio.create_task(self._do_loading())

    def _animate(self) -> None:
        self._frame += 1
        self._render_logo()
        self._render_loading()
        self._render_progress()

    async def _do_loading(self) -> None:
        """Simulate loading with progress."""
        steps = [
            (0.1, "Initializing..."),
            (0.2, "Loading config..."),
            (0.4, "Scanning tasks..."),
            (0.6, "Connecting agents..."),
            (0.8, "Almost ready..."),
            (1.0, "Let's go! 🚀"),
        ]
        
        for progress, msg in steps:
            self._progress = progress
            self._loading_msg = msg
            await asyncio.sleep(0.3)
        
        await asyncio.sleep(0.3)
        self.app.pop_screen()

    def _render_logo(self) -> None:
        logo = self.query_one("#logo", Static)
        lines = LOGO.strip().split("\n")
        text = Text()
        
        for i, line in enumerate(lines):
            color_idx = (i + self._frame) % len(GRADIENT)
            color = GRADIENT[color_idx]
            text.append(line + "\n", style=f"bold {color}")
        
        logo.update(Align.center(text))

    def _render_tagline(self) -> None:
        tagline = self.query_one("#tagline", Static)
        text = Text()
        
        # Gradient tagline
        for i, char in enumerate(TAGLINE):
            color_idx = (i + self._frame // 2) % len(GRADIENT)
            text.append(char, style=f"bold {GRADIENT[color_idx]}")
        
        text.append(f"\n{SUBTITLE}", style=f"italic {COLORS['muted']}")
        tagline.update(Align.center(text))

    def _render_loading(self) -> None:
        loading = self.query_one("#loading", Static)
        
        # Animated spinner
        spinners = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        spinner = spinners[self._frame % len(spinners)]
        
        text = Text()
        text.append(f"{spinner} ", style=f"bold {COLORS['primary']}")
        text.append(self._loading_msg, style=COLORS['muted'])
        
        loading.update(Align.center(text))

    def _render_progress(self) -> None:
        progress_bar = self.query_one("#progress-bar", Static)
        
        width = 40
        filled = int(width * self._progress)
        empty = width - filled
        
        text = Text()
        
        # Glowing progress bar
        glow_pos = self._frame % (width + 5)
        
        for i in range(filled):
            if abs(i - glow_pos) <= 2 and self._progress < 1.0:
                intensity = 2 - abs(i - glow_pos)
                colors = [COLORS['primary'], COLORS['accent'], COLORS['highlight']]
                text.append("█", style=colors[min(intensity, 2)])
            else:
                text.append("█", style=COLORS['primary'])
        
        text.append("░" * empty, style="dim")
        
        progress_bar.update(Align.center(text))

    def _render_version(self) -> None:
        version = self.query_one("#version", Static)
        version.update(Align.center(Text(f"v{self._version}", style="#444")))
