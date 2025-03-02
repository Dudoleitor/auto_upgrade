import sys

def main():
    # Check if exactly two arguments are provided
    if len(sys.argv) != 3:
        print("Usage: python script_name.py <lower_bound> <upper_bound>")
        sys.exit(2)

    # Get the bounds from argv
    try:
        lower = int(sys.argv[1], 16)
        upper = int(sys.argv[2], 16)
    except ValueError:
        print("Error: Invalid hex value for bounds")
        sys.exit(2)

    # Read from stdin
    for line in sys.stdin:
        line = line.strip()
        try:
            address = int(line, 16)
            if lower <= address <= upper:
                sys.exit(1)  # Return 1 if match found
        except ValueError:
            # Skip invalid hex lines
            pass

    # If no match found
    sys.exit(0)

if __name__ == "__main__":
    main()
