import paramiko
import telnetlib
import time
import re
import sys
from typing import List, Dict, Optional, Tuple
import pwinput


"""
我的网络工具箱 1.1 - 修正版
- 支持 SSH + Telnet 设备分开管理
- SSH 清单：  ip_list_ssh.txt
- Telnet 清单：ip_list_telnet.txt
- 当前功能：批量保存交换机配置
"""


# ─── 通用辅助函数 ────────────────────────────────────────────────

def detect_device_type(initial_output: str) -> str:
    lower_text = initial_output.lower()
    if any(word in lower_text for word in ['huawei', 'vrp', 'ne', 's series', '<huawei>', '[quidway]', 'sysname']):
        return 'huawei'
    if any(word in lower_text for word in ['cisco', 'ios', 'xe', 'catalyst', 'nexus']):
        return 'cisco'
    print("警告：无法识别设备类型，默认当作 Cisco 处理")
    return 'cisco'


def clean_output(raw_output: str, sent_command: str) -> str:
    raw_output = re.sub(r'\x1B\[[0-9;]*[mK]', '', raw_output)  # 去除 ANSI 颜色
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
        if any(kw in stripped.lower() for kw in ['ok', 'building configuration', 'configuration', '成功', 'committed', 'wrote']):
            cleaned.append(stripped)
    result = "\n".join(cleaned).strip()
    return result if result else '[操作完成，通常无额外提示]'


# ─── SSH 处理函数 ────────────────────────────────────────────────

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
            timeout=18
        )

        chan = ssh.invoke_shell(width=200, height=500)
        chan.settimeout(3.0)

        # 读取初始 banner
        time.sleep(1.5)
        initial_output = ""
        start = time.time()
        while time.time() - start < 5.0:
            if chan.recv_ready():
                initial_output += chan.recv(8192).decode('utf-8', errors='replace')
            time.sleep(0.1)

        device_type = detect_device_type(initial_output)
        print(f"[{host}] 设备类型：{device_type.upper()}")

        # 根据设备类型设置命令
        if device_type == 'cisco':
            paging_cmd = "terminal length 0\n"
            privilege_cmd = "enable\n"
            prompt_pattern = r'[>#]\s*$'
        else:
            paging_cmd = "screen-length 0 temporary\n"
            privilege_cmd = f"super {privilege_level}\n"
            prompt_pattern = r'[\<\[][\w\.-]+[\>\]]\s*$'

        chan.send(paging_cmd)
        time.sleep(0.8)
        _ = chan.recv(8192)

        if privilege_password:
            print(f"[{host}] 进入特权模式...")
            chan.send(privilege_cmd)
            time.sleep(0.6)
            chan.send(privilege_password + "\n")
            time.sleep(1.8)
            _ = chan.recv(8192)

        for cmd in commands:
            if not cmd.strip():
                continue
            print(f"[{host}] 执行: {cmd}")
            chan.send(cmd + "\n")

            output = ""
            start_time = time.time()
            while time.time() - start_time < timeout_per_cmd:
                if chan.recv_ready():
                    output += chan.recv(8192).decode('utf-8', errors='replace')
                if re.search(prompt_pattern, output[-400:], re.DOTALL | re.MULTILINE):
                    break
                time.sleep(0.08)

            time.sleep(1.0)
            while chan.recv_ready():
                output += chan.recv(8192).decode('utf-8', errors='replace')
                time.sleep(0.15)

            cleaned = clean_output(output, cmd)
            outputs[cmd] = cleaned

            print(f"[{host}] 结果：")
            print(cleaned or "[通常表示成功]")
            print("─" * 70)

        return device_type, outputs

    except Exception as e:
        print(f"[{host}] SSH 失败：{str(e)}")
        return "unknown", {}
    finally:
        if chan:
            chan.close()
        ssh.close()


# ─── Telnet 处理函数 ────────────────────────────────────────────────

