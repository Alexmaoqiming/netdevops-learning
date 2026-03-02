import paramiko
import time
import re
from typing import List, Dict, Optional, Tuple
import pwinput  # 需要先 pip install pwinput

"""
我的网络工具箱 1.0 - 工具1：批量远程保存交换机配置
功能：
- 从 ip_list.txt 读取设备列表
- 自动检测 Cisco / Huawei
- 登录后关闭分页
- 如需要则提升权限
- 执行保存命令：
  - Cisco: write memory  或  copy running-config startup-config
  - Huawei: save
- 显示保存结果（是否成功、提示信息等）
- 不下载配置文件到本地，只在设备上执行保存
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
    """清理输出，保留关键提示信息（如 [OK]、Building configuration... 等）"""
    # 去除 ANSI 颜色码
    raw_output = re.sub(r'\x1B\[[0-9;]*[mK]', '', raw_output)

    lines = raw_output.splitlines()
    cleaned = []
    skip_patterns = [
        sent_command,                   # 命令本身
        r'^\s*$',                       # 纯空行
        r'^[\w\.-]*[>#\[\]<]\s*$',      # 纯提示符行
    ]

    for line in lines:
        stripped = line.rstrip()
        if not stripped:
            continue
        # 保留包含 OK、Building、Configuration、成功等关键词的行
        if any(pat in stripped for pat in ['OK', 'Building configuration', 'Configuration', '成功', 'committed', '保存成功']):
            cleaned.append(stripped)
            continue
        # 跳过明显是回显或无关的
        if any(re.search(p, stripped) for p in skip_patterns):
            continue
        cleaned.append(stripped)

    result = "\n".join(cleaned).strip()
    return result if result else '[无明显反馈，可能已成功保存]'


def network_ssh_execute(
        host: str,
        username: str,
        password: str,
        commands: List[str],
        port: int = 22,
        timeout_per_cmd: float = 20.0,
        privilege_password: Optional[str] = None,
        privilege_level: str = "3"
) -> Tuple[str, Dict[str, str]]:
    """
    通用 SSH 执行器（针对保存配置优化超时和输出等待）
    """
    outputs = {}
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
            timeout=12
        )

        chan = ssh.invoke_shell(width=200, height=500)
        chan.settimeout(3.0)

        # 收集初始 banner 检测类型
        time.sleep(1.8)
        initial_output = ""
        start = time.time()
        while time.time() - start < 4.0:
            if chan.recv_ready():
                initial_output += chan.recv(8192).decode('utf-8', errors='replace')
            time.sleep(0.1)

        device_type = detect_device_type(initial_output)
        print(f"[{host}] 设备类型：{device_type.upper()}")

        # 设备参数
        if device_type == 'cisco':
            paging_cmd = "terminal length 0\n"
            privilege_cmd = "enable\n"
            prompt_pattern = r'[>#]\s*$'
        else:  # huawei
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
            time.sleep(1.2)
            _ = chan.recv(8192)

        for cmd in commands:
            cmd = cmd.strip()
            if not cmd:
                continue

            print(f"[{host}] 执行: {cmd}")
            chan.send(cmd + "\n")

            output = ""
            start_time = time.time()

            # 保存命令可能需要更长时间（如 Cisco write 时 Building configuration...）
            while time.time() - start_time < timeout_per_cmd:
                if chan.recv_ready():
                    chunk = chan.recv(8192).decode('utf-8', errors='replace')
                    output += chunk

                if re.search(prompt_pattern, output[-200:], re.MULTILINE):
                    break

                time.sleep(0.1)

            # 额外等 1-2 秒确保输出完整
            time.sleep(1.5)
            while chan.recv_ready():
                output += chan.recv(8192).decode('utf-8', errors='replace')
                time.sleep(0.2)

            cleaned = clean_output(output, cmd)
            outputs[cmd] = cleaned

            print(f"[{host}] 保存结果：")
            print(cleaned or "[无额外提示，通常表示成功]")
            print("─" * 80)

    except Exception as e:
        print(f"[{host}] 连接/执行失败：{str(e)}")
    finally:
        if 'chan' in locals():
            chan.close()
        ssh.close()

    return device_type, outputs


# ─── 主程序 ────────────────────────────────────────────────
if __name__ == '__main__':
    print("欢迎使用 我的网络工具箱 1.0")
    print("工具：批量远程保存交换机配置（write / save）")
    print("─" * 60)

    # 读取 IP 列表
    ip_list_file = "ip_list.txt"
    try:
        with open(ip_list_file, 'r', encoding='utf-8') as f:
            ip_list = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
        if not ip_list:
            print(f"{ip_list_file} 为空或无有效 IP")
            exit(1)
        print(f"发现 {len(ip_list)} 台设备：")
        for ip in ip_list:
            print(f"  - {ip}")
    except FileNotFoundError:
        print(f"未找到 {ip_list_file}，请创建并填入 IP 列表")
        exit(1)

    # 凭证输入
    print("\n" + "="*60)
    username = input("SSH 用户名（所有设备共用）：").strip()
    password = pwinput.pwinput(prompt="SSH 密码：", mask="*")

    need_priv = input("是否需要特权模式？(y/N)：").strip().lower()
    privilege_password = None
    privilege_level = "3"

    if need_priv in ('y', 'yes'):
        level = input("特权级别 (3/15，默认3)：").strip() or "3"
        privilege_level = level
        prompt_txt = "enable" if level == "3" else f"super {level}"
        privilege_password = pwinput.pwinput(prompt=f"特权密码 ({prompt_txt})：", mask="*")

    print("\n" + "="*60)
    print("开始批量保存配置...\n")

    for host in ip_list:
        print(f"\n{'='*35} {host} {'='*35}\n")

        command_sets = {
            'cisco': [
                "write memory",                     # 或用 "copy running-config startup-config"
                # 如果你的 Cisco 提示确认，可以加： "copy running-config startup-config\n\n"
            ],
            'huawei': [
                "save",                             # 大部分华为会直接保存，少数会问 Y/N
                # 如果总是问确认，可改为："save force" 或 "save\nY\n"
            ]
        }

        # 先检测类型
        try:
            device_type, _ = network_ssh_execute(
                host=host,
                username=username,
                password=password,
                commands=[],
                privilege_password=privilege_password,
                privilege_level=privilege_level
            )
        except Exception as e:
            print(f"[{host}] 检测失败，跳过：{e}")
            continue

        commands = command_sets.get(device_type, command_sets['cisco'])
        print(f"[{host}] 将执行保存命令：{commands}")

        try:
            _, results = network_ssh_execute(
                host=host,
                username=username,
                password=password,
                commands=commands,
                privilege_password=privilege_password,
                privilege_level=privilege_level
            )
            # 可在这里加成功判断逻辑，例如检查输出是否有 "OK" 或 "[OK]"
            print(f"[{host}] 保存流程完成")
        except Exception as e:
            print(f"[{host}] 保存失败：{e}")

    print("\n" + "="*60)
    print("所有设备保存操作已完成。")
    print("请登录设备验证 startup-config 是否已更新。")