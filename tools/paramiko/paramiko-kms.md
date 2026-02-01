# Paramiko 学习笔记

## 一、用途说明
使用 Python Paramiko 模块实现对网络设备的 SSH 连接，用于学习设备交互流程。

## 二、基本连接流程
1. 连接设备 IP
2. 等待用户名提示
3. 输入用户名和密码
4. 执行命令
5. 获取输出并退出

## 三、示例代码

```python
import telnetlib

tn = telnetlib.Telnet("192.168.1.1")
tn.read_until(b"Username:")
tn.write(b"admin\n")


