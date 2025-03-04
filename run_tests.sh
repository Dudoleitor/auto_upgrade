#!/bin/bash

# Configuration
NUM_TESTS=10      # Number of parallel tests to run
MONITOR_TIME=30   # Time in seconds before checking if processes are alive

EXECUTE_SCRIPT=$(dirname "$0")/execute.sh

# Array to store PIDs
declare -a PIDS

# Function to check if a process is running
check_process() {
    ps -p $1 > /dev/null
    return $?
}

# Function to start a process
start_process() {
  $EXECUTE_SCRIPT &

  PIDS+=($!)
  echo "Started test instance $i with PID ${PIDS[-1]}"
}

# Function to cleanup processes
cleanup() {
    echo "Cleaning up processes..."
    for ((i=0; i<NUM_TESTS; i++)); do
        pid=${PIDS[$i]}
        if check_process $pid; then
            kill $pid 2>/dev/null
            echo "Killed process $pid"
            rm -rf "test_$i"
        else 
            echo "Process $pid has already terminated"
        fi
    done
}

# Trap Ctrl+C and cleanup
trap cleanup EXIT

# Start N instances of the test
echo "Starting $NUM_TESTS instances..."
for ((i=0; i<NUM_TESTS; i++)); do
  current_test_dir="test_$i"
  if [ -d "$current_test_dir" ]; then
    rm -rf "$current_test_dir"
  fi
  mkdir "$current_test_dir"
  cd "$current_test_dir" || exit
  # Start the execution with the previous version
  start_process ..
  cd .. || exit
done

# Wait for specified timeout
echo "Waiting for $MONITOR_TIME seconds..."
sleep $MONITOR_TIME

# Check if all processes are still running
echo "Checking processes..."
ALL_RUNNING=true
for pid in "${PIDS[@]}"; do
    if ! check_process $pid; then
        echo "Process $pid has crashed or terminated!"
        ALL_RUNNING=false
    fi
done

# Report status
if $ALL_RUNNING; then
    echo "All processes are running successfully"
else
    echo "Some processes have failed!"
fi

# Wait for user input before cleanup
read -p "Press Enter to terminate all processes..."

# Cleanup processes
cleanup

trap - EXIT
exit 0
