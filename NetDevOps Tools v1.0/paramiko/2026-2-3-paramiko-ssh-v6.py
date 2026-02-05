import paramiko
import time
import re
from typing import List, Dict, Optional


def cisco_ssh_execute(
        host: str,
        username: str,
        password: str,
        commands: List[str],
        port: int = 22,
        timeout_per_cmd: float = 15.0,
        enable_password: Optional[str] = None
) -> Dict[str, str]:
    """
    使用 paramiko 连接 Cisco 设备并执行多条命令
    返回 {命令: 清理后的输出} 的字典
    """
    outputs = {}
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # 测试用；生产改 RejectPolicy + known_hosts

    try:
        ssh.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            look_for_keys=False,
            allow_agent=False,
            timeout=10
        )

        chan = ssh.invoke_shell(width=200, height=500)  # 加大缓冲避免截断
        chan.settimeout(2.0)

        time.sleep(1.0)
        _ = chan.recv(8192)  # 丢弃 banner / motd

        # 关闭分页（必须）
        chan.send("terminal length 0\n")
        time.sleep(0.5)
        _ = chan.recv(4096)

        # 如果需要进入特权模式
        if enable_password:
            chan.send("enable\n")
            time.sleep(0.4)
            chan.send(enable_password + "\n")
            time.sleep(0.6)
            _ = chan.recv(4096)

        for cmd in commands:
            cmd = cmd.strip()
            if not cmd:
                continue

            chan.send(cmd + "\n")
            print(f"发送: {cmd}")

            output = ""
            start_time = time.time()

            while time.time() - start_time < timeout_per_cmd:
                if chan.recv_ready():
                    chunk = chan.recv(8192).decode('utf-8', errors='replace')
                    output += chunk

                # 检测是否回到提示符（# 或 > 结尾）
                if re.search(r'[>#]\s*$', output, re.MULTILINE | re.DOTALL):
                    break

                time.sleep(0.08)

            # 清理输出
            lines = output.splitlines()
            cleaned = []
            echo_skipped = False

            for line in lines:
                stripped = line.rstrip()
                if not echo_skipped and (cmd in stripped or stripped.startswith(cmd)):
                    echo_skipped = True
                    continue
                if re.match(r'^[\w\.-]+[>#]\s*$', stripped):  # 跳过提示符行
                    continue
                if stripped:  # 去掉纯空行
                    cleaned.append(stripped)

            clean_output = "\n".join(cleaned).strip()
            outputs[cmd] = clean_output

            print(f"结果 ({cmd}):\n{clean_output}\n{'─'*70}")

    except Exception as e:
        print(f"连接/执行失败 {host}: {e}")
    finally:
        if 'chan' in locals():
            chan.close()
        ssh.close()

    return outputs


# ─── 使用示例 ────────────────────────────────────────
if __name__ == '__main__':
    result = cisco_ssh_execute(
        host="192.168.93.100",
        username="sshadmin",
        password="lanfei_242",
        enable_password="ocsic",   # 如果需要 enable 密码，填入；否则 None
        commands=[
            "show version",
            "show ip interface brief",
            "show running-config | include hostname"
        ]
    )