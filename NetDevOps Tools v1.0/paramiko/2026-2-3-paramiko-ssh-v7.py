import paramiko
import time
import re
from typing import List, Dict, Optional
import pwinput                     # pip install pwinput

"""
2026-2-3-paramiko-ssh-v7是在v6的基础上增加了：
1.用户名和密码的用户输入，其中使用第三方库pwinput密码输入

需要注意的问题：
1.代码如果在Pycharm中运行需要编辑解释器：在控制台中模拟终端
2.或者直接在ubuntu环境下运行python：(venv) mao@maoubuntun:~$ python /home/mao/my_code/2026-2-3-paramiko-ssh-v7.py

"""
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
    使用 paramiko 連接 Cisco 設備並執行多條命令
    返回 {命令: 清理後的輸出} 的字典
    """
    outputs = {}
    ssh = paramiko.SSHClient()
    # 測試環境使用 AutoAddPolicy，生產環境應改為 RejectPolicy + known_hosts
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

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

        chan = ssh.invoke_shell(width=200, height=500)  # 加大緩衝避免截斷
        chan.settimeout(2.0)

        time.sleep(1.0)
        _ = chan.recv(8192)  # 丟棄 banner / motd

        # 關閉分頁（Cisco 必須）
        chan.send("terminal length 0\n")
        time.sleep(0.5)
        _ = chan.recv(4096)

        # 如果提供了 enable 密碼，進入特權模式
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
            print(f"發送: {cmd}")

            output = ""
            start_time = time.time()

            while time.time() - start_time < timeout_per_cmd:
                if chan.recv_ready():
                    chunk = chan.recv(8192).decode('utf-8', errors='replace')
                    output += chunk

                # 檢測是否回到提示符（# 或 > 結尾）
                if re.search(r'[>#]\s*$', output, re.MULTILINE | re.DOTALL):
                    break

                time.sleep(0.08)

            # 清理輸出
            lines = output.splitlines()
            cleaned = []
            echo_skipped = False

            for line in lines:
                stripped = line.rstrip()
                if not echo_skipped and (cmd in stripped or stripped.startswith(cmd)):
                    echo_skipped = True
                    continue
                if re.match(r'^[\w\.-]+[>#]\s*$', stripped):  # 跳過提示符行
                    continue
                if stripped:  # 去掉純空行
                    cleaned.append(stripped)

            clean_output = "\n".join(cleaned).strip()
            outputs[cmd] = clean_output

            print(f"結果 ({cmd}):\n{clean_output}\n{'─'*70}")

    except Exception as e:
        print(f"連接/執行失敗 {host}: {e}")
    finally:
        if 'chan' in locals():
            chan.close()
        ssh.close()

    return outputs


# ─── 主程式 ────────────────────────────────────────────────
if __name__ == '__main__':
    # ======================
    #   從終端安全輸入帳密
    # ======================
    HOST = "192.168.93.100"           # 可改成輸入或從環境變數讀取
    PORT = 22

    print(f"正在連線到 Cisco 設備：{HOST}:{PORT}")
    print("-" * 50)

    username = input("請輸入 SSH 用戶名: ").strip()
    if not username:
        print("用戶名不能為空")
        exit(1)

    password = pwinput.pwinput(prompt="請輸入 SSH 密碼: ", mask="*")
    if not password:
        print("密碼不能為空")
        exit(1)

    # 是否需要 enable 密碼？
    need_enable = input("是否需要進入 enable 模式？(y/N): ").strip().lower()
    enable_password = None

    if need_enable in ('y', 'yes'):
        enable_password = pwinput.pwinput(prompt="請輸入 enable 密碼: ", mask="*")
        if not enable_password:
            print("已取消 enable 密碼輸入，將以普通模式執行")
            enable_password = None

    commands = [
        "show version",
        "show ip interface brief",
        "show running-config | include hostname",
        # 你可以繼續添加其他命令
    ]

    print("\n開始執行命令...\n")

    result = cisco_ssh_execute(
        host=HOST,
        username=username,
        password=password,
        enable_password=enable_password,
        commands=commands,
        port=PORT,
    )

    print("\n全部命令執行完畢。")