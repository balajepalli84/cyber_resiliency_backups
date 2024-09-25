import oci
import os
import shutil

import subprocess

signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
object_storage_client = oci.object_storage.ObjectStorageClient(config={}, signer=signer)
os_namespace = object_storage_client.get_namespace().data  # Get the Object Storage namespace
bucket_name = 'meeting_recording'  # Replace with your bucket name

def upload_directory_to_object_storage(object_storage_client, directory_path,object_name, bucket_name):
    source_dir = directory_path
    output_zip_file = f'/home/opc/{object_name}'
    shutil.make_archive(output_zip_file, 'zip', source_dir)
    #[things to do] - what will happen when you run out of space
    upload_manager = oci.object_storage.UploadManager(object_storage_client, allow_parallel_uploads=True)
    upload_manager.upload_file(
        namespace_name=os_namespace,
        bucket_name=bucket_name,
        object_name=f'{object_name}.zip',
        file_path=f'{output_zip_file}.zip')


# Create the /mnt_blocks directory if it doesn't exist
create_dir_command = "sudo [ -d /mnt_blocks ] || sudo mkdir /mnt_blocks"
subprocess.run(create_dir_command, shell=True)

# Mount the /dev/sdb1 device to the /mnt_blocks directory
mount_command = "sudo mount /dev/sdb1 /mnt_blocks"
subprocess.run(mount_command, shell=True)

# Define the directory where your block volume is mounted
block_volume_mount_path = '/mnt_blocks'  # Change this to your block volume mount point
object_name='instance4'
# Start uploading all files from the mounted block storage to OCI Object Storage
upload_directory_to_object_storage(object_storage_client, block_volume_mount_path,object_name, bucket_name)
# After the block volume files are uploaded
with open('/home/opc/status_done.txt', 'w') as f:
    f.write('Processing completed successfully.')