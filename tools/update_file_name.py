import json
import sys

def update_criu_name(json_file_path, library_filename, new_name):
    """
    Updates the name in the CRIU checkpoint JSON file.
    """

    with open(json_file_path, 'r') as json_file:
        data = json.load(json_file)

    # Check that MAGIC is "FILES"
    if data['magic'] != 'FILES':
        raise ValueError("Invalid magic value in the CRIU files.json file")

    # Find and update the entry with name ending with the library filename
    lib_entry_found = False
    for entry in data['entries']:
        if entry['type'] == 'REG' and library_filename in entry['reg']['name']:
            entry['reg']['name'] = new_name
            lib_entry_found = True
            break
    
    if not lib_entry_found:
        raise ValueError("No entry found for the library in the CRIU files.json file")

    with open(json_file_path, 'w') as json_file:
        json.dump(data, json_file, indent=4)

    print(f"Updated name to {new_name}.")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 update_name.py <json_file_path> <library_file> <new_name>")
        sys.exit(1)

    json_file_path = sys.argv[1]
    library_filename = sys.argv[2]
    new_name = sys.argv[3]

    update_criu_name(json_file_path, library_filename, new_name)
