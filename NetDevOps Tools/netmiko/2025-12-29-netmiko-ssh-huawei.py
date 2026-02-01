from netmiko import ConnectHandler

sw_hw = {
    'device_type': 'huawei',
    'ip': '192.168.1.110',
    'username': 'yunwei',
    'password': 'lanfei_242'
}
# 没有try catch会引发异常
connect = ConnectHandler(**sw_hw)
# 输入特权密码
# connect.enable()
print(f'successfully connection to ' + sw_hw['ip'])

# connect.send_config_set是配置命令
# send_command是查询命令
config_command = ['int loop 1', 'ip add 3.3.3.3 255.255.255.255']
output = connect.send_config_set(config_command)

print(output)


result = connect.send_command('dis ip interface brief')
print(result)
