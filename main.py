import oci, sys
import time
from datetime import datetime
import random, string

# Initialize the default config
config = oci.config.from_file()

# Initialize OCI clients
compute_client = oci.core.ComputeClient(config)
blockstorage_client = oci.core.BlockstorageClient(config)
object_storage_client = oci.object_storage.ObjectStorageClient(config)

# Parameters - replace these with your specific values
current_datetime = datetime.now()
print(f"Starttime is {current_datetime}")
datetime_string = current_datetime.strftime("%Y-%m-%d-%H-%M-%S")
compartment_id = "ocid1.compartment.oc1..aaaaaaaafklcekq7wnwrt4zxeizcrmvhltz6wxaqzwksbhbs73yz6mtpi5za"
os_namespace = 'ociateam'
bucket_name = "cra-backup"
temp_instance_subnet_ocid = "ocid1.subnet.oc1.iad.aaaaaaaavbogtxo5uxelricigx4jm6nw77xaannxi35v3dpmtorlzzlfjvqq"
tag_key = 'CRA-Backup'
tag_value = 'True'

def list_instances_by_tag(compartment_id, tag_key, tag_value):
    instances = compute_client.list_instances(compartment_id).data
    filtered_instances = []
    for instance in instances:
        instance_tags = instance.freeform_tags
        if tag_key in instance_tags and instance_tags[tag_key] == tag_value:
            filtered_instances.append(instance)

    return filtered_instances

instances = list_instances_by_tag(compartment_id, tag_key, tag_value)

