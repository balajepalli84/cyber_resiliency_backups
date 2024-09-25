import oci
import os
import time
import logging
from datetime import datetime
import concurrent.futures

current_datetime = datetime.now()
datetime_string = current_datetime.strftime("%Y-%m-%d-%H-%M-%S")
# Set up logging
log_dir = r'C:\Security\CRA\mycode\logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)  
log_file = os.path.join(log_dir, f'boot_vol_backup_log_file_{datetime_string}.log')
logger = logging.getLogger()  
logger.setLevel(logging.DEBUG)  
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)  

# Create console handler for printing logs to the console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)  
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

config = oci.config.from_file()

# Initialize OCI clients
try:
    compute_client = oci.core.ComputeClient(config)
    blockstorage_client = oci.core.BlockstorageClient(config)
    object_storage_client = oci.object_storage.ObjectStorageClient(config)
    logger.info("OCI clients initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize OCI clients: {str(e)}")
    raise

# Parameters

compartment_id = "ocid1.compartment.oc1..aaaaaaaafklcekq7wnwrt4zxeizcrmvhltz6wxaqzwksbhbs73yz6mtpi5za"
instance_id = "ocid1.instance.oc1.iad.anuwcljtc3adhhqcz5dtjvpyfc7fzu34wvoebq56qsnimvfk5hg5z3di473a"
os_namespace = 'ociateam'
bucket_name = "cra-backup"
temp_instance_subnet_ocid = "ocid1.subnet.oc1.iad.aaaaaaaavbogtxo5uxelricigx4jm6nw77xaannxi35v3dpmtorlzzlfjvqq"
tag_key = 'CRA-Backup'
tag_value = 'True'

def list_instances_by_tag(compartment_id, tag_key, tag_value):
    try:
        instances = compute_client.list_instances(compartment_id).data
        filtered_instances = [instance for instance in instances 
                              if tag_key in instance.freeform_tags and 
                              instance.freeform_tags[tag_key] == tag_value and 
                              instance.lifecycle_state != 'TERMINATED']
        logger.info(f"Found {len(filtered_instances)} instances with tag {tag_key}: {tag_value}")
        return filtered_instances
    except Exception as e:
        logger.error(f"Error listing instances by tag: {str(e)}")
        raise

