import paramiko
import time
import re


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
            look_for_keys=False,
            allow_agent=False,
            timeout=8
        )

        channel = ssh.invoke_shell()
        channel.settimeout(1.0)

        time.sleep(0.8)           # 等 banner / motd
        _ = channel.recv(8192)    # 丢弃欢迎信息

        # 关闭分页（Cisco 必须）
        channel.send("terminal length 0\n")
        time.sleep(0.4)
        _ = channel.recv(4096)

        # 如果需要进入特权模式（大多数 show 命令不需要，但保险起见）
        # channel.send("enable\n")
        # time.sleep(0.3)
        # channel.send(password + "\n")   # 如果有 enable 密码
        # time.sleep(0.5)
        # _ = channel.recv(4096)

        outputs = {}

        for cmd in commands:
            cmd = cmd.strip()
            if not cmd:
                continue

            channel.send(cmd + "\n")
            print(f"发送: {cmd}")

            output = ""
            start = time.time()

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
        host="192.168.93.100",
        username="sshadmin",
        password="lanfei_242",
        commands=cmds
    )