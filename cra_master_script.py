import oci
import sys
import subprocess

# Define constants
constants = [
    ("os_namespace", 'ociateam'),
    ("bucket_name", "cra-backup"),
    ("temp_instance_subnet_ocid", "ocid1.subnet.oc1.iad.aaaaaaaavbogtxo5uxelricigx4jm6nw77xaannxi35v3dpmtorlzzlfjvqq"),
    ("tag_key", 'CRA-Backup'),
    ("tag_value", 'True'),
    ("private_key_path", r'C:\Security\CRA\mycode\creds\reuse_private.key'),
    ("public_key", 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDlJruyiWi7+sDGmKvYR0i1Oj9Eean6F5ypQ6JIChYodTrQoOZ7f5fNZT2KIBikGBaL8H6IH5UFtsi6tfEfGDgXfsqO1ArSdND0TdRQnamCGROslzSiD7dKYXPUwG4a9Y3mhVcHpIJdG0ejQZbmlKtipNd0D3DS4nTFGOZsI0P2w1EUy5PKqzc//eNUGwJGFBKioDTt5d7PBDWMqOUeON6g7DsXvlhrqj8LfdL+C4EpN1A22qmaA2dLJdOTAwv5M0itQYk5PUZq+tIKCCMOv5R7E8SLQ3PUPqE1KED+pywchfSC28r+xxiQqFseQUfexK+e5wQaJOx7tTdFkPmFcTJj ssh-key-2024-09-19'),
    ("oci_objectstorage_preauthrequest", "https://ociateam.objectstorage.us-ashburn-1.oci.customer-oci.com/p/dZrKbjAkZcsoDo7SeqLpDvEnREhAku63VJTJla0B-IZZp55w000TcEIFb3glrZjQ/n/ociateam/b/bakcup-vault-secrets/o/backup_boot_volume.py")
]
compartment_id = "ocid1.compartment.oc1..aaaaaaaafklcekq7wnwrt4zxeizcrmvhltz6wxaqzwksbhbs73yz6mtpi5za"

signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
object_storage = oci.object_storage.ObjectStorageClient(config={}, signer=signer) 
compute_client = oci.core.ComputeClient(config={}, signer=signer)
blockstorage_client = oci.core.BlockstorageClient(config={}, signer=signer)

# Function to list instances by tag
def list_instances_by_tag(compartment_id, tag_key, tag_value):
    instances = compute_client.list_instances(compartment_id).data
    filtered_instances = []
    for instance in instances:
        instance_tags = instance.freeform_tags
        if tag_key in instance_tags and instance_tags[tag_key] == tag_value and instance.lifecycle_state != 'TERMINATED':
            filtered_instances.append(instance)
    return filtered_instances

# List instances by tag

tag_key = next((value for name, value in constants if name == "tag_key"), None)
tag_value = next((value for name, value in constants if name == "tag_value"), None)
instances = list_instances_by_tag(compartment_id, tag_key, tag_value)

# Call the backup script for each instance
for instance in instances:
    print(f"Processing Instance Name: {instance.display_name}, OCID: {instance.id}")
    # Call the backup script and pass the necessary information as arguments
    args = [instance.id, instance.display_name, compartment_id]
    for name, value in constants:
        args.append(f"{name}={value}")
    subprocess.run(['python', 'backup_script.py'] + args)