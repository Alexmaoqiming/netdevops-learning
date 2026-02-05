import paramiko
import time
import re
from typing import List, Dict, Optional

"""
V2.4版本改进的华为版本
"""
def huawei_vrp_ssh_execute(
        host: str,
        username: str,
        password: str,
        commands: List[str],
        port: int = 22,
        timeout_per_cmd: float = 12.0,
        super_password: Optional[str] = None   # 部分设备需要 super
) -> Dict[str, str]:
    """
    paramiko 连接华为 VRP 设备并批量执行命令
    """
    outputs = {}
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # 生产环境建议改用 known_hosts

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

        chan = ssh.invoke_shell(width=200, height=500)
        chan.settimeout(2.0)

        time.sleep(1.0)
        _ = chan.recv(8192)  # 丢弃登录信息

        # 关闭分页（华为常用命令）
        chan.send("screen-length 0 temporary\n")
        time.sleep(0.5)
        _ = chan.recv(4096)

        # 如果需要进入系统视图或 super 权限
        if super_password:
            chan.send("super\n")
            time.sleep(0.4)
            chan.send(super_password + "\n")
            time.sleep(0.6)
            _ = chan.recv(4096)

        for cmd in commands:
            cmd = cmd.strip()
            if not cmd:
                continue

            chan.send(cmd + "\n")
            print(f"发送: {cmd}")

            output = ""
            start = time.time()

            while time.time() - start < timeout_per_cmd:
                if chan.recv_ready():
                    chunk = chan.recv(8192).decode('utf-8', errors='replace')
                    output += chunk

                # 华为提示符通常是 < > 或 [ ]
                if re.search(r'[\<\[][\w\.-]+[\>\]]\s*$', output, re.MULTILINE | re.DOTALL):
                    break

                time.sleep(0.07)

            # 清理输出
            lines = output.splitlines()
            cleaned = []
            echo_found = False

            for line in lines:
                stripped = line.rstrip()
                if not echo_found and (cmd in stripped or stripped.lstrip().startswith(cmd)):
                    echo_found = True
                    continue
                if re.match(r'^[\<\[][\w\.-]+[\>\]]\s*$', stripped):
                    continue
                if stripped:
                    cleaned.append(stripped)

            clean_text = "\n".join(cleaned).strip()
            outputs[cmd] = clean_text

            print(f"结果 ({cmd}):\n{clean_text}\n{'─'*70}")

    except Exception as e:
        print(f"连接/执行失败 {host}: {e}")
    finally:
        if 'chan' in locals():
            chan.close()
        ssh.close()

    return outputs


# ─── 使用示例 ────────────────────────────────────────
if __name__ == '__main__':
    result = huawei_vrp_ssh_execute(
        host="192.168.93.102",
        username="sshadmin",
        password="Lanfei_212",
        super_password=None,           # 如需填 super 密码
        commands=[
            "display version",
            "display ip interface brief",
            "display current-configuration | include sysname"
        ]
    )