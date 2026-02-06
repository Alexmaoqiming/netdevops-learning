import paramiko
import time
import re
from typing import List, Dict, Optional, Tuple
import pwinput  # 需要先 pip install pwinput

"""
程序版本说明（最新版）：
- 支持 Cisco IOS / Huawei VRP 设备批量巡检
- 从 ip_list.txt 读取 IP 列表（每行一个 IP，支持 # 注释）
- 自动检测设备类型（基于登录 banner / 初始输出）
- 支持权限提升（enable / super）
- 命令列表根据设备类型自动适配（show / display）
- 输出每条命令的发送提示 + 清理后结果，带 [IP] 前缀
- 改进清理逻辑：更宽松，避免误删有效内容
- 去除 ANSI 颜色码，输出更干净
- 错误处理更健壮，一台设备失败不影响其他
"""

def detect_device_type(initial_output: str) -> str:
    """根据初始 banner 判断设备类型"""
    lower_text = initial_output.lower()
    if any(word in lower_text for word in ['huawei', 'vrp', 'ne', 's series', '<huawei>', '[quidway]', 'sysname']):
        return 'huawei'
    if any(word in lower_text for word in ['cisco', 'ios', 'xe', 'catalyst', 'nexus']):
        return 'cisco'
    print("警告：无法自动识别设备类型，默认使用 Cisco 配置")
    return 'cisco'


def clean_output(raw_output: str, sent_command: str) -> str:
    """
    改进版输出清理函数：
    - 更宽松匹配回显，避免误删有效内容
    - 去除 ANSI 颜色码（Cisco 新版常带）
    - 去除多余空行和纯提示符行
    """
    # 先去除 ANSI 颜色码
    raw_output = re.sub(r'\x1B\[[0-9;]*[mK]', '', raw_output)

    lines = raw_output.splitlines()
    cleaned = []
    skip_next = False

    for line in lines:
        stripped = line.rstrip()

        # 跳过空行
        if not stripped:
            continue

        # 跳过命令回显（包含命令本身或提示符+命令）
        if sent_command in stripped or stripped.endswith(sent_command) or stripped.startswith(sent_command):
            skip_next = True
            continue

        if skip_next:
            skip_next = False
            continue

        # 跳过纯提示符行
        if re.match(r'^[\w\.-]*[>#\[\]<]\s*$', stripped):
            continue

        cleaned.append(stripped)

    result = "\n".join(cleaned).strip()
    # 去除连续多个空行
    result = re.sub(r'\n{3,}', '\n\n', result)

    return result if result else '[无有效输出，可能权限不足或命令无返回]'


def network_ssh_execute(
        host: str,
        username: str,
        password: str,
        commands: List[str],
        port: int = 22,
        timeout_per_cmd: float = 15.0,
        privilege_password: Optional[str] = None,
        privilege_level: str = "3"
) -> Tuple[str, Dict[str, str]]:
    """
    通用网络设备 SSH 执行器
    返回 (device_type, {命令: 清理后输出})
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

        # 收集初始输出用于类型检测
        time.sleep(1.5)
        initial_output = ""
        start = time.time()
        while time.time() - start < 3.0:
            if chan.recv_ready():
                chunk = chan.recv(8192).decode('utf-8', errors='replace')
                initial_output += chunk
            time.sleep(0.1)

        device_type = detect_device_type(initial_output)
        print(f"[{host}] 自动检测设备类型：{device_type.upper()}")

        # 根据类型设置环境参数
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
            print(f"[{host}] 正在提升权限...")
            chan.send(privilege_cmd)
            time.sleep(0.4)
            chan.send(privilege_password + "\n")
            time.sleep(0.8)
            _ = chan.recv(8192)

        for cmd in commands:
            cmd = cmd.strip()
            if not cmd:
                continue

            print(f"[{host}] 发送: {cmd}")
            chan.send(cmd + "\n")

            output = ""
            start_time = time.time()

            while time.time() - start_time < timeout_per_cmd:
                if chan.recv_ready():
                    chunk = chan.recv(8192).decode('utf-8', errors='replace')
                    output += chunk

                if re.search(prompt_pattern, output, re.MULTILINE | re.DOTALL):
                    break

                time.sleep(0.08)

            cleaned = clean_output(output, cmd)
            outputs[cmd] = cleaned

            print(f"[{host}] 结果 ({cmd}):")
            print(cleaned)
            print("─" * 80)

    except Exception as e:
        print(f"[{host}] 连接或执行失败: {e}")
    finally:
        if 'chan' in locals():
            chan.close()
        ssh.close()

    return device_type, outputs


# ─── 主程序 ────────────────────────────────────────────────
if __name__ == '__main__':
    PORT = 22

    # 从文件读取 IP 列表
    ip_list_file = "ip_list.txt"
    try:
        with open(ip_list_file, 'r', encoding='utf-8') as f:
            ip_list = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
        if not ip_list:
            print(f"{ip_list_file} 文件为空或无有效 IP")
            exit(1)
        print(f"读取到 {len(ip_list)} 个设备：")
        for ip in ip_list:
            print(f"  - {ip}")
    except FileNotFoundError:
        print(f"找不到 {ip_list_file}，请创建文件，每行一个 IP")
        exit(1)

    # 统一凭证输入
    print("\n" + "="*60)
    username = input("请输入 SSH 用户名（所有设备共用）: ").strip()
    password = pwinput.pwinput(prompt="请输入 SSH 密码: ", mask="*")

    need_privilege = input("是否需要进入特权模式？(y/N): ").strip().lower()
    privilege_password = None
    privilege_level = "3"

    if need_privilege in ('y', 'yes'):
        level_input = input("特权级别 (3/15，默认3): ").strip() or "3"
        privilege_level = level_input
        prompt_text = "enable" if privilege_level == "3" else f"super level {privilege_level}"
        privilege_password = pwinput.pwinput(prompt=f"请输入特权密码 ({prompt_text}): ", mask="*")

    print("\n" + "="*60)
    print("开始批量执行...\n")

    for host in ip_list:
        print(f"\n{'='*30} 处理设备：{host} {'='*30}\n")

        # 定义命令集（可扩展）
        command_sets = {
            'cisco': [
                "show version",
                "show ip interface brief",
                "show running-config | include hostname",
            ],
            'huawei': [
                "display version",
                "display ip interface brief",
                "display current-configuration | include sysname",
            ]
        }

        # 先获取类型
        try:
            device_type, _ = network_ssh_execute(
                host=host,
                username=username,
                password=password,
                commands=[],  # 只检测类型
                port=PORT,
                privilege_password=privilege_password,
                privilege_level=privilege_level
            )
        except Exception as e:
            print(f"[{host}] 检测类型失败，跳过: {e}")
            continue

        # 选择对应命令
        commands = command_sets.get(device_type, command_sets['cisco'])

        print(f"[{host}] 将执行 {len(commands)} 条命令：")
        for cmd in commands:
            print(f"  - {cmd}")

        # 执行命令
        try:
            _, result = network_ssh_execute(
                host=host,
                username=username,
                password=password,
                commands=commands,
                port=PORT,
                privilege_password=privilege_password,
                privilege_level=privilege_level
            )
        except Exception as e:
            print(f"[{host}] 执行失败: {e}")

    print("\n" + "="*60)
    print("批量执行完毕。")