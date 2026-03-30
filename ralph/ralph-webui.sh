#!/usr/bin/env bash
while :; do
    cat ralph/RALPH_PROMPT_WEBUI.md | claude -p --dangerously-skip-permissions
    sleep 2
done
