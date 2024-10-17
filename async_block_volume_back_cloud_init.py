import oci
import os
import sys
import time
import subprocess
from datetime import datetime

# Capture parameters
block_volume_ocid = 'ocid1.volume.oc1.iad.abuwcljtbc4szrz4tbp6rgznponac5oywvqn5fv2kgolvdpxgydghod4uf5q'
worker_instance_ocid = 'ocid1.instance.oc1.iad.anuwcljtc3adhhqczewcudqk4fflmgjdqmhe7qhxrnfknmosqjc4lrgdvl3q'
compartment_id = 'ocid1.compartment.oc1..aaaaaaaafklcekq7wnwrt4zxeizcrmvhltz6wxaqzwksbhbs73yz6mtpi5za'
namespace = 'ociateam'
bucket_name = 'cra-backup-new'
prefix_name = 'test_12345'

# Initialize the default config and signer
signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()

# Initialize OCI clients
compute_client = oci.core.ComputeClient(config={}, signer=signer)
blockstorage_client = oci.core.BlockstorageClient(config={}, signer=signer)
object_storage_client = oci.object_storage.ObjectStorageClient(config={}, signer=signer)

# Get current date-time string for unique naming
current_datetime = datetime.now()
datetime_string = current_datetime.strftime("%Y-%m-%d-%H-%M-%S")


def run_command(command):
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    return stdout.decode("utf-8").strip()


def get_filesystem(device):
    command = f"blkid {device} -s TYPE -o value"
    fs_type = run_command(command)
    return fs_type if fs_type else None


def mount_volume(device, mount_point, fs_type):
    if not os.path.exists(mount_point):
        os.makedirs(mount_point)
    command = f"mount -t {fs_type} {device} {mount_point}"
    return run_command(command)


def unmount_volume(mount_point):
    command = f"umount {mount_point}"
    return run_command(command)


def detach_volume(attachment_ocid):
    print(f"Detaching volume {attachment_ocid}")
    detach_volume_response = compute_client.detach_volume(volume_attachment_id=attachment_ocid)
    print(f"Detach response: {detach_volume_response}")
    
    # Wait for the volume to detach
    while True:
        attachment_status = compute_client.get_volume_attachment(attachment_ocid).data.lifecycle_state
        if attachment_status == "DETACHED":
            print(f"Volume {attachment_ocid} detached successfully.")
            break
        else:
            print(f"Waiting for volume {attachment_ocid} to detach...")
            time.sleep(10)


def upload_file_to_object_storage(object_storage, namespace, bucket_name, object_name, file_path):
    with open(file_path, 'rb') as file:
        object_storage.put_object(namespace, bucket_name, object_name, file)
    print(f"Uploaded {file_path} to {bucket_name}/{object_name}")


