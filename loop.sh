#!/bin/bash
# ADW Ralph Wiggum Loop Script
# Based on Geoffrey Huntley's methodology
#
# Usage: ./loop.sh [plan|build] [max_iterations]
# Examples:
#   ./loop.sh              # Build mode, unlimited iterations
#   ./loop.sh 20           # Build mode, max 20 iterations
#   ./loop.sh plan         # Plan mode, unlimited iterations
#   ./loop.sh plan 5       # Plan mode, max 5 iterations

set -e

# Parse arguments
if [ "$1" = "plan" ]; then
    MODE="plan"
    PROMPT_FILE="PROMPT_plan.md"
    MAX_ITERATIONS=${2:-0}
elif [ "$1" = "build" ]; then
    MODE="build"
    PROMPT_FILE="PROMPT_build.md"
    MAX_ITERATIONS=${2:-0}
elif [[ "$1" =~ ^[0-9]+$ ]]; then
    MODE="build"
    PROMPT_FILE="PROMPT_build.md"
    MAX_ITERATIONS=$1
else
    MODE="build"
    PROMPT_FILE="PROMPT_build.md"
    MAX_ITERATIONS=0
fi

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

# Initialize IMPLEMENTATION_PLAN.md if not exists
if [ ! -f "IMPLEMENTATION_PLAN.md" ]; then
    echo "📝 Creating IMPLEMENTATION_PLAN.md..."
    echo "# ADW Implementation Plan" > IMPLEMENTATION_PLAN.md
    echo "" >> IMPLEMENTATION_PLAN.md
    echo "*Auto-generated. Updated by Ralph loop.*" >> IMPLEMENTATION_PLAN.md
    echo "" >> IMPLEMENTATION_PLAN.md
fi

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

    # Run Ralph iteration with selected prompt
    cat "$PROMPT_FILE" | claude -p \
        --dangerously-skip-permissions \
        --model opus \
        --verbose 2>&1 | tee -a "$LOG_FILE"

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

    # Brief pause between iterations (fresh context)
    echo "⏳ Cooling down before next iteration..."
    sleep 3
done

echo ""
echo "🎉 Ralph loop complete!"
echo "Total iterations: $ITERATION"
echo "Log: $LOG_FILE"
