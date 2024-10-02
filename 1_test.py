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


# Load constants from the JSON configuration file
with open(r'C:\Security\CRA\mycode\configuration.json', 'r') as config_file:
    config_data = json.load(config_file)

current_datetime = datetime.now()
datetime_string = current_datetime.strftime("%Y-%m-%d-%H-%M-%S")
# Initialize the default config and signer


# Extract the necessary constants
craserverinfo = config_data['craserverinfo']
compartmentinfo = config_data['compartmentinfo']
cratagginginfo = config_data['cratagginginfo']
objectstorageinfo = config_data['objectstorageinfo']
networkinfo = config_data['networkinfo']
logginginfo=config_data['logging']
log_group_id = logginginfo["loggroupocid"]
log_id = logginginfo["logocid"]
print(log_group_id)
print(log_id)