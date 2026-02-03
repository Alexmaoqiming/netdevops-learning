import paramiko
import time
import re
from typing import List, Dict, Optional
import pwinput  # 需要先 pip install pwinput

"""
程序版本说明：
- 支持 Cisco IOS / Huawei VRP 设备
- 自动检测设备类型（通过登录 banner / 初始输出关键词）
- 支持权限提升（enable / super）
- 输出每条命令的发送提示 + 清理后结果
- 如果检测失败，默认当作 Cisco 处理并警告
"""

def detect_device_type(initial_output: str) -> str:
    """根据初始 banner 判断设备类型"""
    lower_text = initial_output.lower()
    if any(word in lower_text for word in ['huawei', 'vrp', 'ne', 's series', '<huawei>', '[quidway]', 'sysname']):
        return 'huawei'
    # Cisco 关键词或默认
    if any(word in lower_text for word in ['cisco', 'ios', 'xe', 'catalyst', 'nexus', '>', '#']):
        return 'cisco'
    print("警告：无法自动识别设备类型，默认使用 Cisco 配置。如为华为设备，请检查权限或手动指定。")
    return 'cisco'


def network_ssh_execute(
        host: str,
        username: str,
        password: str,
        commands: List[str],
        port: int = 22,
        timeout_per_cmd: float = 15.0,
        privilege_password: Optional[str] = None,
        privilege_level: str = "3"
) -> Dict[str, str]:
    """
    连接网络设备（Cisco 或 Huawei），执行命令列表，返回 {命令: 清理后输出}
    """
    outputs = {}
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # 生产环境建议改 RejectPolicy

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

        # 收集初始 banner / MOTD / 提示符（用于自动检测）
        time.sleep(1.5)
        initial_output = ""
        start = time.time()
        while time.time() - start < 3.0:
            if chan.recv_ready():
                chunk = chan.recv(8192).decode('utf-8', errors='replace')
                initial_output += chunk
            time.sleep(0.1)

        device_type = detect_device_type(initial_output)
        print(f"自动检测设备类型：{device_type.upper()}")

        # 根据类型配置参数
        if device_type == 'cisco':
            paging_cmd = "terminal length 0\n"
            privilege_cmd = "enable\n"
            prompt_pattern = r'[>#]\s*$'
            clean_prompt_pattern = r'^[\w\.-]+[>#]\s*$'
        else:  # huawei
            paging_cmd = "screen-length 0 temporary\n"
            privilege_cmd = f"super {privilege_level}\n"
            prompt_pattern = r'[\<\[][\w\.-]+[\>\]]\s*$'
            clean_prompt_pattern = r'^[\<\[][\w\.-]+[\>\]]\s*$'

        # 关闭分页
        chan.send(paging_cmd)
        time.sleep(0.5)
        _ = chan.recv(4096)

        # 权限提升
        if privilege_password:
            chan.send(privilege_cmd)
            time.sleep(0.4)
            chan.send(privilege_password + "\n")
            time.sleep(0.8)
            _ = chan.recv(8192)  # 丢弃响应

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

                if re.search(prompt_pattern, output, re.MULTILINE | re.DOTALL):
                    break

                time.sleep(0.08)

            # 调试用：显示原始输出（可注释掉）
            # print(f"[原始输出 {cmd}]:\n{output}\n{'='*60}")

            # 清理输出
            lines = output.splitlines()
            cleaned = []
            echo_skipped = False

            for line in lines:
                stripped = line.rstrip()
                if not echo_skipped and (cmd in stripped or stripped.startswith(cmd)):
                    echo_skipped = True
                    continue
                if re.match(clean_prompt_pattern, stripped):
                    continue
                if stripped:
                    cleaned.append(stripped)

            clean_output = "\n".join(cleaned).strip()
            outputs[cmd] = clean_output

            print(f"结果 ({cmd}):\n{clean_output if clean_output else '[无输出或权限不足]'}")
            print("─" * 70)

    except Exception as e:
        print(f"连接或执行失败 {host}: {e}")
    finally:
        if 'chan' in locals():
            chan.close()
        ssh.close()

    return outputs


# ─── 主程序 ────────────────────────────────────────────────
if __name__ == '__main__':
    HOST = "192.168.93.101"
    PORT = 22

    print(f"正在連線到設備：{HOST}:{PORT}")
    print("-" * 50)

    username = input("請輸入 SSH 用戶名: ").strip()
    if not username:
        print("用戶名不能為空")
        exit(1)

    password = pwinput.pwinput(prompt="請輸入 SSH 密碼: ", mask="*")
    if not password:
        print("密碼不能為空")
        exit(1)

    need_privilege = input("是否需要進入特權模式？(y/N): ").strip().lower()
    privilege_password = None
    privilege_level = "3"

    if need_privilege in ('y', 'yes'):
        level_input = input("特權級別 (3/15，默认3): ").strip() or "3"
        privilege_level = level_input
        prompt_text = "enable" if privilege_level == "3" else f"super level {privilege_level}"
        privilege_password = pwinput.pwinput(prompt=f"請輸入特權模式密碼 ({prompt_text}): ", mask="*")
        if not privilege_password:
            print("已取消特權模式，將以普通模式執行")
            privilege_password = None

    # 根据设备类型自动适配的命令列表
    commands = [
        "show version" if "cisco" in HOST.lower() else "display version",
        "show ip interface brief" if "cisco" in HOST.lower() else "display ip interface brief",
        "show running-config | include hostname" if "cisco" in HOST.lower() else "display current-configuration | include sysname",
    ]

    print("\n開始執行命令...\n")

    result = network_ssh_execute(
        host=HOST,
        username=username,
        password=password,
        commands=commands,
        port=PORT,
        privilege_password=privilege_password,
        privilege_level=privilege_level
    )

    print("\n全部命令執行完畢。")