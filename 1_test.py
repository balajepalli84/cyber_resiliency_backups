import oci
import os
import time
import logging
from datetime import datetime
import concurrent.futures
current_datetime = datetime.now()
datetime_string = current_datetime.strftime("%Y-%m-%d-%H-%M-%S")
config = oci.config.from_file()  # This assumes your config is in ~/.oci/config
blockstorage_client = oci.core.BlockstorageClient(config)
compute_client = oci.core.ComputeClient(config)
restored_volumes = 'ocid1.volume.oc1.iad.abuwcljtbc4szrz4tbp6rgznponac5oywvqn5fv2kgolvdpxgydghod4uf5q','ocid1.volume.oc1.iad.abuwcljt3vmixkkhffsaa6ugaeapp2i4ps4iuambbptxcmbkgta7wnpmy6rq'
for volume_data in restored_volumes:  
    attach_details = oci.core.models.AttachParavirtualizedVolumeDetails(
        instance_id='ocid1.instance.oc1.iad.anuwcljtc3adhhqcejt4cv5vwt657t3huc4w5h3ojaynu6qpi443tvnsqcjq',
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
        time.sleep(10)
    print(f"Volume {volume_data['volume_id']} attached successfully.")