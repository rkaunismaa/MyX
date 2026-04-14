#!/usr/bin/env bash
# Launch Chromium with remote debugging enabled, reusing your existing profile.
chromium-browser \
  --remote-debugging-port=9222 \
  --user-data-dir=/home/rob/.config/chromium \
  "$@"