for instance in instances:
    print(f"Instance Name: {instance.display_name}, OCID: {instance.id}")
    boot_volume_backup_name = instance.display_name + '_' + datetime_string
    object_name = "exported_image_" + instance.display_name + '_' + datetime_string
    custom_image_name = "custom_image_from_volume_" + instance.display_name + '_' + datetime_string
    restored_volume_name = "restored_volume_" + instance.display_name + '_' + datetime_string
    temporary_instance_name = 'temporary_instance_' + instance.display_name + '_' + datetime_string

    # Step 1: Create Boot Volume and Block Volume Backups
    availability_domain = instance.availability_domain
    boot_volume_info = compute_client.list_boot_volume_attachments(availability_domain, instance.compartment_id, instance_id=instance.id).data
    block_volume_info = compute_client.list_volume_attachments(availability_domain=availability_domain, compartment_id=compartment_id, instance_id=instance.id).data
    boot_volume_id = boot_volume_info[0].boot_volume_id
    attached_volume_ids = [vol_info.volume_id for vol_info in block_volume_info if vol_info.lifecycle_state == 'ATTACHED']

    boot_volume_backup_response = blockstorage_client.create_boot_volume_backup(
        create_boot_volume_backup_details=oci.core.models.CreateBootVolumeBackupDetails(
            boot_volume_id=boot_volume_id,
            display_name=boot_volume_backup_name,
            freeform_tags={'cra_boot_volume_backup': 'True'},
            type="FULL"
        )
    ).data       

    print(f"Creating boot volume backup... Backup OCID: {boot_volume_backup_response.id}")
    attached_vol_backup_ocid = []
    for attached_vol_id in attached_volume_ids:
        volume_backup_name = instance.display_name + '_' + datetime_string + '_' + ''.join(random.choices(string.ascii_letters, k=3))
        Attached_volume_backup_response = blockstorage_client.create_volume_backup(
            create_volume_backup_details=oci.core.models.CreateVolumeBackupDetails(
                volume_id=attached_vol_id,
                display_name=volume_backup_name,
                freeform_tags={'cra_volume_backup': 'True'},
                type="FULL"
            )
        ).data       
        attached_vol_backup_ocid.append(Attached_volume_backup_response.id)
        print(f"Creating volume backup... Backup OCID: {Attached_volume_backup_response.id}")

    # Wait until the boot volume backup and block volume backups are available
    while True:
        backup_status = blockstorage_client.get_boot_volume_backup(boot_volume_backup_response.id).data.lifecycle_state
        block_vol_backup = all(
            blockstorage_client.get_volume_backup(vol_backup_id).data.lifecycle_state == "AVAILABLE"
            for vol_backup_id in attached_vol_backup_ocid
        )
        if backup_status == "AVAILABLE" and block_vol_backup:
            break
        print("Waiting for boot volume and block volume backups to complete...")
        time.sleep(15)

    print("Boot volume and attached volume backups created successfully.")

    # Step 2: Restore Boot Volume and Block Volumes from Backups
    restored_boot_volume = blockstorage_client.create_boot_volume(
        create_boot_volume_details=oci.core.models.CreateBootVolumeDetails(
            compartment_id=compartment_id,
            source_details=oci.core.models.BootVolumeSourceFromBootVolumeReplicaDetails(
                type="bootVolumeBackup",
                id=boot_volume_backup_response.id
            ),
            availability_domain=availability_domain,
            display_name=restored_volume_name
        )
    ).data
    print(f"Restoring boot volume from backup... Volume OCID: {restored_boot_volume.id}")

    restored_block_volumes = []
    for attached_vol_backup_id in attached_vol_backup_ocid:
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
        restored_block_volumes.append(restored_block_volume)
        print(f"Restoring block volume from backup... Volume OCID: {restored_block_volume.id}")

    # Wait until the volumes are available
    while True:
        boot_volume_status = blockstorage_client.get_boot_volume(restored_boot_volume.id).data.lifecycle_state
        block_volume_statuses = [
            blockstorage_client.get_volume(vol.id).data.lifecycle_state
            for vol in restored_block_volumes
        ]
        if boot_volume_status == "AVAILABLE" and all(status == "AVAILABLE" for status in block_volume_statuses):
            break
        print("Waiting for all volumes to become available...")
        time.sleep(10)

    print("Volumes restored successfully.")

    # Step 3: Launch Temporary Instance with Restored Volumes
    instance_details = oci.core.models.LaunchInstanceDetails(
        compartment_id=compartment_id,
        availability_domain=availability_domain,
        display_name=temporary_instance_name,
        shape="VM.Standard.E4.Flex",
        shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
            ocpus=12,
            memory_in_gbs=250
        ),
        create_vnic_details=oci.core.models.CreateVnicDetails(
            assign_public_ip=False,
            subnet_id=temp_instance_subnet_ocid
        ),
        source_details=oci.core.models.InstanceSourceViaBootVolumeDetails(
            boot_volume_id=restored_boot_volume.id
        )
    )
    instance = compute_client.launch_instance(instance_details).data
    print(f"Launching temporary instance... Instance OCID: {instance.id}")

    # Wait until the instance is running
    while True:
        instance_status = compute_client.get_instance(instance.id).data.lifecycle_state
        if instance_status == "RUNNING":
            break
        print("Waiting for instance to become available...")
        time.sleep(15)

    print("Instance is running.")
    # Step 4: Attach Restored Block Volumes to the Temporary Instance
    for restored_block_volume in restored_block_volumes:
        attach_details = oci.core.models.AttachParavirtualizedVolumeDetails(
            instance_id=instance.id,
            volume_id=restored_block_volume.id,
            display_name=f"attached_restored_block_volume_{datetime_string}"
        )
        attach_response = compute_client.attach_volume(attach_details).data
        print(f"Attaching block volume... Volume OCID: {restored_block_volume.id}")

        # Wait for attachment to complete
        while True:
            attachment_status = compute_client.get_volume_attachment(attach_response.id).data.lifecycle_state
            if attachment_status == "ATTACHED":
                break
            print("Waiting for block volume to attach...")
            time.sleep(10)

        print("Block volume attached successfully.")    

    # Create a custom image from the instance
    #this is for testing 
    time.sleep(100)

    image_details = oci.core.models.CreateImageDetails(
        compartment_id=compartment_id,
        instance_id=instance.id,
        display_name=custom_image_name
    )
    custom_image = compute_client.create_image(image_details).data

    print(f"Creating custom image... Image OCID: {custom_image.id}")

    # Wait until the image is available
    while True:
        image_status = compute_client.get_image(custom_image.id).data.lifecycle_state
        if image_status == "AVAILABLE":
            break
        print("Waiting for custom image to become available...")
        time.sleep(20)

    print("Custom image created successfully.")
    time.sleep(60)
    export_details = compute_client.export_image(
        image_id=custom_image.id,
        export_image_details=oci.core.models.ExportImageViaObjectStorageTupleDetails( 
            destination_type="objectStorageTuple",
            namespace_name=os_namespace,
            bucket_name=bucket_name,
            object_name=object_name
            #export_format="VHD"
        )
    )

    print(f"Exporting image to Object Storage... Bucket: {bucket_name}, Object: {object_name}")

    # Wait for the export to complete (this can take some time depending on the image size)
    while True:
        image_export_status = compute_client.get_image(custom_image.id).data.lifecycle_state
        if image_export_status == "AVAILABLE":
            break
        print("Waiting for image export to complete...")
        time.sleep(30)

    print("Image exported to Object Storage successfully.")

    # Cleanup: Terminate the temporary instance and delete the restored volume
    compute_client.terminate_instance(instance.id, preserve_boot_volume=False)
    print(f"Terminating temporary instance... Instance OCID: {instance.id}")
    # Wait for the instance to be terminated
    while True:
        instance = compute_client.get_instance(instance.id).data
        if instance.lifecycle_state == 'TERMINATED':
            print("Instance is terminated.")
            break
        else:
            print(f"Current state: {instance.lifecycle_state}. Waiting for termination...")
            time.sleep(10)  # Wait for 10 seconds before checking again

    blockstorage_client.delete_boot_volume(restored_volume.id)
    print(f"Deleting restored volume... Volume OCID: {restored_volume.id}")

    # Delete the custom image
    compute_client.delete_image(custom_image.id)
    print(f"Deleting custom image... Image OCID: {custom_image.id}")

    # Delete the boot volume backup
    blockstorage_client.delete_boot_volume_backup(boot_volume_backup_response.id)
    print(f"Deleting boot volume backup... Backup OCID: {boot_volume_backup_response.id}")

    # Delete the attached volume backups
    for attached_vol_backup_id in attached_vol_backup_ocid:
        blockstorage_client.delete_volume_backup(attached_vol_backup_id)
        print(f"Deleting volume backup... Backup OCID: {attached_vol_backup_id}")

    print("Process completed successfully.")
    current_datetime = datetime.now()
    print(f"Endtime is {current_datetime}")
