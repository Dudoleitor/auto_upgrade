import json
import sys
import subprocess

def get_build_id(elf_file_path):
    """
    Extracts the build ID from an ELF file.
    """
    try:
        # Use readelf or eu-readelf to extract the build ID
        result = subprocess.run(['readelf', '-n', elf_file_path], capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            if 'Build ID:' in line:
                build_id = line.split('Build ID:')[1].strip()

                if (len(build_id) != 40):
                    print("Wrong build id length")
                    exit(1)

                build_id_int = []
                # Convert the hexadecimal build ID to a decimal string
                for i in range(0, len(build_id), 8):
                    # Reversing couple of bytes
                    part_reversed = ''.join(reversed([build_id[i + j:i + j + 2] for j in range(0, 8, 2)]))
                    build_id_int.append(str(int(part_reversed, 16)))

                return build_id_int
    except subprocess.CalledProcessError as e:
        print(f"Error reading ELF file: {e}")
        sys.exit(1)
    
    print("Build ID not found in the ELF file.")
    sys.exit(1)

def update_criu_checkpoint(json_file_path, library_filename, new_build_id):
    """
    Updates the build ID in the CRIU checkpoint JSON file.
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
            entry['reg']['build_id'] = new_build_id
            lib_entry_found = True
            break
    
    if not lib_entry_found:
        raise ValueError("No entry found for the library in the CRIU files.json file")


    with open(json_file_path, 'w') as json_file:
        json.dump(data, json_file, indent=4)

    print(f"Updated build ID to {build_id}.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 update_build_id.py <json_file_path> <library_file>")
        sys.exit(1)

    json_file_path = sys.argv[1]
    library_filename = sys.argv[2]

    build_id = get_build_id(library_filename)
    update_criu_checkpoint(json_file_path, library_filename, build_id)

