import json
import sys

# Path to the JSON file
json_file_path = sys.argv[1]

# Read the library file
library_filename = sys.argv[2]

# Read the current size of the shared library
library_size = sys.argv[3]

# Load the JSON data
with open(json_file_path, 'r') as json_file:
    data = json.load(json_file)

# Check that MAGIC is "FILES"
if data['magic'] != 'FILES':
    raise ValueError("Invalid magic value in the CRIU files.json file")

# Update the size in the JSON data
found_lib_entry = False
for entry in data['entries']:
    if entry['type'] == 'REG' and library_filename in entry['reg']['name']:
        entry['reg']['size'] = library_size
        found_lib_entry = True
        break

if not found_lib_entry:
    raise ValueError("No entry found for the library in the CRIU files.json file")

# Save the updated JSON data back to the file
with open(json_file_path, 'w') as json_file:
    json.dump(data, json_file, indent=4)

print(f"Updated size of {library_filename} to {library_size} bytes.")

