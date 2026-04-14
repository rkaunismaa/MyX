#!/usr/bin/env bash
# Launch Brave with remote debugging enabled, reusing your existing profile.
brave-browser \
  --remote-debugging-port=9222 \
  --user-data-dir=/home/rob/.config/BraveSoftware/Brave-Browser \
  "$@"
