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
logger = logging.getLogger(__name__)  
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

print('all done...')