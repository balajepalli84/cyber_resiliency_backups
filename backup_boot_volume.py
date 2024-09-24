import subprocess
import os
import oci

# Function to run shell commands and capture output
def run_command(command):
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    
    if process.returncode != 0:
        print(f"Error running command: {command}")
        print(stderr.decode("utf-8"))
        return None
    return stdout.decode("utf-8").strip()

# Function to get attached block volumes (excluding the root volume)
def get_attached_volumes():
    # Using lsblk to get block devices, excluding root
    command = "lsblk -n -o NAME,TYPE,MOUNTPOINT | grep disk | awk '{print $1}' | grep -v '^├─' | grep -v '^└─'"
    volumes = run_command(command)
    if volumes:
        return volumes.splitlines()
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
def upload_file_to_object_storage(object_storage,namespace, bucket_name, object_name, file_path):
    namespace_name = namespace
    bucket_name = bucket_name
    object_name = object_name
    file_path = file_path
    
    with open(file_path, 'rb') as file:
        object_storage.put_object(namespace_name, bucket_name, object_name, file)

# Main function to discover and mount block volumes, then upload files to OCI Object Storage
def mount_and_upload_volumes():
    # Get list of attached block volumes
    volumes = get_attached_volumes()
    if not volumes:
        print("No block volumes attached.")
        return
    
    print(f"Found volumes: {volumes}")
    signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
    object_storage = oci.object_storage.ObjectStorageClient(config={}, signer=signer)    
    namespace = object_storage.get_namespace().data  # Get the Object Storage namespace
    bucket_name = 'meeting_recording'  # Replace with your bucket name   
    
    for volume in volumes:
        # Skip the root volume
        if volume == "sda":
            continue

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
        print("start here")
        # Loop over each file in the volume
        for root, dirs, files in os.walk(mount_point):
            print(f"Step 2 - {files}")
            print(f"Step 2.1 - {mount_point}")
            for file in files:
                print(f"Step 3.1 - {file}")
                file_path = os.path.join(root, file)
                object_name = os.path.relpath(file_path, mount_point)
                object_name = f"{volume}/{object_name}"
                print(f"Uploading file: {file_path} to {object_name}")
                upload_file_to_object_storage(object_storage,namespace, bucket_name, object_name, file_path)

if __name__ == "__main__":
    mount_and_upload_volumes()