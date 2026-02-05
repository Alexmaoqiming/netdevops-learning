from netmiko import ConnectHandler

sw_cisco = {
    'device_type': 'cisco_ios',
    'ip': '192.168.1.41',
    'username': 'yunwei',
    'password': 'lanfei_ocsic',
    'secret': 'ocsic'
}

connect = ConnectHandler(**sw_cisco)
# 输入特权密码
connect.enable()
print(f'successfully connection to ' + sw_cisco['ip'])

# connect.send_config_set是配置命令
# send_command是查询命令
config_command = ['int loop 1', 'ip add 3.3.3.3 255.255.255.255']
output = connect.send_config_set(config_command)

print(output)

result = connect.send_command('show ip interface brief')
print(result)
