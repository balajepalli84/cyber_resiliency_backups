import os
import time
import json
import xxhash  # make sure XX hash is installed

# Set the directory path to monitor
volume_mount_path = "/mnt/testmt" #replace this with valid mount path
metadata_file = "/home/opc/file_metadata.json" 

# Extensions and folders to ignore
ignore_extensions = [".tmp", ".log"]  # Add extensions you want to ignore
ignore_folders = ["ignoredir", "testmt^Cgnoredir"]  # Add folder names to ignore

def calculate_xxhash(file_path):
    hash_xx = xxhash.xxh64()  
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_xx.update(chunk)
    return hash_xx.hexdigest()

def get_file_metadata(path):
    file_metadata = {}
    ignored_files = []
    ignored_dirs = []
    
    for root, dirs, files in os.walk(path):
        # Skip directories in ignore_folders and log them
        ignored_dirs.extend([os.path.join(root, d) for d in dirs if d in ignore_folders])
        dirs[:] = [d for d in dirs if d not in ignore_folders]        
        
        for name in files:
            # Skip files with extensions in ignore_extensions and log them
            if any(name.endswith(ext) for ext in ignore_extensions):
                ignored_files.append(os.path.join(root, name))
                continue
            
            file_path = os.path.join(root, name)
            timestamp = os.path.getmtime(file_path)
            xxhash_value = calculate_xxhash(file_path)
            file_metadata[file_path] = {"timestamp": timestamp, "xxhash": xxhash_value}
    
    return file_metadata, ignored_files, ignored_dirs

def save_metadata(metadata, ignored_files, ignored_dirs, file_path):
    metadata_to_save = {
        "file_metadata": metadata,
        "ignored_files": ignored_files,
        "ignored_directories": ignored_dirs
    }
    with open(file_path, 'w') as f:
        json.dump(metadata_to_save, f, indent=4)

def load_metadata(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return {}

# Step 1: Load previous metadata or create a new baseline
previous_metadata = load_metadata(metadata_file).get("file_metadata", {})
current_metadata, ignored_files, ignored_dirs = get_file_metadata(volume_mount_path)

# Step 2: Check for changes
modified_files = []
for file_path, current_data in current_metadata.items():
    prev_data = previous_metadata.get(file_path)
    if not prev_data:
        # New file
        modified_files.append(file_path)
    elif prev_data["timestamp"] != current_data["timestamp"]:
        # Check xxhash if timestamp differs
        if prev_data["xxhash"] != current_data["xxhash"]:
            modified_files.append(file_path)

# Step 3: Output modified files
if modified_files:
    print("Modified files:", modified_files)
else:
    print("No files modified.")

# Step 4: Update metadata baseline including ignored files and directories
save_metadata(current_metadata, ignored_files, ignored_dirs, metadata_file)
