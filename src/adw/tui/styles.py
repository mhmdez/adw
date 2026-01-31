"""Beautiful CSS styles for ADW TUI."""

# Modern dark theme with accent colors
APP_CSS = """
/* Base Theme */
* {
    scrollbar-size: 0 0;
}

Screen {
    background: #0a0a0a;
}

/* Header */
#main-header {
    dock: top;
    height: 3;
    background: #111;
    border-bottom: solid #222;
    padding: 0 2;
}

#header-logo {
    width: auto;
    color: #00D4FF;
    text-style: bold;
}

#header-title {
    width: 1fr;
    padding-left: 2;
    color: #666;
}

#header-status {
    width: auto;
    color: #4ADE80;
}

/* Main Layout */
#main-container {
    height: 1fr;
    padding: 1 2;
}

/* Task Panel */
TaskInbox {
    width: 100%;
    height: auto;
    max-height: 12;
    background: #111;
    border: round #222;
    padding: 1;
    margin-bottom: 1;
}

TaskInbox > #inbox-header {
    height: 1;
    color: #00D4FF;
    text-style: bold;
    border-bottom: solid #222;
    padding-bottom: 1;
    margin-bottom: 1;
}

.task-item {
    height: 1;
    padding: 0 1;
}

.task-item:hover {
    background: #1a1a1a;
}

.task-item.-selected {
    background: #1a2a3a;
    color: #00D4FF;
}

.task-item.-running {
    color: #00D4FF;
}

.task-item.-blocked {
    background: #2a1a1a;
}

/* Detail Panel */
DetailPanel {
    width: 100%;
    height: 1fr;
    background: #111;
    border: round #222;
    padding: 1;
}

DetailPanel > #detail-header {
    display: none;
}

#log-viewer {
    height: 1fr;
    background: #0a0a0a;
    border: solid #222;
    padding: 1;
}

/* Status Line */
StatusLine {
    dock: bottom;
    height: 3;
    background: #111;
    border-top: solid #222;
    padding: 0 2;
}

StatusLine > #prompt {
    width: 3;
    color: #00D4FF;
    text-style: bold;
}

StatusLine > Input {
    width: 1fr;
    background: #0a0a0a;
    border: none;
    padding: 0 1;
}

StatusLine > Input:focus {
    border: none;
    background: #111;
}

StatusLine > #status-info {
    width: auto;
    color: #666;
    padding: 0 1;
}

/* Animations - note: Textual doesn't support CSS animations */
.spinner {
    color: #00D4FF;
}

.pulse {
    color: #00D4FF;
    text-style: bold;
}

/* Modals */
ModalScreen {
    align: center middle;
    background: rgba(0, 0, 0, 0.85);
}

QuestionModal #question-container,
DiscussModal #discuss-container {
    background: #111;
    border: round #00D4FF;
    padding: 2;
}

/* Phase Indicator */
PhaseIndicator {
    height: 1;
    background: #111;
    border-bottom: solid #222;
    padding: 0 2;
}

/* Accent Colors */
.accent-primary {
    color: #00D4FF;
}

.accent-success {
    color: #4ADE80;
}

.accent-warning {
    color: #FBBF24;
}

.accent-error {
    color: #EF4444;
}

.accent-purple {
    color: #A78BFA;
}

.accent-pink {
    color: #F472B6;
}

/* Buttons */
Button {
    background: #222;
    border: solid #333;
    color: #ccc;
    margin: 0 1;
    min-width: 10;
}

Button:hover {
    background: #333;
    border: solid #444;
}

Button.-primary {
    background: #00D4FF;
    color: #000;
    border: solid #00D4FF;
}

Button.-success {
    background: #4ADE80;
    color: #000;
    border: solid #4ADE80;
}

Button.-warning {
    background: #FBBF24;
    color: #000;
    border: solid #FBBF24;
}

Button.-error {
    background: #EF4444;
    color: #fff;
    border: solid #EF4444;
}
"""

# Compact header for small terminals
HEADER_SMALL = """
#main-header {
    height: 1;
}
"""

# Note: Textual doesn't support CSS @keyframes animations
# Animations are done via reactive properties and set_interval() instead
ANIMATIONS_CSS = ""
