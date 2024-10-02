import subprocess
import os
import oci
import sys

# Function to run shell commands and capture output
def run_command(command):
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    
    if process.returncode != 0:
        print(f"Error running command: {command}")
        print(stderr.decode("utf-8"))
        return None
    return stdout.decode("utf-8").strip()

# Function to get detailed information about a block device
def get_volume_info(device):
    command = f"lsblk /dev/{device} -o NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE -n"
    return run_command(command)

# Function to get the root volume
def get_root_volume():
    command = "lsblk -n -o NAME,MOUNTPOINT | grep ' /$' | awk '{print $1}'"
    root_volume = run_command(command)
    if root_volume:
        return root_volume.strip()
    return None

# Function to get attached block volumes (excluding the root volume)
def get_attached_volumes(root_volume):
    command = "lsblk -n -o NAME,TYPE | grep disk | awk '{print $1}'"
    volumes = run_command(command)
    if volumes:
        return [volume for volume in volumes.splitlines() if volume != root_volume]
    return []

# Function to get filesystem type of a device
def get_filesystem(device):
    command = f"blkid /dev/{device} -s TYPE -o value"
    fs_type = run_command(command)
    return fs_type if fs_type else None  # return None if blkid fails

# Function to mount block volume
def mount_volume(device, mount_point, fs_type):
    if not os.path.exists(mount_point):
        os.makedirs(mount_point)
        print(f"Created mount point: {mount_point}")
    command = f"mount -t {fs_type} /dev/{device} {mount_point}"
    result = run_command(command)
    if result is None:
        print(f"Failed to mount /dev/{device} to {mount_point}")
    else:
        print(f"Mounted /dev/{device} to {mount_point}")

# Function to upload file to OCI Object Storage
def upload_file_to_object_storage(object_storage, namespace, bucket_name, object_name, file_path):
    with open(file_path, 'rb') as file:
        object_storage.put_object(namespace, bucket_name, object_name, file)

# Main function to discover and mount block volumes, then upload files to OCI Object Storage
def mount_and_upload_volumes(bucket_name, instance_name):
    # Get the root volume
    root_volume = get_root_volume()
    if not root_volume:
        print("Error: Unable to determine root volume.")
        return
    
    # Print root volume info
    root_info = get_volume_info(root_volume)
    print(f"Root Volume Information:\n{root_info}")
    
    # Get list of attached block volumes excluding the root volume
    volumes = get_attached_volumes(root_volume)
    if not volumes:
        print("No block volumes attached.")
        return
    
    # Print other volumes' information
    print("\nOther Attached Volumes Information:")
    for volume in volumes:
        volume_info = get_volume_info(volume)
        print(volume_info)
    
    signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
    object_storage = oci.object_storage.ObjectStorageClient(config={}, signer=signer)    
    namespace = object_storage.get_namespace().data  # Get the Object Storage namespace
    
    for volume in volumes:
        # Get the filesystem type
        fs_type = get_filesystem(volume)
        
        # Skip unformatted volumes
        if fs_type is None:
            print(f"Skipping unformatted volume: {volume}")
            continue
        
        # Define the mount point as /mnt/<volume_name>
        mount_point = f"/mnt/{volume}"
        
        # Mount the volume
        mount_volume(volume, mount_point, fs_type)
        
        # Loop over each file in the volume
        for root, dirs, files in os.walk(mount_point):
            for file in files:
                file_path = os.path.join(root, file)
                object_name = os.path.relpath(file_path, mount_point)
                object_name = f"{instance_name}/{volume}/{object_name}"
                print(f"Uploading file: {file_path} to {object_name}")
                upload_file_to_object_storage(object_storage, namespace, bucket_name, object_name, file_path)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python script.py <bucket_name> <instance_name>")
        sys.exit(1)

    bucket_name = sys.argv[1]
    instance_name = sys.argv[2]
    mount_and_upload_volumes(bucket_name, instance_name)
