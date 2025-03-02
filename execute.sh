#!/bin/bash

# If not defined, set the path to the configuration file
if [ -z "$EXECUTE_CONFIG_FILE" ]; then
  EXECUTE_CONFIG_FILE="$(dirname "$0")/execute.conf"
fi
if [ ! -f "$EXECUTE_CONFIG_FILE" ]; then
  echo "Error: Configuration file not found: $EXECUTE_CONFIG_FILE"
  exit 1
fi

source "$EXECUTE_CONFIG_FILE"

cleanup() {
  if [ -n "$PID " ]; then
    kill -9 $PID 2>/dev/null
  fi
}
trap cleanup EXIT

# Start the execution with the previous version
LD_LIBRARY_PATH=$OLD_LIB_FOLDER_TO_PRELOAD:$LD_LIBRARY_PATH "$EXE_FILE" > /dev/null <&1 2>&1 &

PID=$!

sleep 3.123  # Wait for the process to execute
$UPDATE_SCRIPT $PID $OLD_LIB_NAME $NEW_LIB_FILE > /dev/null
exit $?
