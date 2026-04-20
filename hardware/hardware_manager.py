"""
硬件通信模块
"""

import time
import threading
from config import HARDWARE_CONFIG

# 尝试导入依赖
HAS_HARDWARE_SUPPORT = False
try:
    import serial
    import socket
    HAS_HARDWARE_SUPPORT = True
except ImportError:
    print("[警告] 硬件支持未启用，跳过硬件功能")

class HardwareManager:
    """硬件设备管理器"""
    
    def __init__(self):
        self.serial_port = None
        self.server_socket = None
        self.clients = []
        self.is_running = False
        self.server_thread = None
        self.serial_thread = None
        self.client_pool = []  # 客户端连接池
        self.max_pool_size = 10  # 最大连接数
        self.connection_timeout = 300  # 连接超时时间（秒）
    
    def connect_serial(self):
        """连接串口设备"""
        if not HAS_HARDWARE_SUPPORT:
            print("[警告] 硬件支持未启用，跳过串口连接")
            return False
        
        try:
            self.serial_port = serial.Serial(
                port=HARDWARE_CONFIG["serial"]["port"],
                baudrate=HARDWARE_CONFIG["serial"]["baudrate"],
                timeout=HARDWARE_CONFIG["serial"]["timeout"]
            )
            print(f"✅ 成功连接串口: {HARDWARE_CONFIG['serial']['port']}")
            return True
        except Exception as e:
            print(f"[错误] 串口连接失败: {e}")
            return False
    
    def start_server(self):
        """启动服务器"""
        if not HAS_HARDWARE_SUPPORT:
            print("[警告] 硬件支持未启用，跳过服务器启动")
            return False
        
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind((HARDWARE_CONFIG["server"]["host"], HARDWARE_CONFIG["server"]["port"]))
            self.server_socket.listen(5)
            self.is_running = True
            
            # 启动服务器线程
            self.server_thread = threading.Thread(target=self._server_loop)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            print(f"✅ 服务器已启动，监听端口: {HARDWARE_CONFIG['server']['port']}")
            return True
        except Exception as e:
            print(f"[错误] 服务器启动失败: {e}")
            return False
    
    def _server_loop(self):
        """服务器主循环"""
        while self.is_running:
            try:
                # 检查连接池大小
                if len(self.clients) >= self.max_pool_size:
                    print("[警告] 连接池已满，拒绝新连接")
                    # 临时接受并关闭连接
                    client_socket, client_address = self.server_socket.accept()
                    client_socket.sendall("连接池已满，请稍后再试\n".encode('utf-8'))
                    client_socket.close()
                    time.sleep(1)
                    continue
                
                client_socket, client_address = self.server_socket.accept()
                print(f"✅ 新客户端连接: {client_address}")
                
                # 为每个客户端创建一个处理线程
                client_thread = threading.Thread(
                    target=self._handle_client, 
                    args=(client_socket,)
                )
                client_thread.daemon = True
                client_thread.start()
            except Exception as e:
                if self.is_running:
                    print(f"[错误] 服务器错误: {e}")
                break
    
    def _handle_client(self, client_socket):
        """处理客户端连接"""
        client_info = {
            'socket': client_socket,
            'last_activity': time.time()
        }
        self.clients.append(client_info)
        
        try:
            while self.is_running:
                # 设置超时，避免阻塞
                client_socket.settimeout(1.0)
                try:
                    data = client_socket.recv(1024)
                    if not data:
                        break
                    
                    # 更新活动时间
                    client_info['last_activity'] = time.time()
                    
                    # 处理接收到的数据
                    message = data.decode('utf-8').strip()
                    print(f"📡 接收到客户端消息: {message}")
                    
                    # 处理消息并生成响应
                    response = self._process_message(message)
                    
                    # 发送响应
                    client_socket.sendall((response + '\n').encode('utf-8'))
                except socket.timeout:
                    # 检查连接是否超时
                    if time.time() - client_info['last_activity'] > self.connection_timeout:
                        print("[警告] 客户端连接超时")
                        break
                    continue
        except Exception as e:
            print(f"[错误] 客户端处理错误: {e}")
        finally:
            if client_info in self.clients:
                self.clients.remove(client_info)
            try:
                client_socket.close()
            except:
                pass
    
    def _process_message(self, message):
        """处理接收到的消息"""
        # 这里可以根据需要处理不同类型的消息
        # 例如，调用RAG系统获取答案
        
        # 示例：如果消息包含"查询"，则使用RAG系统
        if "查询" in message:
            # 提取查询内容
            query = message.replace("查询", "").strip()
            if query:
                # 延迟导入以避免循环依赖
                from core import memory, rag
                
                # 使用RAG系统处理查询
                relevant_mem = memory.search(query)
                rag_info = rag.search(query)
                
                if relevant_mem:
                    return "\n".join(relevant_mem)
                elif rag_info:
                    return rag_info
                else:
                    # 本地无相关内容，返回默认响应
                    return "本地无相关内容"
        
        # 其他类型的消息处理
        return f"已收到消息: {message}"
    
    def send_to_hardware(self, message):
        """发送消息到硬件设备"""
        if not HAS_HARDWARE_SUPPORT:
            print("[警告] 硬件支持未启用，无法发送消息")
            return False
            
        if not self.serial_port or not self.serial_port.is_open:
            print("[警告] 串口未连接，无法发送消息")
            return False
        
        try:
            self.serial_port.write((message + '\n').encode('utf-8'))
            print(f"📤 发送到硬件: {message}")
            return True
        except Exception as e:
            print(f"[错误] 发送到硬件失败: {e}")
            return False
    
    def read_from_hardware(self):
        """从硬件设备读取数据"""
        if not HAS_HARDWARE_SUPPORT:
            print("[警告] 硬件支持未启用，无法读取数据")
            return None
            
        if not self.serial_port or not self.serial_port.is_open:
            print("[警告] 串口未连接，无法读取数据")
            return None
        
        try:
            data = self.serial_port.readline().decode('utf-8').strip()
            if data:
                print(f"📥 从硬件接收: {data}")
                return data
            return None
        except Exception as e:
            print(f"[错误] 从硬件读取失败: {e}")
            return None
    
    def stop(self):
        """停止所有服务"""
        self.is_running = False
        
        # 关闭串口
        if HAS_HARDWARE_SUPPORT and self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
                print("✅ 串口已关闭")
            except Exception as e:
                print(f"[错误] 关闭串口失败: {e}")
        
        # 关闭服务器
        if HAS_HARDWARE_SUPPORT and self.server_socket:
            try:
                self.server_socket.close()
                print("✅ 服务器已关闭")
            except Exception as e:
                print(f"[错误] 关闭服务器失败: {e}")
        
        # 关闭所有客户端连接
        for client in self.clients:
            try:
                client.close()
            except:
                pass
        self.clients.clear()
        
        print("✅ 硬件管理器已停止")