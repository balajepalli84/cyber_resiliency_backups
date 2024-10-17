import oci
import time
from datetime import datetime

# Configuration and parameters
# Capture parameters

compartment_id = 'ocid1.compartment.oc1..aaaaaaaafklcekq7wnwrt4zxeizcrmvhltz6wxaqzwksbhbs73yz6mtpi5za'
worker_instance_ocid = 'ocid1.instance.oc1.iad.anuwcljtc3adhhqczewcudqk4fflmgjdqmhe7qhxrnfknmosqjc4lrgdvl3q'
subnet_ocid = "ocid1.subnet.oc1.iad.aaaaaaaahdaj6y4pqxnoxr2gj3ilyanvmsqrnat6klveylf5xfcdr5bdsqlq"
boot_volume_ocid = "ocid1.bootvolume.oc1.iad.abuwcljtyju5u7k7n5yltdjgw5j3ykajsehwhoozsajwxvdjcgi3yecnsoaq"
namespace = 'ociateam'
bucket_name = 'cra-backup-new'
datetime_string = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
image_name = f"custom_image_{datetime_string}"
object_name = f"exported_image_{datetime_string}.qcow2"

# Initialize the default config and signer
signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()

# Initialize OCI clients
compute_client = oci.core.ComputeClient(config={}, signer=signer)
blockstorage_client = oci.core.BlockstorageClient(config={}, signer=signer)
object_storage_client = oci.object_storage.ObjectStorageClient(config={}, signer=signer)

# Step 1: Backup the boot volume
print("Creating boot volume backup...")
boot_backup = blockstorage_client.create_boot_volume_backup(
    oci.core.models.CreateBootVolumeBackupDetails(
        boot_volume_id=boot_volume_ocid,
        display_name=f"boot_backup_{datetime_string}",
        type="FULL"
    )
).data
print(f"Boot volume backup created: {boot_backup.id}")

# Wait for backup to complete
while True:
    backup_status = blockstorage_client.get_boot_volume_backup(boot_backup.id).data.lifecycle_state
    if backup_status == "AVAILABLE":
        print("Boot volume backup is available.")
        break
    time.sleep(15)

# Step 2: Restore the boot volume
print("Restoring boot volume from backup...")
restored_boot_volume = blockstorage_client.create_boot_volume(
    oci.core.models.CreateBootVolumeDetails(
        compartment_id=compartment_id,
        source_details=oci.core.models.BootVolumeSourceFromBootVolumeBackupDetails(
            id=boot_backup.id
        ),
        availability_domain=compute_client.get_instance(worker_instance_ocid).data.availability_domain,
        display_name=f"restored_boot_{datetime_string}"
    )
).data

print(f"Restored boot volume: {restored_boot_volume.id}")

# Wait for the restored boot volume to become available
while True:
    volume_status = blockstorage_client.get_boot_volume(restored_boot_volume.id).data.lifecycle_state
    if volume_status == "AVAILABLE":
        print("Restored boot volume is available.")
        break
    time.sleep(15)

# Step 3: Launch a temporary instance with the restored boot volume
print("Launching temporary instance...")
instance_details = oci.core.models.LaunchInstanceDetails(
    compartment_id=compartment_id,
    availability_domain=compute_client.get_instance(worker_instance_ocid).data.availability_domain,
    display_name=f"temp_instance_{datetime_string}",
    shape="VM.Standard.E4.Flex",
    shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(ocpus=2, memory_in_gbs=10),
    source_details=oci.core.models.InstanceSourceViaBootVolumeDetails(boot_volume_id=restored_boot_volume.id),
    create_vnic_details=oci.core.models.CreateVnicDetails(subnet_id=subnet_ocid)
)
instance = compute_client.launch_instance(instance_details).data
print(f"Temporary instance created: {instance.id}")

# Wait for the instance to start
while True:
    instance_status = compute_client.get_instance(instance.id).data.lifecycle_state
    if instance_status == "RUNNING":
        print("Temporary instance is running.")
        break
    time.sleep(15)

# Step 4: Create an image from the instance
print("Creating custom image...")
custom_image = compute_client.create_image(
    oci.core.models.CreateImageDetails(
        compartment_id=compartment_id,
        instance_id=instance.id,
        display_name=image_name
    )
).data
print(f"Custom image created: {custom_image.id}")

# Wait for the image to be available
while True:
    image_status = compute_client.get_image(custom_image.id).data.lifecycle_state
    if image_status == "AVAILABLE":
        print("Custom image is available.")
        break
    time.sleep(15)

# Step 5: Export the image to Object Storage
print("Exporting image to Object Storage...")
compute_client.export_image(
    image_id=custom_image.id,
    export_image_details=oci.core.models.ExportImageViaObjectStorageTupleDetails(
        destination_type="objectStorageTuple",
        namespace_name=namespace,
        bucket_name=bucket_name,
        object_name=object_name
    )
)

# Wait for the export to complete
while True:
    export_status = compute_client.get_image(custom_image.id).data.lifecycle_state
    if export_status == "AVAILABLE":
        print("Image export completed.")
        break
    time.sleep(30)

# Step 6: Cleanup - Terminate the instance and delete volumes and backups
print("Terminating temporary instance...")
compute_client.terminate_instance(instance.id)
while True:
    instance_status = compute_client.get_instance(instance.id).data.lifecycle_state
    if instance_status == "TERMINATED":
        print("Temporary instance terminated.")
        break
    time.sleep(15)

print("Deleting restored boot volume...")
blockstorage_client.delete_boot_volume(restored_boot_volume.id)
print("Deleting boot volume backup...")
blockstorage_client.delete_boot_volume_backup(boot_backup.id)

print("Process completed successfully.")
