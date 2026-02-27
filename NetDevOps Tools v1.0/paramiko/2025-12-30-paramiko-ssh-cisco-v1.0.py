import paramiko
import time

"""
V1.0版本：测试最基本的的Cisco设备的SSH连接，配置一条loopback接口地址，跑通测试与真机环境
"""
# 需要在EVE-NG中提前配置好设备的账号和密码
ip = '192.168.93.100'
username = 'sshadmin'
password = 'lanfei_242'
enable_password = 'ocsic'

# 创建paramiko的SSH客户端对象
ssh_client = paramiko.SSHClient()
# 创建秘钥(标准配置）
ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
#  缺少look_for_keys和allow_agent参数或导致在ubuntu下执行弹窗
ssh_client.connect(hostname=ip, username=username, password=password, look_for_keys=False, allow_agent=False)

print("Successfully connected to " + ip)
# 唤醒shell
command = ssh_client.invoke_shell()

# 发送测试命令
command.send("enable\n")
time.sleep(1)
# enable密码
command.send(enable_password + "\n")
time.sleep(1)
# 配置一个环回接口
command.send("configure terminal\n")
command.send("int loop 1\n")
command.send("ip address 1.1.1.1 255.255.255.255\n")
time.sleep(1)
command.send("end\n")
command.send("wr mem\n")

time.sleep(1)
# 接收IOS输出并打印
output = command.recv(65535)
print(output.decode("ascii"))

ssh_client.close()