def backup_and_restore_volume(block_volume_ocid, worker_instance_ocid, compartment_id):
    try:
        print(f"Starting backup for block volume: {block_volume_ocid}")
        volume_backup_name = f"backup_{datetime_string}"
        volume_backup_response = blockstorage_client.create_volume_backup(
            create_volume_backup_details=oci.core.models.CreateVolumeBackupDetails(
                volume_id=block_volume_ocid,
                display_name=volume_backup_name,
                type="FULL"
            )
        ).data
        backup_ocid = volume_backup_response.id
        print(f"Backup created with OCID: {backup_ocid}")
        
        while True:
            backup_status = blockstorage_client.get_volume_backup(backup_ocid).data.lifecycle_state
            if backup_status == "AVAILABLE":
                print(f"Backup {backup_ocid} is available.")
                break
            else:
                print(f"Waiting for backup {backup_ocid} to become available...")
                time.sleep(15)

        print(f"Restoring block volume from backup: {backup_ocid}")
        restored_volume_response = blockstorage_client.create_volume(
            create_volume_details=oci.core.models.CreateVolumeDetails(
                compartment_id=compartment_id,
                availability_domain=compute_client.get_instance(worker_instance_ocid).data.availability_domain,
                source_details=oci.core.models.VolumeSourceFromVolumeBackupDetails(
                    id=backup_ocid,
                    type="volumeBackup"
                ),
                display_name=f"restored_volume_{datetime_string}"
            )
        ).data
        restored_volume_ocid = restored_volume_response.id
        print(f"Restored volume OCID: {restored_volume_ocid}")
        
        while True:
            volume_status = blockstorage_client.get_volume(restored_volume_ocid).data.lifecycle_state
            if volume_status == "AVAILABLE":
                print(f"Restored volume {restored_volume_ocid} is available.")
                break
            else:
                print(f"Waiting for restored volume {restored_volume_ocid} to become available...")
                time.sleep(15)

        print(f"Attaching restored volume {restored_volume_ocid} to worker instance {worker_instance_ocid}")
        devices = compute_client.list_instance_devices(instance_id=worker_instance_ocid).data
        first_available_device = next((device.name for device in devices if device.is_available), None)

        attach_response = compute_client.attach_volume(
            oci.core.models.AttachParavirtualizedVolumeDetails(
                instance_id=worker_instance_ocid,
                volume_id=restored_volume_ocid,
                device=first_available_device,
                display_name=f"attached_volume_{datetime_string}"
            )
        ).data
        attachment_ocid = attach_response.id
        print(f"Volume attached to worker instance. Attachment OCID: {attachment_ocid}")
        
        while True:
            attachment_status = compute_client.get_volume_attachment(attachment_ocid).data.lifecycle_state
            if attachment_status == "ATTACHED":
                print(f"Volume {restored_volume_ocid} attached successfully to instance {worker_instance_ocid}.")
                break
            else:
                print(f"Waiting for volume {restored_volume_ocid} to attach...")
                time.sleep(10)
        return first_available_device, restored_volume_ocid, backup_ocid, attachment_ocid
    except oci.exceptions.ServiceError as e:
        print(f"Service error: {e}")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")


def mount_and_upload_volume(device, bucket_name, instance_name):
    fs_type = get_filesystem(device)
    if fs_type is None:
        print(f"Volume {device} is not formatted. Skipping...")
        return
    mount_point = f"/mnt/{device.split('/')[-1]}"
    mount_result = mount_volume(device, mount_point, fs_type)
    print(f"Mounted volume {device} at {mount_point}. Result: {mount_result}")
    
    for root, dirs, files in os.walk(mount_point):
        for file in files:
            file_path = os.path.join(root, file)
            object_name = os.path.relpath(file_path, mount_point)
            object_name = f"{instance_name}/{device.split('/')[-1]}/{object_name}"
            upload_file_to_object_storage(object_storage_client, namespace, bucket_name, object_name, file_path)

    # Unmount the volume after uploading the files
    print(f"Unmounting volume {mount_point}")
    unmount_result = unmount_volume(mount_point)
    print(f"Unmount result: {unmount_result}")


def delete_volume_and_backup(volume_ocid, backup_ocid):
    try:
        print(f"Deleting restored volume {volume_ocid}")
        blockstorage_client.delete_volume(volume_ocid)
        print(f"Restored volume {volume_ocid} deleted.")

        print(f"Deleting backup {backup_ocid}")
        blockstorage_client.delete_volume_backup(backup_ocid)
        print(f"Backup {backup_ocid} deleted.")
    except oci.exceptions.ServiceError as e:
        print(f"Service error: {e}")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")



# Step 1: Backup and restore the volume, and get the attached device path and attachment OCID
device, restored_volume_ocid, backup_ocid, attachment_ocid = backup_and_restore_volume(block_volume_ocid, worker_instance_ocid, compartment_id)

# Step 2: Mount and upload the files from the attached volume to Object Storage
if device:
    mount_and_upload_volume(device, bucket_name, prefix_name)
    # Step 3: Detach the volume from the instance after unmounting
    detach_volume(attachment_ocid)
    # Step 4: Delete the restored volume and backup
    delete_volume_and_backup(restored_volume_ocid, backup_ocid)
else:
    print(f'device {device} not found')
    delete_volume_and_backup(restored_volume_ocid, backup_ocid)
