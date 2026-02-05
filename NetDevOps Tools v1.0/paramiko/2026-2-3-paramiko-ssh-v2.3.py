import paramiko
import time
import re

"""
V2.3版本改进（思科版本），将SSH连接执行命令的操作抽象为一个函数
# 1. 建立SSH连接
# 2. 打开交互式shell通道
# 3. 丢弃欢迎信息
# 4. 关闭分页
# 5. 循环执行每条命令
#    - 发送命令
#    - 智能读取输出直到出现提示符
#    - 清理输出（去回显、去提示符）
# 6. 返回 {命令: 干净输出} 的字典
# 7. 异常处理 + 资源清理
"""
def ssh_cisco_interactive(
        host: str,
        username: str,
        password: str,
        commands: list[str],
        port: int = 22,
        timeout: float = 15.0
):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            look_for_keys=False, #禁用公钥认证和ssh-agent，只用密码
            allow_agent=False,
            timeout=8    # 连接建立的超时
        )

        # 打开交互式shell通道
        channel = ssh.invoke_shell()
        channel.settimeout(1.0)

        # 丢弃初始欢迎信息 / banner / motd
        time.sleep(0.8)           # 等 banner / motd
        _ = channel.recv(8192)    # 丢弃欢迎信息

        # Cisco关闭分页
        channel.send("terminal length 0\n")
        time.sleep(0.4)
        _ = channel.recv(4096)

        # 如果需要进入特权模式（大多数 show 命令不需要，但保险起见）
        # channel.send("enable\n")
        # time.sleep(0.3)
        # channel.send(password + "\n")   # 如果有 enable 密码
        # time.sleep(0.5)
        # _ = channel.recv(4096)

        # 核心循环：逐条执行命令
        outputs = {}

        for cmd in commands:
            # 清理命令两端空格
            cmd = cmd.strip()
            # 跳过空命令
            if not cmd:
                continue
            # 发送命令 + 回车
            channel.send(cmd + "\n")
            print(f"发送: {cmd}")

            output = ""
            start = time.time()

            # 加入时间判断，超出timeout自动跳出，防止死循环
            while time.time() - start < timeout:
                if channel.recv_ready():
                    chunk = channel.recv(8192).decode('utf-8', errors='replace')
                    output += chunk

                    # 简单判断是否回到提示符（可优化为正则）
                    if re.search(r'[>#]\s*$', output, re.MULTILINE):
                        break

                time.sleep(0.05)

            # 清理输出（去掉回显 + 提示符）
            lines = output.splitlines()
            cleaned = []
            skip_next = False

            for line in lines:
                if skip_next:
                    skip_next = False
                    continue
                if cmd in line or line.strip().startswith(cmd):
                    skip_next = True  # 跳过回显行
                    continue
                if re.match(r'^\S+[>#]\s*$', line.strip()):
                    continue  # 跳过提示符
                cleaned.append(line.rstrip())

            clean_text = "\n".join(cleaned).strip()
            outputs[cmd] = clean_text

            print(f"结果 ({cmd}):\n{clean_text}\n{'-'*60}")

        return outputs

    except Exception as e:
        print(f"错误: {e}")
        return None

    finally:
        if 'channel' in locals():
            channel.close()
        ssh.close()


# 使用示例
if __name__ == '__main__':
    cmds = [
        "show ip interface brief",
        "show version",
    ]

    ssh_cisco_interactive(
        host="192.168.93.101",
        username="sshadmin",
        password="lanfei_ocsic",
        commands=cmds
    )