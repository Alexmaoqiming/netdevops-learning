import paramiko
import time
import re
from typing import List, Dict, Optional, Tuple
import pwinput  # pip install pwinput
import sys
import getpass

"""
我的网络工具箱 1.0
- 带菜单交互框架
- 当前功能：1. 批量保存交换机配置 (write memory / save)
- 后续可轻松添加巡检、批量执行命令等
"""

# ─── 通用函数（从之前保留并微调） ────────────────────────────────────────────────

def detect_device_type(initial_output: str) -> str:
    lower_text = initial_output.lower()
    if any(word in lower_text for word in ['huawei', 'vrp', 'ne', 's series', '<huawei>', '[quidway]', 'sysname']):
        return 'huawei'
    if any(word in lower_text for word in ['cisco', 'ios', 'xe', 'catalyst', 'nexus']):
        return 'cisco'
    print("警告：无法识别设备类型，默认当作 Cisco 处理")
    return 'cisco'


def clean_output(raw_output: str, sent_command: str) -> str:
    raw_output = re.sub(r'\x1B\[[0-9;]*[mK]', '', raw_output)
    lines = raw_output.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.rstrip()
        if not stripped:
            continue
        if sent_command in stripped or stripped.endswith(sent_command):
            continue
        if re.match(r'^[\w\.-]*[>#\[\]<]\s*$', stripped):
            continue
        if any(kw in stripped.lower() for kw in ['ok', 'building configuration', 'configuration', '成功', 'committed']):
            cleaned.append(stripped)
    result = "\n".join(cleaned).strip()
    return result if result else '[操作完成，通常无额外提示]'


def network_ssh_execute(
        host: str,
        username: str,
        password: str,
        commands: List[str],
        port: int = 22,
        timeout_per_cmd: float = 25.0,
        privilege_password: Optional[str] = None,
        privilege_level: str = "3"
) -> Tuple[str, Dict[str, str]]:
    outputs = {}
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    chan = None
    try:
        ssh.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            look_for_keys=False,
            allow_agent=False,
            timeout=12
        )

        chan = ssh.invoke_shell(width=200, height=500)
        chan.settimeout(3.0)

        # 读取初始 banner
        time.sleep(1.8)
        initial_output = ""
        start = time.time()
        while time.time() - start < 4.0:
            if chan.recv_ready():
                initial_output += chan.recv(8192).decode('utf-8', errors='replace')
            time.sleep(0.1)

        device_type = detect_device_type(initial_output)
        print(f"[{host}] 设备类型：{device_type.upper()}")

        # 参数
        if device_type == 'cisco':
            paging_cmd = "terminal length 0\n"
            privilege_cmd = "enable\n"
            prompt_pattern = r'[>#]\s*$'
        else:
            paging_cmd = "screen-length 0 temporary\n"
            privilege_cmd = f"super {privilege_level}\n"
            prompt_pattern = r'[\<\[][\w\.-]+[\>\]]\s*$'

        # 关闭分页
        chan.send(paging_cmd)
        time.sleep(0.6)
        _ = chan.recv(4096)

        # 权限提升
        if privilege_password:
            print(f"[{host}] 提升权限...")
            chan.send(privilege_cmd)
            time.sleep(0.5)
            chan.send(privilege_password + "\n")
            time.sleep(1.5)
            _ = chan.recv(8192)

        for cmd in commands:
            cmd = cmd.strip()
            if not cmd:
                continue

            print(f"[{host}] 执行: {cmd}")
            chan.send(cmd + "\n")

            output = ""
            start_time = time.time()
            while time.time() - start_time < timeout_per_cmd:
                if chan.recv_ready():
                    chunk = chan.recv(8192).decode('utf-8', errors='replace')
                    output += chunk
                if re.search(prompt_pattern, output[-300:], re.MULTILINE | re.DOTALL):
                    break
                time.sleep(0.1)

            # 额外读取剩余输出
            time.sleep(2.0)
            while chan.recv_ready():
                output += chan.recv(8192).decode('utf-8', errors='replace')
                time.sleep(0.2)

            cleaned = clean_output(output, cmd)
            outputs[cmd] = cleaned

            print(f"[{host}] 结果：")
            print(cleaned or "[通常表示成功]")
            print("─" * 70)

    except Exception as e:
        print(f"[{host}] 失败：{str(e)}")
    finally:
        if chan:
            chan.close()
        ssh.close()

    return device_type, outputs


def batch_save_config():
    """功能1：批量保存交换机配置"""

    ip_list_file = "ip_list.txt"
    try:
        with open(ip_list_file, 'r', encoding='utf-8') as f:
            ip_list = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
        if not ip_list:
            print(f"{ip_list_file} 为空或无有效IP")
            return
        print(f"\n发现 {len(ip_list)} 台设备")
    except FileNotFoundError:
        print(f"未找到 {ip_list_file}，请创建文件并填入IP列表")
        return

    # 凭证（只问一次）
    print("\n" + "═"*60)
    username = input("SSH 用户名（所有设备共用）：").strip()
    if not username:
        print("用户名不能为空")
        return

    password = pwinput.pwinput(prompt="SSH 密码：", mask="*")
    if not password:
        print("密码不能为空")
        return

    need_priv = input("需要进入特权模式？(y/N)：").strip().lower()
    privilege_password = None
    privilege_level = "3"

    if need_priv in ('y', 'yes'):
        level = input("特权级别 (3/15，默认3)：").strip() or "3"
        privilege_level = level
        prompt_txt = "enable" if level == "3" else f"super {level}"
        privilege_password = pwinput.pwinput(prompt=f"特权密码 ({prompt_txt})：", mask="*")

    print("\n开始批量保存配置...\n")

    command_sets = {
        'cisco': ["write memory"],
        'huawei': ["save"]
        # 如果华为总是问确认，可改为 ["save force"] 或 ["save", "Y"]
    }

    for host in ip_list:
        print(f"\n{'═'*30} {host} {'═'*30}\n")

        try:
            device_type, _ = network_ssh_execute(
                host=host,
                username=username,
                password=password,
                commands=[],  # 只检测类型
                privilege_password=privilege_password,
                privilege_level=privilege_level
            )

            commands = command_sets.get(device_type, command_sets['cisco'])
            print(f"将执行：{commands[0]}")

            _, results = network_ssh_execute(
                host=host,
                username=username,
                password=password,
                commands=commands,
                privilege_password=privilege_password,
                privilege_level=privilege_level
            )

            print(f"[{host}] 保存流程完成")

        except Exception as e:
            print(f"[{host}] 操作异常：{e}")

    print("\n" + "═"*60)
    print("所有设备保存操作已执行完毕")


# ─── 主菜单 ────────────────────────────────────────────────

def show_menu():
    print("\n" + "═"*60)
    print("      我的网络工具箱 1.0")
    print("═"*60)
    print("  1. 批量保存所有交换机配置 (write / save)")
    print("  0. 退出程序")
    print("═"*60)


def main():
    while True:
        show_menu()
        choice = input("请输入选项 (0-9)：").strip()

        if choice in ('0', 'q', 'quit', 'exit'):
            print("\n感谢使用，再见！")
            sys.exit(0)

        elif choice == '1':
            batch_save_config()

        else:
            print("无效选项，请重新输入")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断，程序退出")
    except Exception as e:
        print(f"程序异常：{e}")