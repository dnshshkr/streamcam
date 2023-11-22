def get_ip_linux(interface:str)->str:
    import socket
    import fcntl
    import struct
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    packed_iface = struct.pack('256s', interface.encode('utf_8'))
    packed_addr = fcntl.ioctl(sock.fileno(), 0x8915, packed_iface)[20:24]
    return socket.inet_ntoa(packed_addr)

def get_ip_windows(interface:str)->str:
    import psutil
    interfaces = psutil.net_if_addrs()
    return interfaces[interface][1].address

#print(get_ip_linux('eth0'))