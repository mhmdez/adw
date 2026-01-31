"""ADW Branding - ASCII art, colors, and fun messages."""

import random

# Big ASCII logo
LOGO = """
 █████╗ ██████╗ ██╗    ██╗
██╔══██╗██╔══██╗██║    ██║
███████║██║  ██║██║ █╗ ██║
██╔══██║██║  ██║██║███╗██║
██║  ██║██████╔╝╚███╔███╔╝
╚═╝  ╚═╝╚═════╝  ╚══╝╚══╝ 
"""

LOGO_SMALL = """
┌─┐┌┬┐┬ ┬
├─┤ │││││
┴ ┴─┴┘└┴┘
"""

TAGLINE = "AI Developer Workflow"
SUBTITLE = "Ship features while you sleep"

# Loading messages - fun and varied
LOADING_MESSAGES = [
    "Waking up the agents...",
    "Brewing digital coffee...",
    "Summoning Claude...",
    "Spinning up worktrees...",
    "Consulting the oracle...",
    "Parsing the matrix...",
    "Initializing awesome...",
    "Loading creativity...",
    "Charging flux capacitor...",
    "Defragmenting thoughts...",
    "Compiling brilliance...",
    "Syncing neurons...",
    "Downloading inspiration...",
    "Calibrating AI...",
    "Warming up GPUs...",
]

THINKING_MESSAGES = [
    "🤔 Thinking...",
    "💭 Processing...",
    "🧠 Computing...",
    "⚡ Analyzing...",
    "🔮 Predicting...",
    "✨ Creating...",
]

SUCCESS_MESSAGES = [
    "🎉 Nailed it!",
    "✨ Beautiful!",
    "🚀 Shipped!",
    "💫 Done!",
    "🌟 Perfect!",
    "⚡ Lightning fast!",
]

ERROR_MESSAGES = [
    "💥 Oops!",
    "🔥 Houston, we have a problem",
    "😅 That didn't work",
    "🤖 Beep boop error",
]

# Color palette (rich markup)
COLORS = {
    "primary": "#00D4FF",      # Cyan
    "secondary": "#FF6B6B",    # Coral
    "success": "#4ADE80",      # Green
    "warning": "#FBBF24",      # Amber
    "error": "#EF4444",        # Red
    "muted": "#6B7280",        # Gray
    "accent": "#A78BFA",       # Purple
    "highlight": "#F472B6",    # Pink
}

# Gradient for fancy text
GRADIENT = ["#FF6B6B", "#FBBF24", "#4ADE80", "#00D4FF", "#A78BFA", "#F472B6"]

# Fun spinners
SPINNERS = {
    "dots": ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
    "braille": ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"],
    "arrows": ["←", "↖", "↑", "↗", "→", "↘", "↓", "↙"],
    "bounce": ["⠁", "⠂", "⠄", "⠂"],
    "pulse": ["◜", "◠", "◝", "◞", "◡", "◟"],
    "moon": ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘"],
    "clock": ["🕐", "🕑", "🕒", "🕓", "🕔", "🕕", "🕖", "🕗", "🕘", "🕙", "🕚", "🕛"],
    "earth": ["🌍", "🌎", "🌏"],
    "dots_grow": ["·", "•", "●", "•"],
    "wave": ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█", "▇", "▆", "▅", "▄", "▃", "▂"],
}

# Progress bar styles
PROGRESS_STYLES = {
    "block": ("█", "░"),
    "shade": ("▓", "░"),
    "smooth": ("━", "─"),
    "dots": ("●", "○"),
    "arrows": ("▶", "▷"),
}


def get_loading_message() -> str:
    return random.choice(LOADING_MESSAGES)


def get_thinking_message() -> str:
    return random.choice(THINKING_MESSAGES)


def get_success_message() -> str:
    return random.choice(SUCCESS_MESSAGES)


def get_error_message() -> str:
    return random.choice(ERROR_MESSAGES)


def get_spinner(name: str = "dots") -> list[str]:
    return SPINNERS.get(name, SPINNERS["dots"])


def gradient_text(text: str) -> str:
    """Apply gradient colors to text."""
    result = []
    for i, char in enumerate(text):
        color = GRADIENT[i % len(GRADIENT)]
        result.append(f"[{color}]{char}[/]")
    return "".join(result)


def rainbow_line(width: int = 60) -> str:
    """Create a rainbow gradient line."""
    chars = "─" * width
    return gradient_text(chars)
