import paramiko
import time

"""
V2.0版本改进（思科版本）：
1.增加了开局清空banner/motd/提示符的命令
2.增加是否存在enable密码的判断
3.增加了Cisco不分页的命令terminal length 0
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

# 此时应该已经进入特权模式（提示符带 #）
command.send("terminal length 0\n")
command.send("show version\n")
time.sleep(1)

# 读取输出
output = command.recv(65535).decode('utf-8', errors='ignore')
print(output)

# ── 清理退出 ──
command.send("exit\n")
command.close()
client.close()