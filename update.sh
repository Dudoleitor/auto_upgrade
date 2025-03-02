#!/bin/bash

# Path and names of the executable and the library to be upgraded
PID=$1 
if [ -z "$PID" ]; then
  echo "Usage: $0 <PID>"
  exit 1
fi

ps -p $PID > /dev/null
retval=$?
if [ $retval -ne 0 ]; then
  echo "Error: Process with PID $PID not found."
  exit $retval
fi
EXE_NAME=$(ps -p $PID -o comm=)
EXE_FILE=$(readlink -f /proc/$PID/exe)

OLD_LIB_NAME=$2  # e.g., "libz.so.1.2.12", must be the name of the library as it appears in /proc/PID/maps
if [ -z "$OLD_LIB_NAME" ]; then
  echo "Usage: $0 <PID> <old_lib_name>"
  exit 1
fi

cat /proc/$PID/maps | grep -q "$OLD_LIB_NAME" > /dev/null
retval=$?
if [ $retval -ne 0 ]; then
  echo "Error: Library $OLD_LIB_NAME not found in process $PID." >&2
  exit $retval
fi

NEW_LIB_FILE=$3  # e.g., "/home/user/zlib-1.3.1/libz.so.1.3.1", must be the full path to the new library
if [ -z "$NEW_LIB_FILE" ]; then
  echo "Usage: $0 <PID> <old_lib_name> <new_lib_file>" >&2
  exit 1
fi

if [ ! -f "$NEW_LIB_FILE" ]; then
  echo "New library file does not exist: $NEW_LIB_FILE" >&2
  exit 1
fi

NEW_LIB_FOLDER_TO_PRELOAD=$(dirname "$NEW_LIB_FILE")
retval=$?
if [ $retval -ne 0 ]; then
  echo "Error: Could not determine the folder to preload the new library." >&2
  exit $retval
fi

CLEANUP=1  # 0 or 1

# If not defined, set the path to the configuration file
if [ -z "$UPDATE_CONFIG_FILE" ]; then
  UPDATE_CONFIG_FILE="../update.conf"
fi
if [ ! -f "$UPDATE_CONFIG_FILE" ]; then
  echo "Error: Configuration file not found: $UPDATE_CONFIG_FILE" >&2
  exit 1
fi
source "$UPDATE_CONFIG_FILE"

CRIU_OPTS="-j -v4 --skip-file-rwx-check"

###############################################

echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope   # TODO 
echo 1 | sudo tee /proc/sys/kernel/randomize_va_space
mkdir -p checkpoint; rm -f checkpoint/*;

# Getting information about the old library
OLD_LIB_FILE=$(cat /proc/$PID/maps | grep -m 1 "$OLD_LIB_NAME" | awk '{print $6}')
OLD_LIB_FOLDER_TO_PRELOAD=$(dirname "$OLD_LIB_FILE")

FIRST_PAGE_ELF_START=0x$(readelf -SW "$EXE_FILE" | grep " .got " | awk '{print $4}')
FIRST_PAGE_ELF_END=0x$(readelf -SW "$EXE_FILE" | grep " .data " | awk '{print $4}')

SECOND_PAGE_ELF_START=$(readelf -lW "$OLD_LIB_FILE" | grep " LOAD " | grep " RW " | awk '{print $3}')
SECOND_PAGE_ELF_SIZE=$(readelf -lW "$OLD_LIB_FILE" | grep " LOAD " | grep " RW " | awk '{print $5}')
SECOND_PAGE_ELF_END=$(python3 -c "print(hex(int('$SECOND_PAGE_ELF_START', 16) + int('$SECOND_PAGE_ELF_SIZE', 16)))")

DYNAMIC_ELF_START=$(readelf -lW "$OLD_LIB_FILE" | grep " DYNAMIC " | awk '{print $3}')
DYNAMIC_ELF_SIZE=$(readelf -lW "$OLD_LIB_FILE" | grep " DYNAMIC " | awk '{print $5}')
DYNAMIC_ELF_END=$(python3 -c "print(hex(int('$DYNAMIC_ELF_START', 16) + int('$DYNAMIC_ELF_SIZE', 16)))")

# Ensure that the DYNAMIC section is inside the LOAD RW segment
if [[ $(python3 -c "print(int('$DYNAMIC_ELF_START', 16) >= int('$SECOND_PAGE_ELF_START', 16) and int('$DYNAMIC_ELF_END', 16) <= int('$SECOND_PAGE_ELF_END', 16))") == "False" ]]; then
    echo "DYNAMIC section is not inside the LOAD RW segment" >&2
    exit 1
fi

# Ensure that the executable and the library are valid ELF files
readelf -h $EXE_FILE > /dev/null
if [[ $? -ne 0 ]]; then
    echo "Executable file is not an ELF file" >&2
    exit 1
fi
readelf -h $OLD_LIB_FILE > /dev/null
if [[ $? -ne 0 ]]; then
    echo "Old library file is not an ELF file" >&2
    exit 1
fi
readelf -h $NEW_LIB_FILE > /dev/null
if [[ $? -ne 0 ]]; then
    echo "New library file is not an ELF file" >&2
    exit 1
fi

EXE_ELF_TYPE="$(readelf -h $EXE_FILE | grep 'Type:' | awk '{print $2}')"
if [[ "$EXE_ELF_TYPE" != "EXEC" && "$EXE_ELF_TYPE" != "DYN" ]]; then
    echo "Executable file is not an ELF executable" >&2
    exit 1
fi

LIB_ELF_TYPE="$(readelf -h $OLD_LIB_FILE | grep 'Type:' | awk '{print $2}')"
if [[ "$LIB_ELF_TYPE" != "DYN" ]]; then
    echo "Library file is not an ELF DYN object" >&2
    exit 1
fi

# Gather information about the current execution
LIB_BASE_ADDR=0x$(cat /proc/$PID/maps | grep -m 1 "$OLD_LIB_FILE" | awk '{print $1}' | awk -F '-' '{print $1}')
cat /proc/$PID/maps > real_mappings.txt


if [[ "$EXE_ELF_TYPE" == "EXEC" ]]; then
  EXE_BASE_ADDR="0x0"
  EXE_BASE_TO_ADD=""
else  # DYN
  EXE_BASE_ADDR=0x$(cat /proc/$PID/maps | grep -m 1 "$EXE_NAME" | awk '{print $1}' | awk -F '-' '{print $1}')
  EXE_BASE_TO_ADD="\$exe_base_addr +"
fi

# Getting the range of addresses of the library
LIB_START_ADDR=$LIB_BASE_ADDR
LIB_END_ADDR=0x$(cat /proc/$PID/maps | grep "$OLD_LIB_FILE" | tail -n 1 | awk '{print $1}' | awk -F '-' '{print $2}')

# Using gdb to wait until the execution is outside the library we want to upgrade
echo "set \$outside_lib = 0" > .gdbtmp
echo "catch syscall" >> .gdbtmp
echo "while ( \$outside_lib == 0 )" >> .gdbtmp
echo "  pipe info stack | awk '{print \$2}' | python3 $CHECK_HEX_RANGE $LIB_START_ADDR $LIB_END_ADDR" >> .gdbtmp 
echo "  if ( \$_shell_exitcode == 0 && (\$pc < $LIB_START_ADDR || \$pc > $LIB_END_ADDR ) )" >> .gdbtmp
echo "    set \$outside_lib = 1" >> .gdbtmp
echo "  else" >> .gdbtmp
echo "    continue" >> .gdbtmp
echo "  end" >> .gdbtmp
echo "end" >> .gdbtmp
LD_LIBRARY_PATH=$OLD_LIB_FOLDER_TO_PRELOAD:$LD_LIBRARY_PATH gdb -p $PID -batch \
-ex "p \$pc" \
-ex "source .gdbtmp" \
-ex "!kill -SIGSTOP $PID" \
-ex "p \$pc" \
-ex "detach" \
-ex "quit"

# Perform the checkpoint
sudo $CRIU dump -D checkpoint -t $PID $CRIU_OPTS -o dump.log
retcode=$?
if [ $retcode -ne 0 ]; then
  echo "Error during checkpointing" >&2
  sudo tail checkpoint/dump.log >&2
  exit $retcode
fi

sudo chown $(id -u):$(id -g) -R checkpoint

# Performing the upgrade

# Gathering information for the new execution, starting a new process with GDB to dump the memory
printf 'set $exe_base_addr = ' > .gdbtmp1
printf 'set $lib_base_addr = ' > .gdbtmp2
LD_LIBRARY_PATH=$NEW_LIB_FOLDER_TO_PRELOAD:$LD_LIBRARY_PATH gdb "$EXE_FILE" -batch \
-ex "break main" -ex "run" \
-ex "pipe info proc mappings | tail -n +5 | head -n -1 > synthetic_mappings.txt" \
-ex "pipe info proc mappings | grep -m 1 $EXE_NAME | awk '{print \$1 }' >> .gdbtmp1" \
-ex "source .gdbtmp1" \
-ex "set \$first_page_elf_start = $FIRST_PAGE_ELF_START" \
-ex "set \$first_page_start = $EXE_BASE_TO_ADD \$first_page_elf_start" \
-ex "set \$first_page_elf_end = $FIRST_PAGE_ELF_END" \
-ex "set \$first_page_end = $EXE_BASE_TO_ADD \$first_page_elf_end" \
-ex "dump binary memory memory_dump_1.bin \$first_page_start \$first_page_end" \
-ex "pipe info proc mappings | grep -m 1 $NEW_LIB_FILE | awk '{print \$1 }' >> .gdbtmp2" \
-ex "source .gdbtmp2" \
-ex "set \$second_page_elf_start = $SECOND_PAGE_ELF_START" \
-ex "set \$second_page_start = \$lib_base_addr + \$second_page_elf_start" \
-ex "set \$second_page_elf_size = $SECOND_PAGE_ELF_SIZE" \
-ex "set \$second_page_end = \$second_page_start + \$second_page_elf_size" \
-ex "dump binary memory memory_dump_2.bin \$second_page_start \$second_page_end" \
-ex "quit"

python3 $SHIFT_ADDRESSES memory_dump_1.bin memory_dump_1_translated.bin --src-gdb --src-maps synthetic_mappings.txt --dst-maps real_mappings.txt
python3 $SHIFT_ADDRESSES memory_dump_2.bin memory_dump_2_translated.bin --src-gdb --src-maps synthetic_mappings.txt --dst-maps real_mappings.txt

FIRST_PAGE_START=$(python3 -c "print(hex(int('$EXE_BASE_ADDR', 16) + int('$FIRST_PAGE_ELF_START', 16)))")
SECOND_PAGE_START=$(python3 -c "print(hex(int('$LIB_BASE_ADDR', 16) + int('$SECOND_PAGE_ELF_START', 16)))")

# Updating the memory with data from the synthetic execution
$CRIT edit -b memory_dump_1_translated.bin checkpoint/pages-1.img "$(python3 $TRANSLATE_ADDRESSES checkpoint "$FIRST_PAGE_START" --result-only)"
$CRIT edit -b memory_dump_2_translated.bin checkpoint/pages-1.img "$(python3 $TRANSLATE_ADDRESSES checkpoint "$SECOND_PAGE_START" --result-only)"

# Updating criu information stored in files.img
echo "Changing library file name, size and build id: from $OLD_LIB_FILE to $NEW_LIB_FILE"
$CRIT decode -i checkpoint/files.img -o checkpoint/files.json
python3 $UPDATE_FILE_NAME checkpoint/files.json $OLD_LIB_FILE $NEW_LIB_FILE
python3 $UPDATE_LIB_SIZE checkpoint/files.json $NEW_LIB_FILE $(stat --format="%s" $NEW_LIB_FILE)
python3 $UPDATE_BUILD_ID checkpoint/files.json $NEW_LIB_FILE
$CRIT encode -o checkpoint/files.img -i checkpoint/files.json

# Updating criu information stored in core-PID.img
checkpoint_core_file=$(ls checkpoint/core-*.img)
$CRIT decode -i $checkpoint_core_file -o checkpoint/core.json
python3 $SET_THREAD_ALIVE checkpoint/core.json
$CRIT encode -o $checkpoint_core_file -i checkpoint/core.json; # rm checkpoint/core.json

# Printing some debug information
FIRST_PAGE_END=$(python3 -c "print(hex(int('$EXE_BASE_ADDR', 16) + int('$FIRST_PAGE_ELF_END', 16)))")
echo "First page: $FIRST_PAGE_START - $FIRST_PAGE_END"
SECOND_PAGE_END=$(python3 -c "print(hex(int('$SECOND_PAGE_START', 16) + int('$SECOND_PAGE_ELF_SIZE', 16)))")
echo "Second page: $SECOND_PAGE_START - $SECOND_PAGE_END"

# Restoring the process
sudo $CRIU restore -D checkpoint $CRIU_OPTS -o restore.log

retcode=$?
if [ $retcode -ne 0 ]; then
  echo "Error during restore" >&2
  sudo tail checkpoint/restore.log >&2
  exit $retcode
fi

if [ $CLEANUP -eq 1 ]; then
  rm -rf checkpoint
  rm -f .gdbtmp*
  rm -f synthetic_mappings.txt
  rm -f real_mappings.txt
  rm -f memory_dump_*.bin
fi
