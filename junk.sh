#!/usr/bin/env bash

LOCKFILE="/tmp/move_to_junk.lock"
ROOT="/home/coworking/email_filter/"
SCRIPT="main.py"

cd $ROOT

LIMIT=""

# Parse arguments
while getopts "l:" opt; do
  case $opt in
    l)
      LIMIT="$OPTARG"
      ;;
    *)
      echo "Usage: $0 [-l <limit>]"
      exit 1
      ;;
  esac
done

# Acquire lock (fd 200)
exec 200>"$LOCKFILE"
flock -n 200 || exit 0

# Build command dynamically
if [ -n "$LIMIT" ]; then
    python3 "$SCRIPT" -l "$LIMIT" -y
else
    python3 "$SCRIPT" -y
fi

exit 0
