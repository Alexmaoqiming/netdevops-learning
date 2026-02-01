import paramiko
import time

ip = '192.168.1.41'
username = 'sshadmin'
password = 'cisco'
enable_password = 'ocsic'

# 创建paramiko的SSH客户端对象
ssh_client = paramiko.SSHClient()
# 创建秘钥(标准配置）
ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh_client.connect(hostname=ip, username=username, password=password)

print("Successfully connected to " + ip)
# 唤醒shell
command = ssh_client.invoke_shell()

command.send("enable\n")
time.sleep(1)
command.send(enable_password + "\n")
time.sleep(1)
command.send("configure terminal\n")
command.send("int loop 1\n")
command.send("ip address 1.1.1.1 255.255.255.255\n")
command.send("end\n")
command.send("wr mem\n")

time.sleep(2)
output = command.recv(65535)
print(output.decode("ascii"))

ssh_client.close()
