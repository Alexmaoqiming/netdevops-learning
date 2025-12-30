import paramiko
import time

ip = '192.168.1.110'
username = 'yunwei'
password = 'lanfei_242'

# 创建paramiko的SSH对象
ssh_client = paramiko.SSHClient()
# 创建秘钥
ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
# 连接SSH
ssh_client.connect(hostname=ip, username=username, password=password)
print("Successfully connected to " + ip)
# 唤醒shell
command = ssh_client.invoke_shell()

command.send("sys\n")
time.sleep(1)
command.send("int loop 1\n")
command.send("ip add 1.1.1.1 24\n")
time.sleep(1)
command.send("return\n")

command.send("save\n")
command.send("y\n")
time.sleep(1)

output = command.recv(65535)
print(output.decode("ascii"))

ssh_client.close()
