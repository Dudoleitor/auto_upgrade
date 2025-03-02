import json
import sys

ALIVE_CODE = 1

def update_json_file(json_file_path):
    """
    Updates the task_state in the JSON file to 'alive' for all entries of type 'tc'.
    """
    try:
        with open(json_file_path, 'r') as json_file:
            data = json.load(json_file)

        # Check that MAGIC is "CORE"
        if data['magic'] != "CORE":
            raise ValueError("Invalid magic value in the JSON file")

        # Update task_state for all 'tc' entries
        updated_entries = 0
        for entry in data['entries']:
            tc = entry['tc']
            if tc:
                task_state = tc['task_state']
                if (task_state != ALIVE_CODE):
                    tc['task_state'] = ALIVE_CODE
                    updated_entries += 1

        if updated_entries == 0:
            print("No tasks found to update")
            return

        # Write updated data back to the JSON file
        with open(json_file_path, 'w') as json_file:
            json.dump(data, json_file, indent=4)

        print(f"Successfully updated {updated_entries} task(s) to 'Alive'")

    except FileNotFoundError:
        print(f"File {json_file_path} not found")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Invalid JSON format in {json_file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 update_json.py <json_file_path>")
        sys.exit(1)

    json_file_path = sys.argv[1]
    update_json_file(json_file_path)
