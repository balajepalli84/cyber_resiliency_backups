import oci,sys
import time
from datetime import datetime
import random, string
import paramiko
# Initialize the default config
config = oci.config.from_file()

# Initialize OCI clients
compute_client = oci.core.ComputeClient(config)
blockstorage_client = oci.core.BlockstorageClient(config)
object_storage_client = oci.object_storage.ObjectStorageClient(config)
network_client = oci.core.VirtualNetworkClient(config)

current_datetime = datetime.now()
print(f"Starttime is {current_datetime}")
datetime_string = current_datetime.strftime("%Y-%m-%d-%H-%M-%S")
compartment_id = "ocid1.compartment.oc1..aaaaaaaafklcekq7wnwrt4zxeizcrmvhltz6wxaqzwksbhbs73yz6mtpi5za"
os_namespace = 'ociateam'
bucket_name = "cra-backup"
temp_instance_subnet_ocid = "ocid1.subnet.oc1.iad.aaaaaaaavbogtxo5uxelricigx4jm6nw77xaannxi35v3dpmtorlzzlfjvqq"
tag_key = 'CRA-Backup'
tag_value = 'True'
private_key_path=r'C:\Security\CRA\mycode\creds\reuse_private.key'
public_key = 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDlJruyiWi7+sDGmKvYR0i1Oj9Eean6F5ypQ6JIChYodTrQoOZ7f5fNZT2KIBikGBaL8H6IH5UFtsi6tfEfGDgXfsqO1ArSdND0TdRQnamCGROslzSiD7dKYXPUwG4a9Y3mhVcHpIJdG0ejQZbmlKtipNd0D3DS4nTFGOZsI0P2w1EUy5PKqzc//eNUGwJGFBKioDTt5d7PBDWMqOUeON6g7DsXvlhrqj8LfdL+C4EpN1A22qmaA2dLJdOTAwv5M0itQYk5PUZq+tIKCCMOv5R7E8SLQ3PUPqE1KED+pywchfSC28r+xxiQqFseQUfexK+e5wQaJOx7tTdFkPmFcTJj ssh-key-2024-09-19'  
oci_objectstorage_preauthrequest="https://ociateam.objectstorage.us-ashburn-1.oci.customer-oci.com/p/dZrKbjAkZcsoDo7SeqLpDvEnREhAku63VJTJla0B-IZZp55w000TcEIFb3glrZjQ/n/ociateam/b/bakcup-vault-secrets/o/backup_boot_volume.py"

# Function to list instances by tag
def list_instances_by_tag(compartment_id, tag_key, tag_value):
    instances = compute_client.list_instances(compartment_id).data
    filtered_instances = []
    for instance in instances:
        instance_tags = instance.freeform_tags
        if tag_key in instance_tags and instance_tags[tag_key] == tag_value and instance.lifecycle_state != 'TERMINATED':
            filtered_instances.append(instance)
    return filtered_instances

instances = list_instances_by_tag(compartment_id, tag_key, tag_value)

