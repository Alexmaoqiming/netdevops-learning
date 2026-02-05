import paramiko
import time

from genie.libs.sdk.apis.iosxe.bfd.configure import enable_bfd_on_ospf

enable_password = "ocsic"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname='192.168.93.100', username='sshadmin', password='lanfei_242',look_for_keys=False, allow_agent=False)

print("Successfully connected")

command = ssh.invoke_shell()

command.recv(65535)

command.send(b"enable\n")
time.sleep(1)
command.send(enable_password + "\n")
time.sleep(1)
command.send("terminal length 0\n")
# command.send("conf t\n")
# time.sleep(1)
# command.send("interface loop 1\n")
# command.send("ip address 1.1.1.1 255.255.255.255\n")
# time.sleep(1)
# command.send("exit\n")
# command.send("exit\n")
# command.send("wr\n")
# time.sleep(2)
#
# command.send("show ip int brief\n")
# time.sleep(1)
command.send("show version\n")
time.sleep(1)

output = command.recv(65535)
print(output.decode('utf-8', errors='ignore'))
ssh.close()
