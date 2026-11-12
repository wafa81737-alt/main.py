#!/bin/bash
set -e

echo "Starting Xvfb..."
Xvfb :99 -screen 0 540x1170x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!

sleep 2

if ! kill -0 $XVFB_PID 2>/dev/null; then
    echo "❌ Xvfb failed to start"
    exit 1
fi

export DISPLAY=:99
echo "DISPLAY=$DISPLAY"

trap "kill $XVFB_PID 2>/dev/null || true" EXIT

echo "Starting bot..."
python main.py
