from ping3 import ping
import time
import os  # 添加 os 以检查文件路径

"""
V1.0版本：
搜索指定网段中的存活设备（ping3库），原理是发送 ICMP ping 请求并获取响应时间：
1.每个 IP 尝试 3 次 ping（间隔 0.3 秒），只要有一次成功就视为在线（取平均延迟）
2.排序结果：按 IP 数字顺序排序，便于查看
"""

network = "192.168.93"  # 根据你的网段调整
output_file = "alive.txt"

alive = []

print("扫描开始...\n")

start = time.time()

for i in range(1, 255):
    ip = f"{network}.{i}"

    # 尝试 3 次 ping，容忍偶尔丢包
    success_attempts = 0
    delays = []  # 收集成功延迟
    for attempt in range(1, 4):  # 最多尝试 3 次
        delay = ping(ip, timeout=2, unit='s')  # 超时加大到 2 秒
        if delay is not None:
            success_attempts += 1
            ms = round(delay * 1000, 1)
            delays.append(ms)
            print(f"在线 → {ip:15} {ms:5.1f}ms (第 {attempt} 次尝试)")
        time.sleep(0.3)  # 每次尝试间稍等，避免过度负载

    if success_attempts > 0:
        # 取平均延迟（或最小值，根据需要）
        avg_ms = sum(delays) / len(delays) if delays else 0
        alive.append((ip, round(avg_ms, 1)))
    else:
        # 可选：打印不通的 IP（调试用）
        # print(f"  ×  {ip}")
        pass

# 按 IP 排序
alive.sort(key=lambda x: tuple(map(int, x[0].split('.'))))

print(f"\n扫描结束，用时 {time.time() - start:.2f} 秒")
print(f"发现 {len(alive)} 个在线设备\n")

# 写入文件
with open(output_file, "w", encoding="utf-8") as f:
    f.write(f"扫描时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"在线数量：{len(alive)}\n\n")
    for ip, ms in alive:
        f.write(f"{ip}\t{ms:.1f} ms\n")

print(f"结果已保存至：{os.path.abspath(output_file)}")  # 显示完整路径，便于查找