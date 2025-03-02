import argparse
import re
from typing import BinaryIO, List

class MemoryMapping:
    def __init__(self, start: int, end: int, perms: str, offset: int, path: str = ""):
        self.start = start
        self.end = end
        self.perms = perms
        self.offset = offset
        self.path = path
        self.size = end - start

    @staticmethod
    def parse_proc_line(line: str) -> 'MemoryMapping':
        # Example line: 7ff7bcee7000-7ff7bcee8000 r--p 00000000 08:01 2753574    /usr/lib64/ld-linux-x86-64.so.2
        pattern = r'([0-9a-f]+)-([0-9a-f]+)\s+([rwxps-]+)\s+([0-9a-f]+)\s+([0-9a-f]+:[0-9a-f]+)\s+(\d+)\s*(.*)'
        match = re.match(pattern, line.strip())
        if not match:
            raise ValueError(f"Invalid mapping line: {line}")
        
        return MemoryMapping(
            start=int(match.group(1), 16),
            end=int(match.group(2), 16),
            perms=match.group(3),
            offset=int(match.group(4), 16),
            path=match.group(7).strip()
        )

    @staticmethod
    def parse_gdb_line(line: str) -> 'MemoryMapping':
        # Example: 0x400000           0x401000     0x1000        0x0  r--p   /path/to/file
        pattern = r'\s*0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+0x[0-9a-f]+\s+0x([0-9a-f]+)\s+([rwxp-]+)\s*(.*)'
        match = re.match(pattern, line.strip())
        if not match:
            raise ValueError(f"Invalid GDB mapping line: {line}")
        
        return MemoryMapping(
            start=int(match.group(1), 16),
            end=int(match.group(2), 16),
            perms=match.group(4),
            offset=int(match.group(3), 16),
            path=match.group(5).strip()
        )


    def __str__(self):
        return f"{hex(self.start)}-{hex(self.end)} {self.perms} {hex(self.offset)} {self.path}"

def parse_mappings_file(filename: str, gdb_format: bool = False) -> List[MemoryMapping]:
    with open(filename, 'r') as f:
        mappings = []

        for line in f:
            if line.strip():
                try:
                    if gdb_format:
                        mapping = MemoryMapping.parse_gdb_line(line)
                    else:
                        mapping = MemoryMapping.parse_proc_line(line)
                    mappings.append(mapping)
                except ValueError as e:
                    print(f"Warning: Skipping invalid line: {e}")
        return mappings

def normalize_library_path(path: str) -> str:
    """
    Normalize library path by removing version numbers.
    Example: 'libexample.so.1.2.3' -> 'libexample.so'
    """
    if not path or is_special_mapping(path):
        return path
    
    # Regular expression to match version numbers in library names
    # Matches patterns like: .1.2.3, -1.2.3, _1.2.3
    return re.sub(r'[._-]\d+(\.\d+)*(?=\s*$|/)', '', path)

def group_mappings_by_path(mappings: List[MemoryMapping]) -> dict:
    """Group mappings by their normalized file path."""
    grouped = {}
    for mapping in mappings:
        path = mapping.path if mapping.path else "[anonymous]"
        normalized_path = normalize_library_path(path)
        if normalized_path not in grouped:
            grouped[normalized_path] = []
        grouped[normalized_path].append(mapping)
    return grouped

def is_special_mapping(path: str) -> bool:
    """Check if the path is a special mapping (enclosed in square brackets)."""
    return path.startswith('[') and path.endswith(']')

def validate_grouped_mappings(src_groups: dict, dst_groups: dict):
    """Validate that source and destination groups match."""
    # Check if all paths in source exist in destination and vice versa
    src_paths = set(src_groups.keys())
    dst_paths = set(dst_groups.keys())
    
    missing_in_dst = src_paths - dst_paths
    missing_in_src = dst_paths - src_paths
    
    if missing_in_dst or missing_in_src:
        error_msg = []
        if missing_in_dst:
            for path in missing_in_dst:
                msg = f"File in source but not in destination: {path}"
                if is_special_mapping(path):
                    print(f"Warning: {msg}")
                else:
                    error_msg.append(msg)
        if missing_in_src:
            for path in missing_in_src:
                msg = f"File in destination but not in source: {path}"
                if is_special_mapping(path):
                    print(f"Warning: {msg}")
                else:
                    error_msg.append(msg)
        if error_msg:  # Only raise error if there are non-special mapping mismatches
            raise ValueError("\n".join(error_msg))

    # For each file, validate the number of mappings and their sizes match
    for path in src_paths & dst_paths:  # Intersection of paths
        src_maps = src_groups[path]
        dst_maps = dst_groups[path]
        
        if len(src_maps) != len(dst_maps):
            msg = (f"Number of mappings mismatch for {path}:\n"
                  f"Source: {len(src_maps)} mappings ({src_maps[0].path})\n"
                  f"Destination: {len(dst_maps)} mappings ({dst_maps[0].path})")
            if is_special_mapping(path):
                print(f"Warning: {msg}")
                continue
            else:
                raise ValueError(msg)
        
        for idx, (src, dst) in enumerate(zip(src_maps, dst_maps)):
            if src.size != dst.size:
                msg = (f"Size mismatch in {path} at mapping {idx + 1}:\n"
                      f"Source:      {str(src)}\n"
                      f"             size: {hex(src.size)}\n"
                      f"Destination: {str(dst)}\n"
                      f"             size: {hex(dst.size)}")
                if is_special_mapping(path):
                    print(f"Warning: {msg}")
                else:
                    raise ValueError(msg)

