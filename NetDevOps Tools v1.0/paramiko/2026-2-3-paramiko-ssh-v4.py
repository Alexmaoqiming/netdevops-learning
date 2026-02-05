import paramiko


def ssh_cmd_password(host, port=22, user="root", password="your_pass", command="df -h"):
    try:
        # 创建 SSH 客户端
        ssh = paramiko.SSHClient()

        # 自动接受未知主机（生产环境建议改用known_hosts文件验证）
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # 连接
        ssh.connect(
            hostname=host,
            port=port,
            username=user,
            password=password,
            timeout=10,
            allow_agent=False,
            look_for_keys=False,
        )

        print(f"连接成功: {host}")

        # 执行命令
        stdin, stdout, stderr = ssh.exec_command(command)

        # 读取输出
        out = stdout.read().decode('utf-8').strip()
        err = stderr.read().decode('utf-8').strip()

        if err:
            print("错误输出：")
            print(err)
        else:
            print("命令输出：")
            print(out)

    except Exception as e:
        print(f"连接/执行失败：{e}")

    finally:
        ssh.close()


# 使用示例
if __name__ == '__main__':
    ssh_cmd_password(
        host="192.168.93.100",
        user="sshadmin",
        password="lanfei_242",
        command="show ip int brief && show version",
    )
