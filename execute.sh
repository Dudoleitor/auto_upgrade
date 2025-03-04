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
    kill -9 $PID >/dev/null 2>&1
  fi
}
trap cleanup EXIT

# Start the execution with the previous version
if [[ $DEBUG -eq 1 ]]; then
  LD_LIBRARY_PATH=$OLD_LIB_FOLDER_TO_PRELOAD:$LD_LIBRARY_PATH "$EXE_FILE" &
else
  LD_LIBRARY_PATH=$OLD_LIB_FOLDER_TO_PRELOAD:$LD_LIBRARY_PATH "$EXE_FILE" > /dev/null 2>&1 0<&1 &
fi

PID=$!

sleep 3.123  # Wait for the process to execute
if [[ $DEBUG -eq 1 ]]; then
  bash -x $UPDATE_SCRIPT $PID $OLD_LIB_NAME $NEW_LIB_FILE
else
  $UPDATE_SCRIPT $PID $OLD_LIB_NAME $NEW_LIB_FILE > execute.log 2>&1
fi
exit $?
