import paramiko
private_key_path=r'C:\Security\CRA\mycode\creds\reuse_private.key'

for public_ip in '129.213.105.115','150.136.126.173','193.122.143.102':
    print(public_ip)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    private_key = paramiko.RSAKey.from_private_key_file(private_key_path)
    ssh.connect(public_ip, username='opc', pkey=private_key)

    stdin, stdout1, stderr1 = ssh.exec_command(f"sudo lsblk")
    output1 = stdout1.read().decode()
    error1 = stderr1.read().decode()
    print("Command 1 Output:")
    print(output1)
    if error1:
        print("Command 1 Error:")
        print(error1)
        # Command 2: Run script
    stdin, stdout2, stderr2 = ssh.exec_command(f"sudo python --version")
    output2 = stdout2.read().decode()
    error2 = stderr2.read().decode()
    print("Command 2 Output:")
    print(output2)
    if error2:
        print("Command 2 Error:")
        print(error2)

    ssh.close()
    
    