import paramiko
import time

"""
V2.1版本改进（思科版本）：
对command命令使用list重构，命令输入更方便
"""
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname='192.168.93.101', username='sshadmin', password='lanfei_ocsic',
               look_for_keys=False, allow_agent=False)

# 开启交互式shell通道
command = client.invoke_shell()
time.sleep(0.5)

# 等待设备显示banner/motd/提示符，清空欢迎信息
command.recv(65535)          # 或者用10000、5000都可以

# 输入enable判断是否需要输入密码
command.send("enable\n")
time.sleep(0.3)

# 如果需要输入 enable 密码
if command.recv_ready():
    # 获取是否有password的输出
    output = command.recv(65535).decode('utf-8', errors='ignore')
    if "Password:" in output or "password:" in output:
        command.send("ocsic\n")          # 输入enable 密码
        time.sleep(0.4)


# 交互式 shell（适合需要连续输入命令的场景）
commands = [
    "terminal length 0\n",  # 首先输入禁止分页
    "show version\n",
    "show ip interface brief\n",
    "exit\n"
]

for cmd in commands:
    command.send(cmd)
    time.sleep(1)
    while command.recv_ready():
        print(command.recv(4096).decode(errors='ignore'), end='')

client.close()