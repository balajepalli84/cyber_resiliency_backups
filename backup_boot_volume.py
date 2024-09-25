import oci, sys
import time
from datetime import datetime
import random, string
import concurrent.futures

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
instance_id = "ocid1.instance.oc1.iad.anuwcljtc3adhhqcz5dtjvpyfc7fzu34wvoebq56qsnimvfk5hg5z3di473a"
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
        if tag_key in instance_tags and instance_tags[tag_key] == tag_value and instance.lifecycle_state != 'TERMINATED':
            filtered_instances.append(instance)

    return filtered_instances

def process_instance(instance):
    print(f"Instance Name: {instance.display_name}, OCID: {instance.id}")
    boot_volume_backup_name = instance.display_name + '_' + datetime_string
    object_name = "exported_image_" + instance.display_name + '_' + datetime_string
    custom_image_name = "custom_image_from_volume_" + instance.display_name + '_' + datetime_string
    restored_volume_name = "restored_volume_" + instance.display_name + '_' + datetime_string
    temporary_instance_name = 'temporary_instance_' + instance.display_name + '_' + datetime_string

    # Step 1: Create a Boot Volume Backup
    availability_domain = instance.availability_domain
    boot_volume_info = compute_client.list_boot_volume_attachments(availability_domain, instance.compartment_id,
                                                                   instance_id=instance.id).data
    boot_volume_id = boot_volume_info[0].boot_volume_id

    boot_volume_backup_response = blockstorage_client.create_boot_volume_backup(
        create_boot_volume_backup_details=oci.core.models.CreateBootVolumeBackupDetails(
            boot_volume_id=boot_volume_id,
            display_name=boot_volume_backup_name,
            freeform_tags={
                'cra_boot_volume_backup': 'True'},
            type="FULL")).data

    print(f"Creating boot volume backup... Backup OCID: {boot_volume_backup_response.id}")
    # Wait until the boot volume backup is available
    while True:
        backup_status = blockstorage_client.get_boot_volume_backup(boot_volume_backup_response.id).data.lifecycle_state
        if backup_status == "AVAILABLE":
            break
        print("Waiting for boot volume backup to complete...")
        time.sleep(15)

    print("Boot volume and Attached Volume backup created successfully.")

    # Step 2: Restore the Boot Volume Backup
    restored_volume = blockstorage_client.create_boot_volume(
        create_boot_volume_details=oci.core.models.CreateBootVolumeDetails(
            compartment_id=compartment_id,
            source_details=oci.core.models.BootVolumeSourceFromBootVolumeReplicaDetails(
                type="bootVolumeBackup",
                id=boot_volume_backup_response.id),
            availability_domain=availability_domain,
            display_name=restored_volume_name)).data
    print(f"Restoring volume from backup... Volume OCID: {restored_volume.id}")

    # Wait until the volume is available
    while True:
        volume_status = blockstorage_client.get_boot_volume(restored_volume.id).data.lifecycle_state
        if volume_status == "AVAILABLE":
            break
        print("Waiting for volume to become available...")
        time.sleep(10)

    print("Volume restored successfully.")

    # Step 3: Create a Custom Image from the Restored Volume
    instance_details = oci.core.models.LaunchInstanceDetails(
        compartment_id=compartment_id,
        availability_domain=availability_domain,
        display_name=temporary_instance_name,
        shape="VM.Standard.E4.Flex",
        shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
            ocpus=2,
            memory_in_gbs=10),
        create_vnic_details=oci.core.models.CreateVnicDetails(
            assign_public_ip=False,
            subnet_id=temp_instance_subnet_ocid
        ),
        source_details=oci.core.models.InstanceSourceViaBootVolumeDetails(
            boot_volume_id=restored_volume.id
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

instances = list_instances_by_tag(compartment_id, tag_key, tag_value)

with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    futures = []
    for instance in instances:
        futures.append(executor.submit(process_instance, instance))
    for future in concurrent.futures.as_completed(futures):
        future.result()

print("Process completed successfully.")
current_datetime = datetime.now()
print(f"Endtime is {current_datetime}")