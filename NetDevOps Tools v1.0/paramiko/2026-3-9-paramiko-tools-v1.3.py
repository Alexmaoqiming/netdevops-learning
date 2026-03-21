import paramiko
import telnetlib
import time
import re
import sys
import ftplib
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
import pwinput

# ─── 配置映射表 ────────────────────────────────────────────────
DEVICE_CONFIG = {
    'huawei': {
        'paging': 'screen-length 0 temporary',
        'save': ['save', 'Y'],
        'backup': 'display current-configuration',
        'prompt': r'[\<\[][\w\.-]+[\>\]]\s*$'
    },
    'cisco': {
        'paging': 'terminal length 0',
        'save': ['write memory'],
        'backup': 'show running-config',
        'prompt': r'[>#]\s*$'
    }
}


# ─── 通用辅助函数 ────────────────────────────────────────────────
def detect_device_type(initial_output: str) -> str:
    lower_text = initial_output.lower()
    if any(word in lower_text for word in ['huawei', 'vrp', 'ne', 's series', '<huawei>', '[quidway]']):
        return 'huawei'
    if any(word in lower_text for word in ['cisco', 'ios', 'xe', 'catalyst', 'nexus']):
        return 'cisco'
    return 'cisco'  # 默认思科


def clean_output(raw_output: str, sent_command: str) -> str:
    # 去除 ANSI 颜色和控制符
    raw_output = re.sub(r'\x1B\[[0-9;]*[mK]', '', raw_output)
    lines = raw_output.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.rstrip()
        if not stripped or sent_command in stripped: continue
        # 过滤掉提示符行
        if re.match(r'^[\w\.-]*[>#\[\]<]\s*$', stripped): continue
        cleaned.append(stripped)
    return "\n".join(cleaned).strip()


# ─── 统一执行引擎 ────────────────────────────────────────────────
def run_task(host: str, username: str, password: str, task_mode: str,
             priv_pwd: Optional[str] = None, method: str = 'ssh') -> Optional[str]:
    """
    task_mode: 'save' 或 'backup'
    method: 'ssh' 或 'telnet'
    """
    print(f"[{host}] 正在通过 {method.upper()} 连接...")
    output_result = ""

    try:
        if method == 'ssh':
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(host, 22, username, password, timeout=10, look_for_keys=False)
            chan = client.invoke_shell(width=200, height=1000)
            time.sleep(1)
            initial = chan.recv(8192).decode('utf-8', 'ignore')
        else:
            tn = telnetlib.Telnet(host, timeout=10)
            tn.read_until(b"Username:", timeout=5)
            tn.write(username.encode('ascii') + b"\n")
            tn.read_until(b"Password:", timeout=5)
            tn.write(password.encode('ascii') + b"\n")
            time.sleep(1)
            initial = tn.read_very_eager().decode('ascii', 'ignore')

        dtype = detect_device_type(initial)
        cfg = DEVICE_CONFIG[dtype]
        print(f"[{host}] 识别为 {dtype.upper()}")

        # 内部执行函数
        def send_and_wait(cmd: str, wait_time=1.5):
            if method == 'ssh':
                chan.send(cmd + "\n")
                time.sleep(wait_time)
                res = ""
                while chan.recv_ready():
                    res += chan.recv(8192).decode('utf-8', 'ignore')
                return res
            else:
                tn.write(cmd.encode('ascii') + b"\n")
                time.sleep(wait_time)
                return tn.read_very_eager().decode('ascii', 'ignore')

        # 1. 提权 & 翻页设置
        if priv_pwd:
            p_cmd = "enable" if dtype == 'cisco' else "super 3"
            send_and_wait(p_cmd)
            send_and_wait(priv_pwd)
        send_and_wait(cfg['paging'])

        # 2. 执行具体任务
        if task_mode == 'save':
            for c in cfg['save']:
                print(f"[{host}] 执行保存: {c}")
                send_and_wait(c, wait_time=2.0)
            output_result = "SUCCESS"
        else:
            print(f"[{host}] 正在抓取配置...")
            raw_cfg = send_and_wait(cfg['backup'], wait_time=3.0)
            # 处理长文本可能未读完的情况 (针对 backup)
            if method == 'ssh':
                while not re.search(cfg['prompt'], raw_cfg, re.M):
                    if chan.recv_ready():
                        raw_cfg += chan.recv(8192).decode('utf-8', 'ignore')
                    else:
                        time.sleep(0.5)
            output_result = clean_output(raw_cfg, cfg['backup'])

        if method == 'ssh':
            client.close()
        else:
            tn.close()
        return output_result

    except Exception as e:
        print(f"[{host}] 错误: {e}")
        return None


# ─── 业务流程 ────────────────────────────────────────────────
def process_all(mode: str):
    """mode: 'save' 或 'backup'"""
    user = input("用户名: ").strip()
    pwd = pwinput.pwinput("密码: ")
    priv_pwd = pwinput.pwinput("特权密码 (如无直接回车): ") or None

    ssh_ips = load_ip_list("ip_list_ssh.txt")
    telnet_ips = load_ip_list("ip_list_telnet.txt")

    ftp_client = None
    if mode == 'backup':
        ftp_cfg = load_ftp_config()
        if not ftp_cfg: return
        try:
            ftp_client = ftplib.FTP(ftp_cfg['host'], ftp_cfg['username'], ftp_cfg['password'])
            ftp_client.cwd(ftp_cfg['directory'])
        except Exception as e:
            print(f"FTP 连接失败: {e}");
            return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 合并任务处理
    tasks = [(ip, 'ssh') for ip in ssh_ips] + [(ip, 'telnet') for ip in telnet_ips]

    for ip, method in tasks:
        print(f"\n{'-' * 50}\n处理设备: {ip}")
        result = run_task(ip, user, pwd, mode, priv_pwd, method)

        if result and mode == 'backup':
            filename = f"{ip}_{timestamp}.cfg"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(result)
            with open(filename, 'rb') as f:
                ftp_client.storbinary(f'STOR {filename}', f)
            os.remove(filename)
            print(f"[{ip}] 备份已上传至 FTP")
        elif result == "SUCCESS":
            print(f"[{ip}] 配置保存成功")

    if ftp_client: ftp_client.quit()
    print("\n任务全部完成。")


# ─── 辅助读取函数 (复用原脚本) ──────────────────────────────────
def load_ip_list(filename: str) -> List[str]:
    if not os.path.exists(filename): return []
    with open(filename, 'r', encoding='utf-8') as f:
        return [l.strip() for l in f if l.strip() and not l.strip().startswith('#')]


def load_ftp_config(filename: str = "ftp_config.txt") -> Optional[Dict]:
    if not os.path.exists(filename): return None
    config = {}
    with open(filename, 'r') as f:
        for line in f:
            if '=' in line:
                k, v = line.split('=', 1)
                config[k.strip()] = v.strip()
    return config


# ─── 主入口 ────────────────────────────────────────────────
def main():
    while True:
        print("\n=== 网络自动备份工具 2.0 ===")
        print("1. 批量保存配置 (Save)")
        print("2. 备份配置到 FTP (Backup)")
        print("0. 退出")
        choice = input("选择: ")
        if choice == '1':
            process_all('save')
        elif choice == '2':
            process_all('backup')
        elif choice == '0':
            break


if __name__ == '__main__':
    main()