for instance in instances:
    print(f"Processing Instance Name: {instance.display_name}, OCID: {instance.id}")
    availability_domain = instance.availability_domain
    block_volume_info = compute_client.list_volume_attachments(
        availability_domain=availability_domain, 
        compartment_id=compartment_id, 
        instance_id=instance.id
    ).data
    
    attached_volume_ids = [vol_info.volume_id for vol_info in block_volume_info if vol_info.lifecycle_state == 'ATTACHED']

    # Step 1: Create Block Volume Backups
    attached_vol_backup_ocids = []
    for attached_vol_id in attached_volume_ids:
        volume_backup_name = f"{instance.display_name}_{datetime_string}_{''.join(random.choices(string.ascii_letters, k=3))}"
        volume_backup_response = blockstorage_client.create_volume_backup(
            create_volume_backup_details=oci.core.models.CreateVolumeBackupDetails(
                volume_id=attached_vol_id,
                display_name=volume_backup_name,
                freeform_tags={'cra_volume_backup': 'True'},
                type="FULL"
            )
        ).data
        attached_vol_backup_ocids.append(volume_backup_response.id)
        print(f"Creating volume backup... Backup OCID: {volume_backup_response.id}")

    # Wait for backups to complete
    while True:
        block_vol_backup = all(
            blockstorage_client.get_volume_backup(vol_backup_id).data.lifecycle_state == "AVAILABLE"
            for vol_backup_id in attached_vol_backup_ocids
        )
        if block_vol_backup:
            break
        print("Waiting for block volume backups to complete...")
        time.sleep(15)

    print("Attached volume backups created successfully.")

    # Step 2: Restore Block Volumes from Backups
    restored_volumes = []
    for attached_vol_backup_id in attached_vol_backup_ocids:
        restored_block_volume = blockstorage_client.create_volume(
            create_volume_details=oci.core.models.CreateVolumeDetails(
                compartment_id=compartment_id,
                source_details=oci.core.models.VolumeSourceFromVolumeBackupDetails(
                    type="volumeBackup",
                    id=attached_vol_backup_id
                ),
                availability_domain=availability_domain,
                display_name=f"restored_block_volume_{datetime_string}"
            )
        ).data
        restored_volumes.append({
            'volume_id': restored_block_volume.id,
            'instance_name': instance.display_name,
            'instance_ocid': instance.id,
            'availability_domain': availability_domain
        })
        print(f"Restoring block volume from backup... Volume OCID: {restored_block_volume.id}")

    # Wait until the volumes are available
    while True:
        block_volume_statuses = [
            blockstorage_client.get_volume(vol['volume_id']).data.lifecycle_state
            for vol in restored_volumes
        ]
        if all(status == "AVAILABLE" for status in block_volume_statuses):
            break
        print("Waiting for restored block volumes to become available...")
        time.sleep(10)

    print("Volumes restored successfully.")

    temporary_instance_name = f'temporary_instance_{instance.display_name}_{datetime_string}'

    instance_details = oci.core.models.LaunchInstanceDetails(
        compartment_id=compartment_id,
        availability_domain=availability_domain,
        display_name=temporary_instance_name,
        shape="VM.Standard.E4.Flex",
        shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
            ocpus=2,
            memory_in_gbs=10
        ),
        create_vnic_details=oci.core.models.CreateVnicDetails(
            assign_public_ip=True,
            subnet_id=temp_instance_subnet_ocid
        ),
        source_details=oci.core.models.InstanceSourceViaImageDetails(
            image_id='ocid1.image.oc1.iad.aaaaaaaa32s2htizwbsi5q2tnbrzii5n67tqmki7en7hkrvxzfww556qggxq'
        ),
        metadata={
            "ssh_authorized_keys": public_key
        }
    )

    # Launch the instance
    new_instance = compute_client.launch_instance(instance_details).data

    print(f"Launching new instance... Instance OCID: {new_instance.id}")


    # Wait until the instance is running
    while True:
        instance_status = compute_client.get_instance(new_instance.id).data.lifecycle_state
        if instance_status == "RUNNING":
            break
        print("Waiting for instance to become available...")
        time.sleep(15)

    print("New instance is running.")

    # Step 4: Attach all restored block volumes to the new instance
    for volume_data in restored_volumes:
        attach_details = oci.core.models.AttachParavirtualizedVolumeDetails(
            instance_id=new_instance.id,
            volume_id=volume_data['volume_id'],
            display_name=f"{volume_data['instance_name']}_attached_volume_{datetime_string}"
        )
        attach_response = compute_client.attach_volume(attach_details).data
        print(f"Attaching volume {volume_data['volume_id']} from instance {volume_data['instance_name']} to new instance {new_instance.display_name}")

        # Wait for attachment to complete
        while True:
            attachment_status = compute_client.get_volume_attachment(attach_response.id).data.lifecycle_state
            if attachment_status == "ATTACHED":
                break
            print(f"Waiting for volume {volume_data['volume_id']} to attach...")
            time.sleep(10)

        print(f"Volume {volume_data['volume_id']} attached successfully.")

    print("All volumes attached to the new instance.")

    list_vnic_attachments_response = compute_client.list_vnic_attachments(
        compartment_id=compartment_id,
        instance_id=new_instance.id).data
    response_get_vnic = network_client.get_vnic(list_vnic_attachments_response[0].vnic_id).data
    instance_status = compute_client.get_instance(new_instance.id).data.lifecycle_state
    time.sleep(30)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    private_key = paramiko.RSAKey.from_private_key_file(private_key_path)
    ssh.connect(response_get_vnic.public_ip, username='opc', pkey=private_key)

    stdin, stdout1, stderr1 = ssh.exec_command(f"sudo curl '{oci_objectstorage_preauthrequest}' > /home/opc/backup_script.py")
    output1 = stdout1.read().decode()
    error1 = stderr1.read().decode()
    print("Command 1 Output:")
    print(output1)
    if error1:
        print("Command 1 Error:")
        print(error1)

    # Command 2: Run script
    stdin, stdout2, stderr2 = ssh.exec_command(f"sudo python /home/opc/backup_script.py {bucket_name} {instance.display_name}_{datetime_string}")
    output2 = stdout2.read().decode()
    error2 = stderr2.read().decode()
    print("Command 2 Output:")
    print(output2)
    if error2:
        print("Command 2 Error:")
        print(error2)

    ssh.close()
    # Cleanup: Terminate the temporary instance and delete the restored volume
    compute_client.terminate_instance(new_instance.id, preserve_boot_volume=False)
    print(f"Terminating temporary instance... Instance OCID: {new_instance.id}")
    while True:
        instance = compute_client.get_instance(new_instance.id).data
        if instance.lifecycle_state == 'TERMINATED':
            print("Instance is terminated.")
            break
        else:
            print(f"Current state: {instance.lifecycle_state}. Waiting for termination...")
            time.sleep(10)  # Wait for 10 seconds before checking again
    # Delete the attached volume backups
    for volume_data in restored_volumes:
        blockstorage_client.delete_volume(volume_data['volume_id'])
    print("Restored volumes are terminated.")
    for vol_backup_id in attached_vol_backup_ocids:
        blockstorage_client.delete_volume_backup(vol_backup_id)
    print("Volume backups are terminated.")
print("Process completed successfully.")
current_datetime = datetime.now()