import oci
import time

# Initialize the default config
config = oci.config.from_file()

# Initialize OCI clients
compute_client = oci.core.ComputeClient(config)
object_storage_client = oci.object_storage.ObjectStorageClient(config)

# Parameters - replace these with your specific values
compartment_id = "ocid1.compartment.oc1..aaaaaaaafklcekq7wnwrt4zxeizcrmvhltz6wxaqzwksbhbs73yz6mtpi5za"
availability_domain = "uFjs:US-ASHBURN-AD-1"
bucket_name = "cra-backup"
namespace_name = "ociateam"
object_name = "exported_image_cra-test-1_2024-09-24-22-29-46"
display_name = "Imported Custom Image"
instance_display_name = "restored_instance"
subnet_id = "ocid1.subnet.oc1.iad.aaaaaaaavbogtxo5uxelricigx4jm6nw77xaannxi35v3dpmtorlzzlfjvqq"

# Step 1: Import the Image from Object Storage
import_image_details = oci.core.models.CreateImageDetails(
    compartment_id=compartment_id,
    display_name=display_name,
    image_source_details=oci.core.models.ImageSourceViaObjectStorageTupleDetails(
        source_type="objectStorageTuple",
        bucket_name=bucket_name,
        namespace_name=namespace_name,
        object_name=object_name
    )
)

imported_image = compute_client.create_image(import_image_details).data

print(f"Importing image from Object Storage... Image OCID: {imported_image.id}")

# Wait until the image is available
while True:
    image_status = compute_client.get_image(imported_image.id).data.lifecycle_state
    if image_status == "AVAILABLE":
        break
    print("Waiting for image to become available...")
    time.sleep(20)

print("Image imported successfully.")

# Step 2: Launch a New Instance using the Imported Image

launch_instance_details=oci.core.models.LaunchInstanceDetails(
    availability_domain=availability_domain,
    compartment_id=compartment_id,
    create_vnic_details=oci.core.models.CreateVnicDetails(
        assign_public_ip=False,
        subnet_id=subnet_id),
    display_name=instance_display_name,
    shape="VM.Standard.E4.Flex",
    shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
        ocpus=12,
        memory_in_gbs=250),
    source_details=oci.core.models.InstanceSourceViaImageDetails(
        image_id=imported_image.id
    ))

new_instance = compute_client.launch_instance(launch_instance_details).data

print(f"Launching new instance... Instance OCID: {new_instance.id}")

# Wait until the instance is running
while True:
    instance_status = compute_client.get_instance(new_instance.id).data.lifecycle_state
    if instance_status == "RUNNING":
        break
    print("Waiting for instance to become available...")
    time.sleep(20)

print("Instance launched successfully.")
