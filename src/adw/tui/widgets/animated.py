"""Animated widgets for a beautiful TUI."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static
from textual.reactive import reactive
from rich.text import Text
from rich.panel import Panel
from rich.align import Align
import random

from ..branding import (
    LOGO, TAGLINE, COLORS, SPINNERS, GRADIENT,
    get_loading_message, get_spinner, gradient_text
)


class AnimatedLogo(Static):
    """Animated ASCII logo with gradient effect."""

    DEFAULT_CSS = """
    AnimatedLogo {
        height: auto;
        padding: 0;
        text-align: center;
    }
    """

    frame = reactive(0)

    def __init__(self):
        super().__init__()
        self._colors = GRADIENT.copy()

    def on_mount(self) -> None:
        self.set_interval(0.15, self._tick)
        self._render()

    def _tick(self) -> None:
        self.frame = (self.frame + 1) % len(self._colors)
        # Rotate colors for wave effect
        self._colors = self._colors[1:] + self._colors[:1]
        self._render()

    def _render(self) -> None:
        lines = LOGO.strip().split("\n")
        text = Text()
        
        for i, line in enumerate(lines):
            color_idx = (i + self.frame) % len(self._colors)
            color = self._colors[color_idx]
            text.append(line + "\n", style=color)
        
        text.append(f"\n{TAGLINE}", style=f"bold {COLORS['muted']}")
        self.update(Align.center(text))


class AnimatedSpinner(Static):
    """Animated spinner with customizable style."""

    DEFAULT_CSS = """
    AnimatedSpinner {
        width: auto;
        height: 1;
    }
    """

    frame = reactive(0)

    def __init__(self, style: str = "dots", message: str = ""):
        super().__init__()
        self._spinner = get_spinner(style)
        self._message = message
        self._style = style

    def on_mount(self) -> None:
        self.set_interval(0.1, self._tick)

    def _tick(self) -> None:
        self.frame = (self.frame + 1) % len(self._spinner)
        self._render()

    def _render(self) -> None:
        spinner_char = self._spinner[self.frame]
        text = Text()
        text.append(f" {spinner_char} ", style=f"bold {COLORS['primary']}")
        if self._message:
            text.append(self._message, style=COLORS['muted'])
        self.update(text)

    def set_message(self, message: str) -> None:
        self._message = message
        self._render()


class AnimatedProgress(Static):
    """Animated progress bar with glow effect."""

    DEFAULT_CSS = """
    AnimatedProgress {
        width: 100%;
        height: 1;
        padding: 0 1;
    }
    """

    progress = reactive(0.0)
    glow_pos = reactive(0)

    def __init__(self, width: int = 40):
        super().__init__()
        self._width = width

    def on_mount(self) -> None:
        self.set_interval(0.05, self._tick_glow)

    def _tick_glow(self) -> None:
        self.glow_pos = (self.glow_pos + 1) % (self._width + 5)
        self._render()

    def set_progress(self, value: float) -> None:
        self.progress = max(0.0, min(1.0, value))
        self._render()

    def _render(self) -> None:
        filled = int(self._width * self.progress)
        empty = self._width - filled

        text = Text()
        text.append("▐", style="dim")

        # Render filled portion with glow
        for i in range(filled):
            if abs(i - self.glow_pos) <= 2 and self.progress < 1.0:
                # Glow effect
                intensity = 2 - abs(i - self.glow_pos)
                colors = [COLORS['primary'], COLORS['accent'], COLORS['highlight']]
                text.append("█", style=colors[intensity])
            else:
                text.append("█", style=COLORS['primary'])

        # Empty portion
        text.append("░" * empty, style="dim")
        text.append("▌", style="dim")

        # Percentage
        pct = int(self.progress * 100)
        text.append(f" {pct}%", style=f"bold {COLORS['primary']}")

        self.update(text)


class WaveText(Static):
    """Text with animated wave effect."""

    DEFAULT_CSS = """
    WaveText {
        height: 1;
    }
    """

    offset = reactive(0)

    def __init__(self, text: str):
        super().__init__()
        self._text = text

    def on_mount(self) -> None:
        self.set_interval(0.1, self._tick)

    def _tick(self) -> None:
        self.offset = (self.offset + 1) % len(GRADIENT)
        self._render()

    def _render(self) -> None:
        text = Text()
        for i, char in enumerate(self._text):
            color_idx = (i + self.offset) % len(GRADIENT)
            text.append(char, style=f"bold {GRADIENT[color_idx]}")
        self.update(text)


class PulsingDot(Static):
    """Pulsing status indicator."""

    DEFAULT_CSS = """
    PulsingDot {
        width: 3;
        height: 1;
    }
    """

    pulse = reactive(0)

    def __init__(self, color: str = "primary"):
        super().__init__()
        self._color = COLORS.get(color, color)

    def on_mount(self) -> None:
        self.set_interval(0.3, self._tick)

    def _tick(self) -> None:
        self.pulse = (self.pulse + 1) % 4
        self._render()

    def _render(self) -> None:
        dots = ["○", "◔", "●", "◔"]
        dot = dots[self.pulse]
        self.update(Text(f" {dot} ", style=f"bold {self._color}"))


class ParticleField(Static):
    """Animated particle field background effect."""

    DEFAULT_CSS = """
    ParticleField {
        width: 100%;
        height: 3;
    }
    """

    frame = reactive(0)

    PARTICLES = ["·", "∙", "•", "◦", "○", "◌", "◯", "✦", "✧", "⋆", "∗", "⁕"]

    def __init__(self, width: int = 60, height: int = 3, density: float = 0.1):
        super().__init__()
        self._width = width
        self._height = height
        self._density = density
        self._field = self._generate_field()

    def _generate_field(self) -> list[list[str]]:
        field = []
        for _ in range(self._height):
            row = []
            for _ in range(self._width):
                if random.random() < self._density:
                    row.append(random.choice(self.PARTICLES))
                else:
                    row.append(" ")
            field.append(row)
        return field

    def on_mount(self) -> None:
        self.set_interval(0.2, self._tick)

    def _tick(self) -> None:
        self.frame += 1
        # Shift particles
        for row in self._field:
            row.insert(0, row.pop())
        
        # Randomly add/remove particles
        for y, row in enumerate(self._field):
            for x in range(len(row)):
                if random.random() < 0.02:
                    if row[x] == " ":
                        row[x] = random.choice(self.PARTICLES)
                    else:
                        row[x] = " "
        
        self._render()

    def _render(self) -> None:
        text = Text()
        for row in self._field:
            for char in row:
                if char != " ":
                    color = random.choice(GRADIENT)
                    text.append(char, style=f"{color} dim")
                else:
                    text.append(" ")
            text.append("\n")
        self.update(text)
