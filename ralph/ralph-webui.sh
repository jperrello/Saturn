#!/usr/bin/env bash
while :; do
    if ! bd ready 2>/dev/null | grep -q .; then
        echo "ralph: all beads closed, exiting loop"
        break
    fi
    cat ralph/RALPH_PROMPT_WEBUI.md | claude -p --dangerously-skip-permissions
    sleep 2
done
