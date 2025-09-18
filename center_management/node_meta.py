import os
import requests

def get_server_ip():
    log_file = '/etc/s-box/server_ipcl.log'
    log_dir = os.path.dirname(log_file)  # 获取文件所在的目录

    # 确保目录存在
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 检查文件是否存在
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                ip = f.read().strip()  # 读取内容并去除首尾空格
            return ip
        except Exception as e:
            print(f"Error reading file: {e}")
    else:
        try:
            # 使用requests库获取公网IP地址
            response = requests.get('https://icanhazip.com', timeout=5)
            response.raise_for_status()  # 确保请求成功
            ip = response.text.strip()  # 获取IP地址并去除首尾空格
            
            # 将IP地址保存到文件中
            with open(log_file, 'w') as f:
                f.write(ip)
            
            return ip
        except requests.RequestException as e:
            print(f"Error fetching IP address: {e}")
            return None

# 调用函数
ip_address = get_server_ip()
if ip_address:
    print(f"Server IP: {ip_address}")
else:
    print("Failed to get server IP.")