def process_instance(instance):
    try:
        logger.info(f"Processing instance {instance.display_name} (OCID: {instance.id})")        
        boot_volume_backup_name = instance.display_name + '_' + datetime_string
        object_name = "exported_image_" + instance.display_name + '_' + datetime_string
        custom_image_name = "custom_image_from_volume_" + instance.display_name + '_' + datetime_string
        restored_volume_name = "restored_volume_" + instance.display_name + '_' + datetime_string
        temporary_instance_name = 'temporary_instance_' + instance.display_name + '_' + datetime_string

        # Step 1: Create a Boot Volume Backup
        availability_domain = instance.availability_domain
        boot_volume_info = compute_client.list_boot_volume_attachments(
            availability_domain, instance.compartment_id, instance_id=instance.id).data
        boot_volume_id = boot_volume_info[0].boot_volume_id

        boot_volume_backup_response = blockstorage_client.create_boot_volume_backup(
            create_boot_volume_backup_details=oci.core.models.CreateBootVolumeBackupDetails(
                boot_volume_id=boot_volume_id,
                display_name=boot_volume_backup_name,
                freeform_tags={'cra_boot_volume_backup': 'True'},
                type="FULL")).data

        logger.info(f"Boot volume backup created. Backup OCID: {boot_volume_backup_response.id}")

        # Wait for backup to complete
        while True:
            backup_status = blockstorage_client.get_boot_volume_backup(boot_volume_backup_response.id).data.lifecycle_state
            logger.info(f"Waiting for Boot volume backup to become available...{boot_volume_backup_name}")
            if backup_status == "AVAILABLE":
                break
            time.sleep(15)

        logger.info(f"Boot volume backup completed successfully.{boot_volume_backup_name},{boot_volume_backup_response.id}")

        # Step 2: Restore the Boot Volume Backup
        restored_volume = blockstorage_client.create_boot_volume(
            create_boot_volume_details=oci.core.models.CreateBootVolumeDetails(
                compartment_id=compartment_id,
                source_details=oci.core.models.BootVolumeSourceFromBootVolumeReplicaDetails(
                    type="bootVolumeBackup",
                    id=boot_volume_backup_response.id),
                availability_domain=availability_domain,
                display_name=restored_volume_name)).data

        logger.info(f"Restored volume from backup. Volume OCID: {restored_volume_name},{restored_volume.id}")

        while True:
            volume_status = blockstorage_client.get_boot_volume(restored_volume.id).data.lifecycle_state
            if volume_status == "AVAILABLE":
                break
            logger.info(f"Waiting for volume to become available...{restored_volume_name}")
            time.sleep(10)

        logger.info(f"Volume restored successfully.{restored_volume_name}")

        # Step 3: Launch temporary instance and create custom image
        instance_details = oci.core.models.LaunchInstanceDetails(
            compartment_id=compartment_id,
            availability_domain=availability_domain,
            display_name=temporary_instance_name,
            shape="VM.Standard.E4.Flex",
            shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
                ocpus=2, memory_in_gbs=10),
            create_vnic_details=oci.core.models.CreateVnicDetails(
                assign_public_ip=False,
                subnet_id=temp_instance_subnet_ocid),
            source_details=oci.core.models.InstanceSourceViaBootVolumeDetails(
                boot_volume_id=restored_volume.id)
        )
        temp_instance = compute_client.launch_instance(instance_details).data

        logger.info(f"Temporary instance launched. Instance OCID: {temporary_instance_name},{temp_instance.id}")

        while True:
            instance_status = compute_client.get_instance(temp_instance.id).data.lifecycle_state
            if instance_status == "RUNNING":
                break
            logger.info(f"Waiting for instance to become available...{temporary_instance_name}")
            time.sleep(15)

        logger.info(f"Temporary instance {temporary_instance_name} is running.")

        # Step 4: Create a custom image from the instance
        image_details = oci.core.models.CreateImageDetails(
            compartment_id=compartment_id,
            instance_id=temp_instance.id,
            display_name=custom_image_name
        )
        custom_image = compute_client.create_image(image_details).data

        logger.info(f"Custom image - {custom_image_name} created. Image OCID: {custom_image.id}")

        while True:
            image_status = compute_client.get_image(custom_image.id).data.lifecycle_state
            if image_status == "AVAILABLE":
                break
            logger.info(f"Waiting for custom image - {custom_image_name} to become available...")
            time.sleep(20)

        logger.info(f"Custom image - {custom_image_name} created successfully.")

        # Step 5: Export the custom image to Object Storage
        export_details = compute_client.export_image(
            image_id=custom_image.id,
            export_image_details=oci.core.models.ExportImageViaObjectStorageTupleDetails(
                destination_type="objectStorageTuple",
                namespace_name=os_namespace,
                bucket_name=bucket_name,
                object_name=object_name
            )
        )
        logger.info(f"Exporting image to Object Storage... Bucket: {bucket_name}, Object: {object_name}")

        while True:
            image_export_status = compute_client.get_image(custom_image.id).data.lifecycle_state
            if image_export_status == "AVAILABLE":
                break
            logger.info(f"Waiting for image - {object_name} export to complete...")
            time.sleep(30)

        logger.info("Image - {object_name} exported to Object Storage successfully.")

        # Cleanup: Terminate the temporary instance and delete the restored volume
        compute_client.terminate_instance(temp_instance.id, preserve_boot_volume=False)
        logger.info(f"Terminating temporary instance... Instance OCID: {temp_instance.id}")

        while True:
            instance = compute_client.get_instance(temp_instance.id).data
            if instance.lifecycle_state == 'TERMINATED':
                logger.info(f"Temporary instance {temporary_instance_name} terminated.")
                break
            logger.info(f"Current state: {instance.lifecycle_state}. Waiting for termination...")
            time.sleep(10)

        blockstorage_client.delete_boot_volume(restored_volume.id)
        logger.info(f"Deleted restored volume. Volume OCID: {restored_volume.id}")

    except Exception as e:
        logger.error(f"Error processing instance {instance.display_name}: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        instances = list_instances_by_tag(compartment_id, tag_key, tag_value)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(process_instance, instance) for instance in instances]
            for future in concurrent.futures.as_completed(futures):
                future.result()

        logger.info("Process completed successfully.")
    except Exception as e:
        logger.error(f"Error in main processing: {str(e)}")
        raise
