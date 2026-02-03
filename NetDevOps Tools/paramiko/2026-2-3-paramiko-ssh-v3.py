import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.93.100", username="sshadmin", password="lanfei_242",allow_agent=False, look_for_keys=False)

# 开启交互式 shell
channel = ssh.invoke_shell()
channel.settimeout(10)

channel.send("enable\n")
time.sleep(1)
channel.send("ocsic\n")
time.sleep(1)
# 关闭分页（网络设备常用）
channel.send("terminal length 0\n")
time.sleep(0.5)

# 交互式 shell（适合需要连续输入命令的场景）
commands = [
    "show version\n",
    "show ip interface brief\n",
    "exit\n"
]

for cmd in commands:
    channel.send(cmd)
    time.sleep(1)
    while channel.recv_ready():
        print(channel.recv(4096).decode(errors='ignore'), end='')

ssh.close()