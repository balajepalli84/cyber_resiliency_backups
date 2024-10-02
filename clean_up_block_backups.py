import oci
import logging

# OCI config and clients initialization
config = oci.config.from_file()  # This assumes your config is in ~/.oci/config
blockstorage_client = oci.core.BlockstorageClient(config)

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Function to delete block volume backups
def delete_block_volume_backups(compartment_id, name_prefix):
    logger.info("Fetching block volume backups...")
    backups = blockstorage_client.list_volume_backups(compartment_id=compartment_id).data

    # Filter backups that start with the specified name prefix
    filtered_backups = [backup for backup in backups if backup.display_name.startswith(name_prefix)]

    for backup in filtered_backups:
        try:
            logger.info(f"Deleting block volume backup: {backup.display_name}, OCID: {backup.id}")
            blockstorage_client.delete_volume_backup(backup.id)
        except oci.exceptions.ServiceError as e:
            logger.error(f"Error deleting volume backup {backup.display_name}: {e.message}")

# Function to delete restored block volumes
def delete_block_volumes(compartment_id, name_prefix):
    logger.info("Fetching block volumes...")
    volumes = blockstorage_client.list_volumes(compartment_id=compartment_id).data

    # Filter volumes that start with the specified name prefix
    filtered_volumes = [volume for volume in volumes if volume.display_name.startswith(name_prefix)]

    for volume in filtered_volumes:
        try:
            logger.info(f"Deleting block volume: {volume.display_name}, OCID: {volume.id}")
            blockstorage_client.delete_volume(volume.id)
        except oci.exceptions.ServiceError as e:
            logger.error(f"Error deleting block volume {volume.display_name}: {e.message}")

# Main function to delete backups and restored volumes
def main():
    # Specify your compartment OCID and name prefix
    compartment_id = "ocid1.compartment.oc1..aaaaaaaafklcekq7wnwrt4zxeizcrmvhltz6wxaqzwksbhbs73yz6mtpi5za"  # Replace with your compartment OCID
    backup_name_prefix = "cra-test"  # Replace with the name prefix to search for
    restored_volume_prefix='restored_block_volume'
    # Delete volume backups and block volumes
    delete_block_volume_backups(compartment_id, backup_name_prefix)
    delete_block_volumes(compartment_id, restored_volume_prefix)

if __name__ == "__main__":
    main()
