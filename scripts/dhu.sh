#!/usr/bin/env bash
# Manage the Desktop Head Unit (DHU) with a persistent command pipe.
#
# Usage:
#   scripts/dhu.sh start              - Start DHU with command pipe
#   scripts/dhu.sh stop               - Stop DHU
#   scripts/dhu.sh screenshot [path]  - Capture screenshot
#   scripts/dhu.sh cmd "command"      - Send arbitrary DHU console command
#   scripts/dhu.sh status             - Check if DHU is running
set -euo pipefail

DHU_BIN="${ANDROID_HOME}/extras/google/auto/desktop-head-unit"
PIPE="/tmp/dhu_cmd_pipe"
PID_FILE="/tmp/dhu.pid"
KEEPER_PID_FILE="/tmp/dhu_keeper.pid"

start_dhu() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "DHU already running (pid $(cat "$PID_FILE"))"
        return 0
    fi

    adb forward tcp:5277 tcp:5277 2>/dev/null || true
    rm -f "$PIPE"
    mkfifo "$PIPE"

    # Background process that holds the write-end open forever (prevents EOF)
    (while true; do sleep 3600; done) > "$PIPE" &
    echo $! > "$KEEPER_PID_FILE"
    disown

    # Start DHU reading from the pipe
    "$DHU_BIN" < "$PIPE" > /tmp/dhu.log 2>&1 &
    echo $! > "$PID_FILE"
    disown

    # Wait for DHU to connect
    for i in $(seq 1 12); do
        if grep -q "connected" /tmp/dhu.log 2>/dev/null; then
            echo "DHU started (pid $(cat "$PID_FILE"))"
            return 0
        fi
        sleep 1
    done

    echo "DHU started (pid $(cat "$PID_FILE")), check /tmp/dhu.log for status"
}

stop_dhu() {
    [ -f "$PID_FILE" ] && kill "$(cat "$PID_FILE")" 2>/dev/null || true
    [ -f "$KEEPER_PID_FILE" ] && kill "$(cat "$KEEPER_PID_FILE")" 2>/dev/null || true
    pkill -f desktop-head-unit 2>/dev/null || true
    rm -f "$PID_FILE" "$KEEPER_PID_FILE" "$PIPE"
    echo "DHU stopped"
}

send_cmd() {
    local cmd="$1"
    if [ ! -p "$PIPE" ]; then
        echo "ERROR: DHU not running (no pipe)" >&2
        return 1
    fi
    # Write to pipe (non-blocking since keeper holds it open)
    echo "$cmd" > "$PIPE"
}

screenshot() {
    local output="${1:-/tmp/dhu_screenshot.png}"
    rm -f "$output"
    send_cmd "screenshot $output"
    for i in $(seq 1 10); do
        if [ -f "$output" ]; then
            echo "$output"
            return 0
        fi
        sleep 0.5
    done
    echo "ERROR: screenshot not created after 5s" >&2
    return 1
}

status_check() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "DHU running (pid $(cat "$PID_FILE"))"
    else
        echo "DHU not running"
    fi
}

case "${1:-}" in
    start)      start_dhu ;;
    stop)       stop_dhu ;;
    screenshot) screenshot "${2:-/tmp/dhu_screenshot.png}" ;;
    cmd)        send_cmd "${2:?Usage: dhu.sh cmd \"command\"}" ;;
    status)     status_check ;;
    *)          echo "Usage: $0 {start|stop|screenshot [path]|cmd \"command\"|status}" ;;
esac