def network_telnet_execute(
        host: str,
        username: str,
        password: str,
        commands: List[str],
        timeout: int = 25,
        privilege_password: Optional[str] = None,
        privilege_level: str = "3"
) -> bool:
    try:
        tn = telnetlib.Telnet(host, timeout=timeout)

        # 等待登录提示（根据实际情况可能为 login: 或 Username:）
        tn.read_until(b"Username:", timeout=timeout)
        tn.write(username.encode('ascii') + b"\r\n")

        tn.read_until(b"Password:", timeout=timeout)
        tn.write(password.encode('ascii') + b"\r\n")

        time.sleep(1.2)
        banner = tn.read_very_eager().decode('ascii', errors='ignore')

        device_type = detect_device_type(banner)
        print(f"[{host}] Telnet 设备类型：{device_type.upper()}")

        # 进入特权模式
        if privilege_password:
            if device_type == 'cisco':
                tn.write(b"enable\r\n")
                tn.read_until(b"Password:", timeout=timeout)
                tn.write(privilege_password.encode('ascii') + b"\r\n")
            else:
                tn.write(f"super {privilege_level}\r\n".encode('ascii'))
                tn.read_until(b"Password:", timeout=timeout)
                tn.write(privilege_password.encode('ascii') + b"\r\n")

            time.sleep(1.5)

        # 关闭分页
        if device_type == 'cisco':
            tn.write(b"terminal length 0\r\n")
        else:
            tn.write(b"screen-length 0 temporary\r\n")
        time.sleep(0.8)
        tn.read_very_eager()

        success = True

        for cmd in commands:
            print(f"[{host}] 执行: {cmd}")
            tn.write(cmd.encode('ascii') + b"\r\n")
            time.sleep(2.0)

            output = ""
            start = time.time()
            while time.time() - start < timeout:
                output += tn.read_very_eager().decode('ascii', errors='ignore')
                if "#" in output or ">" in output or "]" in output:
                    break
                time.sleep(0.3)

            cleaned = clean_output(output, cmd)
            print(f"[{host}] 结果：")
            print(cleaned or "[通常表示成功]")
            print("─" * 70)

            if not any(kw in cleaned.lower() for kw in ['ok', '成功', 'wrote', 'committed', 'building']):
                success = False

        tn.write(b"exit\r\n")
        tn.close()
        return success

    except Exception as e:
        print(f"[{host}] Telnet 失败：{str(e)}")
        return False


# ─── 读取 IP 列表 ────────────────────────────────────────────────

def load_ip_list(filename: str) -> List[str]:
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            ips = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
        if ips:
            print(f"从 {filename} 读取到 {len(ips)} 个设备")
        return ips
    except FileNotFoundError:
        print(f"未找到文件：{filename}，跳过")
        return []
    except Exception as e:
        print(f"读取 {filename} 失败：{e}")
        return []


# ─── 批量保存配置 ────────────────────────────────────────────────

def batch_save_config():
    print("\n" + "═"*60)

    username = input("用户名（SSH 和 Telnet 共用）：").strip()
    if not username:
        print("用户名不能为空")
        return

    password = pwinput.pwinput(prompt="密码：", mask="*")
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

    ssh_list    = load_ip_list("ip_list_ssh.txt")
    telnet_list = load_ip_list("ip_list_telnet.txt")

    total = len(ssh_list) + len(telnet_list)
    if total == 0:
        print("没有找到任何设备列表")
        return

    success_count = 0

    command_sets = {
        'cisco': ["write memory"],
        'huawei': ["save", "Y"]   # 或 ["save force"] / ["commit"] 根据实际情况调整
    }

    # 处理 SSH 设备
    if ssh_list:
        print("\n" + "═"*20 + " 处理 SSH 设备 " + "═"*20 + "\n")
        for host in ssh_list:
            print(f"\n{'─'*30} {host} {'─'*30}\n")
            try:
                # 第一步：探测设备类型
                device_type, _ = network_ssh_execute(
                    host=host,
                    username=username,
                    password=password,
                    commands=[],
                    privilege_password=privilege_password,
                    privilege_level=privilege_level
                )

                # 根据类型选择保存命令
                save_commands = command_sets.get(device_type, command_sets['cisco'])
                print(f"将执行命令：{' '.join(save_commands)}")

                # 第二步：执行保存
                _, _ = network_ssh_execute(
                    host=host,
                    username=username,
                    password=password,
                    commands=save_commands,
                    privilege_password=privilege_password,
                    privilege_level=privilege_level
                )
                success_count += 1

            except Exception as e:
                print(f"[{host}] 操作异常：{e}")

    # 处理 Telnet 设备（目前假设都是 Cisco 老设备）
    if telnet_list:
        print("\n" + "═"*20 + " 处理 Telnet 设备 " + "═"*20 + "\n")
        for host in telnet_list:
            print(f"\n{'─'*30} {host} {'─'*30}\n")
            ok = network_telnet_execute(
                host=host,
                username=username,
                password=password,
                commands=["write memory"],  # Telnet 部分暂固定为 Cisco
                privilege_password=privilege_password,
                privilege_level=privilege_level
            )
            if ok:
                success_count += 1

    print("\n" + "═"*60)
    print(f"所有保存操作完成    成功：{success_count} / 总计：{total}")


# ─── 主菜单 ────────────────────────────────────────────────

def show_menu():
    print("\n" + "═"*60)
    print("      我的网络工具箱 1.1   (SSH + Telnet)  修正版")
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