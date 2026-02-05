import paramiko
import time

ip = '192.168.93.101'
username = 'sshadmin'
password = 'Lanfei_212'

# 创建paramiko的SSH对象
ssh_client = paramiko.SSHClient()
# 创建秘钥
ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
# 连接SSH
ssh_client.connect(hostname=ip, username=username, password=password, look_for_keys=False, allow_agent=False)

print("Successfully connected to " + ip)
# 唤醒shell
command = ssh_client.invoke_shell()

# 发送华为配置命令
command.send("sys\n")
time.sleep(1)
# 配置一个环回接口
command.send("int loop 1\n")
command.send("ip add 1.1.1.1 24\n")
time.sleep(1)
command.send("quit\n")
time.sleep(1)
command.send("save\n")
command.send("y\n")

output = command.recv(65535)
print(output.decode("ascii"))

ssh_client.close()
