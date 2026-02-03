import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname='192.168.93.100', username='sshadmin', password='lanfei_242',
               look_for_keys=False, allow_agent=False)

# 1. 开启交互式 shell 通道
chan = client.invoke_shell()
time.sleep(0.5)           # 等待设备显示 banner / motd / 提示符

# 2. 非常重要：清空欢迎信息/初始输出
chan.recv(65535)          # 或者用 10000、5000 都可以

# ────────────────────────────────────────
# 下面开始发送命令 —— 每次都要加 \n 并稍作等待
# ────────────────────────────────────────

chan.send("enable\n")
time.sleep(0.3)

# 如果需要输入 enable 密码
if chan.recv_ready():
    output = chan.recv(65535).decode('utf-8', errors='ignore')
    if "Password:" in output or "password:" in output:
        chan.send("ocsic\n")          # ← 替换成你的 enable 密码
        time.sleep(0.4)

# 此时应该已经进入特权模式（提示符带 #）
chan.send("terminal length 0\n")
chan.send("show version\n")
time.sleep(1)

# 读取输出
output = chan.recv(65535).decode('utf-8', errors='ignore')
print(output)

# ── 清理退出 ──
chan.send("exit\n")
chan.close()
client.close()