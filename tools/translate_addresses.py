import os
import sys
import subprocess
import json
import argparse

# Define the page size in bytes
PAGE_SIZE = 4096

def find_pagemap_file(directory):
    # List all files in the specified directory
    files = os.listdir(directory)
    
    # Filter files that match the pattern pagemap-*.img
    pagemap_files = [f for f in files if f.startswith('pagemap-') and f.endswith('.img')]
    
    # Check if there is exactly one pagemap file
    if len(pagemap_files) != 1:
        print("Error: There should be exactly one pagemap-*.img file in the directory.")
        sys.exit(1)
    
    return os.path.join(directory, pagemap_files[0])

def decode_pagemap_file(filepath):
    # Use the crit decode -i command to transform the file into JSON
    try:
        # This assumes crit is in your PATH. Otherwise, use the full path to crit.
        result = subprocess.run(['crit', 'decode', '-i', filepath], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error decoding file with crit: {e}")
        sys.exit(1)

def process_json_data(json_data, result_only):
    # Check if the JSON data contains the expected structure
    if json_data.get("magic") != "PAGEMAP":
        print("Error: Missing or incorrect 'magic' field.")
        sys.exit(1)

    entries = json_data["entries"]
    position = 0
    address_mapping = {}

    for entry in entries:
        # Check if entry contains 'vaddr' and 'nr_pages'
        if 'vaddr' in entry and 'nr_pages' in entry:
            vaddr = entry['vaddr']
            nr_pages = entry['nr_pages']

            # Calculate the end address
            end_vaddr = vaddr + nr_pages * PAGE_SIZE

            # Calculate the range of addresses inside the page
            start_address_inside_page = position * PAGE_SIZE
            end_address_inside_page = start_address_inside_page + nr_pages * PAGE_SIZE

            # Store the mapping
            address_mapping[(vaddr, end_vaddr)] = (start_address_inside_page, end_address_inside_page)

            # Print the range of virtual addresses and their corresponding range inside the page if not in result-only mode
            if not result_only:
                print(f"Position {position}: Virtual Address Range {hex(vaddr)} - {hex(end_vaddr - 1)}, "
                      f"Address Range Inside Page: {hex(start_address_inside_page)} - {hex(end_address_inside_page - 1)}")

            # Increment position by the number of pages
            position += nr_pages

    return address_mapping

def find_address_inside_page(virtual_address, address_mapping):
    # Find the virtual address range that contains the given address
    for (vaddr_range, addr_range_inside_page) in address_mapping.items():
        if vaddr_range[0] <= virtual_address < vaddr_range[1]:
            # Calculate the offset from the start of the virtual address range
            offset = virtual_address - vaddr_range[0]
            # Compute the address inside the page by adding the offset to the start address inside the page
            address_inside_page = addr_range_inside_page[0] + offset
            return address_inside_page
    return None

def main():
    parser = argparse.ArgumentParser(description="Translate a virtual address to an address inside a page.")
    parser.add_argument("checkpoint_directory", help="Directory containing the pagemap file")
    parser.add_argument("virtual_address", type=lambda x: int(x, 0), help="Virtual address to look up (supports hex with 0x prefix)")
    parser.add_argument("--result-only", action="store_true", help="Only print the result of the address lookup")
    
    args = parser.parse_args()

    if not os.path.isdir(args.checkpoint_directory):
        print("Error: Provided path is not a directory.")
        sys.exit(1)

    pagemap_file = find_pagemap_file(args.checkpoint_directory)
    if not args.result_only:
        print(f"Found pagemap file: {pagemap_file}")

    json_data = decode_pagemap_file(pagemap_file)
    address_mapping = process_json_data(json_data, args.result_only)

    address_inside_page = find_address_inside_page(args.virtual_address, address_mapping)
    if address_inside_page is not None:
        if not args.result_only:
            print(f"Virtual Address {hex(args.virtual_address)} maps to Address Inside Page: {hex(address_inside_page)}")
        else:
            print(hex(address_inside_page))
    else:
        print(f"Error: Virtual Address {hex(args.virtual_address)} is not within any known range.")
        sys.exit(1)

if __name__ == "__main__":
    main()

