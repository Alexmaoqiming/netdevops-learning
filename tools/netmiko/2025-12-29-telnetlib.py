import telnetlib
import time

HOST = "192.168.1.1"     # 设备 IP
PORT = 23               # Telnet 默认端口
USERNAME = "admin"      # 用户名
PASSWORD = "admin123"   # 密码

def telnet_connect():
    tn = telnetlib.Telnet(HOST, PORT, timeout=10)

    # 等待用户名提示
    tn.read_until(b"Username:", timeout=5)
    tn.write(USERNAME.encode("ascii") + b"\n")

    # 等待密码提示
    tn.read_until(b"Password:", timeout=5)
    tn.write(PASSWORD.encode("ascii") + b"\n")

    time.sleep(1)

    # 执行命令（示例）
    tn.write(b"display version\n")   # 华为
    # tn.write(b"show version\n")    # Cisco

    time.sleep(2)

    output = tn.read_very_eager().decode("utf-8", errors="ignore")
    print(output)

    tn.write(b"quit\n")
    tn.close()

if __name__ == "__main__":
    telnet_connect()