def process_file(input_file: BinaryIO, output_file: BinaryIO, 
                src_mappings: List[MemoryMapping], dst_mappings: List[MemoryMapping], 
                address_size: int):
    """Process the binary file and translate addresses based on mappings."""
    chunk_size = address_size // 8
    
    # Group mappings by normalized path
    src_groups = group_mappings_by_path(src_mappings)
    dst_groups = group_mappings_by_path(dst_mappings)
    
    # Validate grouped mappings
    validate_grouped_mappings(src_groups, dst_groups)

    # Create translations list
    translations = []
    print("\nMapping translations by file:")
    print("=" * 60)
    
    for path in sorted(src_groups.keys()):
        src_maps = src_groups[path]
        dst_maps = dst_groups[path]
        
        print(f"\nFile: {path}")
        if src_maps[0].path != dst_maps[0].path:
            print(f"Source: {src_maps[0].path}")
            print(f"Destination: {dst_maps[0].path}")
        print("-" * 60)
        
        for idx, (src, dst) in enumerate(zip(src_maps, dst_maps)):
            shift = dst.start - src.start
            translations.append((src.start, src.end, shift))
            print(f"Region {idx + 1}:")
            print(f"  Source:      {hex(src.start)}-{hex(src.end)} ({hex(src.size)} bytes)")
            print(f"  Destination: {hex(dst.start)}-{hex(dst.end)} ({hex(dst.size)} bytes)")
            print(f"  Shift:       {hex(shift)}")
            print(f"  Permissions: {src.perms}")

    print("\nProcessing file...")
    while True:
        chunk = input_file.read(chunk_size)
        if not chunk:
            break
        
        if len(chunk) != chunk_size:
            output_file.write(chunk)
            break
            
        address = int.from_bytes(chunk, byteorder='little')
        
        # Check each mapping range
        modified = False
        for start, end, shift in translations:
            if start <= address <= end:
                new_address = address + shift
                output_file.write(new_address.to_bytes(chunk_size, byteorder='little'))
                modified = True
                break
        
        if not modified:
            output_file.write(chunk)

def main():
    parser = argparse.ArgumentParser(
        description='Translate addresses in a binary file based on memory mappings.',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    
    parser.add_argument('input_file', help='Input binary file path')
    parser.add_argument('output_file', help='Output binary file path')
    parser.add_argument('--src-maps', required=True, help='Source process memory mappings file')
    parser.add_argument('--dst-maps', required=True, help='Destination process memory mappings file')
    parser.add_argument('--bits', choices=[32, 64], type=int, default=64,
                        help='Address size in bits (32 or 64, default: 64)')
    parser.add_argument('--src-gdb', action='store_true',
                        help='Parse source mapping file in GDB "info proc mappings" format')
    parser.add_argument('--dst-gdb', action='store_true',
                        help='Parse destination mapping file in GDB "info proc mappings" format')
    
    args = parser.parse_args()

    try:
        # Parse mapping files
        print(f"\nReading source mappings from: {args.src_maps}")
        print(f"Using {'GDB' if args.src_gdb else 'proc'} format")
        src_mappings = parse_mappings_file(args.src_maps, args.src_gdb)
        
        print(f"Reading destination mappings from: {args.dst_maps}")
        print(f"Using {'GDB' if args.dst_gdb else 'proc'} format")
        dst_mappings = parse_mappings_file(args.dst_maps, args.dst_gdb)

        print(f"\nProcessing with {args.bits}-bit addresses")
        print(f"Source mappings: {len(src_mappings)} entries")
        print(f"Destination mappings: {len(dst_mappings)} entries")

        with open(args.input_file, 'rb') as input_file, \
             open(args.output_file, 'wb') as output_file:
            process_file(input_file, output_file, src_mappings, dst_mappings, args.bits)
            print(f"\nProcessing complete. Output written to {args.output_file}")
            
    except FileNotFoundError as e:
        print(f"Error: File not found - {e}")
        exit(1)
    except PermissionError:
        print(f"Error: Permission denied when accessing files.")
        exit(1)
    except ValueError as e:
        print(f"Error: {str(e)}")
        exit(1)
    except Exception as e:
        print(f"Error: An unexpected error occurred: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()
