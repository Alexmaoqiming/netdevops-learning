from netmiko import ConnectHandler
import time

# 1.定义设备连接参数
device = {
    'device_type': 'cisco_ios',
    'host': '192.168.93.101',
    'username': 'sshadmin',
    'password': 'Cisco_123',
    'secret': 'ocsic',
    'port': 22,

    # 关键调整参数（解决慢响应或提示符问题）
    'global_delay_factor': 2,          # 增大延迟（从0.8改到2）
    'session_timeout': 60,             # 延长会话超时
    'fast_cli': False,                 # 关闭快速模式，常解决EVE-NG问题
}

# 2.建立连接
net_connect = ConnectHandler(**device)
print("当前提示符:", net_connect.find_prompt())

# 3.进入特权模式（enable)
net_connect.enable()
print("进入enable后提示符:", net_connect.find_prompt())

# 手动发送 configure terminal 命令
output = net_connect.send_command_timing("configure terminal")
print("configure terminal 输出:\n", output)

# 批量发送配置命令
config_commands = [
    'interface loopback 1',
    'ip address 1.1.1.1 255.255.255.255',
    'exit'
]
output = net_connect.send_config_set(config_commands)
print(output)

net_connect.save_config()