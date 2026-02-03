#!/bin/bash
# ADW Ralph Wiggum Loop Script
# Based on Geoffrey Huntley's methodology
#
# Usage: ./loop.sh [plan|build|phase3] [max_iterations] [--gemini]
# Examples:
#   ./loop.sh              # Build mode, unlimited iterations
#   ./loop.sh 20           # Build mode, max 20 iterations
#   ./loop.sh plan         # Plan mode, unlimited iterations
#   ./loop.sh phase3 10 --gemini  # Phase 3 mode, 10 iters, using Gemini

set -e

# Defaults
MODE="build"
PROMPT_FILE="PROMPT_build.md"
MAX_ITERATIONS=0
USE_GEMINI=false
export GEMINI_API_KEY="AIzaSyDGOFqwlTRmkECsWjACdAbefKRO7NP0ggk"

# Parse arguments
for arg in "$@"; do
    case $arg in
        plan)
            MODE="plan"
            PROMPT_FILE="PROMPT_plan.md"
            ;;
        build)
            MODE="build"
            PROMPT_FILE="PROMPT_build.md"
            ;;
        phase3)
            MODE="phase3"
            PROMPT_FILE="PROMPT_phase3.md"
            ;;
        --gemini)
            USE_GEMINI=true
            ;;
        *)
            if [[ "$arg" =~ ^[0-9]+$ ]]; then
                MAX_ITERATIONS=$arg
            fi
            ;;
    esac
done

ITERATION=0
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "main")
LOG_DIR=".adw/ralph-logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/ralph-$(date +%Y%m%d-%H%M%S).log"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🐛 ADW Ralph Wiggum Loop"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Mode: $MODE"
echo "Prompt: $PROMPT_FILE"
echo "Engine: $( [ "$USE_GEMINI" = true ] && echo "Gemini (Custom)" || echo "Claude" )"
echo "Branch: $CURRENT_BRANCH"
echo "Log: $LOG_FILE"
[ $MAX_ITERATIONS -gt 0 ] && echo "Max: $MAX_ITERATIONS iterations"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Verify prompt file exists
if [ ! -f "$PROMPT_FILE" ]; then
    echo "❌ Error: $PROMPT_FILE not found"
    exit 1
fi

# Check for specs
SPEC_COUNT=$(find specs -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
echo "📋 Found $SPEC_COUNT spec files"

while true; do
    if [ $MAX_ITERATIONS -gt 0 ] && [ $ITERATION -ge $MAX_ITERATIONS ]; then
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "✅ Reached max iterations: $MAX_ITERATIONS"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        break
    fi

    ITERATION=$((ITERATION + 1))
    TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
    
    echo "" | tee -a "$LOG_FILE"
    echo "════════════════════ ITERATION $ITERATION ($TIMESTAMP) ════════════════════" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"

    # Run Ralph iteration
    if [ "$USE_GEMINI" = true ]; then
        # Gemini Mode (using custom wrapper in tools/gemini-cli/cli.py)
        echo "🤖 Running Gemini..."
        # We invoke the python script directly.
        # Assuming uv is available and .venv is set up in tools/gemini-cli
        cd tools/gemini-cli && uv run cli.py "$(cat ../../$PROMPT_FILE)" 2>&1 | tee -a "../../$LOG_FILE"
        cd ../..
    else
        # Claude Mode
        echo "🤖 Running Claude..."
        cat "$PROMPT_FILE" | claude -p \
            --dangerously-skip-permissions \
            --model opus \
            --verbose 2>&1 | tee -a "$LOG_FILE"
    fi

    # Check for completion signal
    if grep -q "RALPH_COMPLETE" "$LOG_FILE"; then
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "🎉 Ralph signaled completion!"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        break
    fi

    # Push changes after each iteration
    if [ "$CURRENT_BRANCH" != "no-git" ]; then
        git push origin "$CURRENT_BRANCH" 2>/dev/null || {
            echo "Creating remote branch..."
            git push -u origin "$CURRENT_BRANCH" 2>/dev/null || true
        }
    fi

    # Brief pause between iterations
    echo "⏳ Cooling down before next iteration..."
    sleep 3
done

echo ""
echo "🎉 Ralph loop complete!"
echo "Total iterations: $ITERATION"
echo "Log: $LOG_FILE"
