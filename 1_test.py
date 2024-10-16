import oci
from oci.loggingingestion import LoggingClient, models
import time
from datetime import datetime,timezone
import random
import string
import paramiko
import concurrent.futures
import os
import json

import oci

def get_instance_os(instance_id, compartment_id):
    # Create a client for the Compute service
    config = oci.config.from_file()  # Load default OCI config file
    compute_client = oci.core.ComputeClient(config)

    # Get instance details
    instance = compute_client.get_instance(instance_id).data
    
    # Get image details to retrieve OS information
    image_id = instance.source_details.image_id
    image = compute_client.get_image(image_id).data
    
    # OS details are part of the image details
    os = image.operating_system
    os_version = image.operating_system_version

    return f"Operating System: {os} {os_version}"

# Replace with your instance OCID and compartment OCID
instance_ocid = 'ocid1.instance.oc1.iad.anuwcljtc3adhhqczewcudqk4fflmgjdqmhe7qhxrnfknmosqjc4lrgdvl3q'
compartment_ocid = 'ocid1.compartment.oc1..aaaaaaaafklcekq7wnwrt4zxeizcrmvhltz6wxaqzwksbhbs73yz6mtpi5za'

os_info = get_instance_os(instance_ocid, compartment_ocid)
print(os_info)
