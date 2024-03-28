__ver__=[2]
__version__='.'.join([str(_) for _ in __ver__])
del __ver__
from sys import exit
from platform import system as platform_system
from flask import Flask,Response
from cv2 import __version__ as cv2___version__,error as cv2_error,imread,getTextSize,putText,imwrite,cvtColor,imshow,waitKey,destroyWindow,imencode,COLOR_BGR2GRAY,FONT_HERSHEY_SIMPLEX,IMWRITE_JPEG_QUALITY
# import pypylon._pylon,pypylon._genicam #comment this line when compiling for linux, uncomment when compiling for windows
# import pypylon.pylon as pylon
from pypylon.pylon import __version__ as pylon___version__,TlFactory,InstantCamera,GrabStrategy_LatestImageOnly,TimeoutHandling_ThrowException,TimeoutException
from gevent.pywsgi import WSGIServer
from gevent import sleep as gevent_sleep,joinall,spawn as gevent_spawn
from psutil import net_if_stats
from time import sleep as time_sleep,time
from threading import Thread,Event
from get_ip import get_ip_linux,get_ip_windows
from configparser import ConfigParser
from sys import exit
ljust_space=16
__copyright__='Copyright© 2023-2024 Delloyd'
print(f'{__copyright__}\n\n{"Version".ljust(ljust_space)}: {__version__}\n{"OpenCV version".ljust(ljust_space)}: {cv2___version__}\n{"pypylon version".ljust(ljust_space)}: {pylon___version__}')
app=Flask(__name__)
config=ConfigParser()
config.read('config.ini')
show_img=True if config['DEFAULT']['show_image_locally']=='1' else False
img_quality=int(config['DEFAULT']['image_quality'])
colored=True if config['DEFAULT']['colored_image']=='1' else False
put_fps=True if config['DEFAULT']['put_fps']=='1' else False
camera_init_timeout=float(config['DEFAULT']['camera_initialization_timeout'])
check_cable_interval=int(config['DEFAULT']['check_cable_interval'])
net_interface=config['DEFAULT']['network_interface']
gain_auto=config['DEFAULT']['gain_auto']
exposure_auto=config['DEFAULT']['exposure_auto']
exposure_time=float(config['DEFAULT']['exposure_time'])
img_width=int(config['DEFAULT']['image_width'])
img_height=int(config['DEFAULT']['image_height'])
port=int(config['DEFAULT']['port'])
del ConfigParser,config,ljust_space
image=None
camera=None
master_loop=Event()
sys_platform=platform_system().lower()
CAMERA_USB_DISCONNECTED='Camera USB disconnected'
class CameraUSBDisconnectedError(Exception):
    def __init__(self):
        self.msg='Camera is disconnected'
        super().__init__(self.msg)
try:
    standby=imread('standby.jpg')
    if standby is None:
        raise FileNotFoundError('standby.jpg not found. Creating new one')
except FileNotFoundError as e:
    print(e)
    import numpy as np
    standby=np.zeros((img_height,img_width,3 if colored else 1),dtype=np.uint8)
    font,scale,thickness=FONT_HERSHEY_SIMPLEX,3,3
    text_size=getTextSize(CAMERA_USB_DISCONNECTED,FONT_HERSHEY_SIMPLEX,scale,thickness)[0]
    text_x=(img_width-text_size[0])//2
    text_y=(img_height+text_size[1])//2
    putText(standby,CAMERA_USB_DISCONNECTED,(text_x,text_y),FONT_HERSHEY_SIMPLEX,scale,(255,255,255),thickness)
    imwrite('standby.jpg',standby)
    del np,font,scale,thickness,text_size,text_x,text_y
else:
    standby=standby if colored else cvtColor(standby,COLOR_BGR2GRAY)
if net_interface.lower()=='localhost':
    ip='localhost'
elif net_interface.lower()!='localhost' and sys_platform=='linux':
    ip=get_ip_linux(net_interface)
elif net_interface.lower()!='localhost' and sys_platform=='windows':
    ip=get_ip_windows(net_interface)
del sys_platform,platform_system,get_ip_windows,get_ip_linux

def camera_init():
    def __camera_init():
        global camera
        try:
            tlf=TlFactory.GetInstance()
            devices=tlf.EnumerateDevices()
            if len(devices)==0:
                raise CameraUSBDisconnectedError
            camera=InstantCamera(tlf.CreateDevice(devices[0]))
            #camera=InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
            camera.Open()
        except CameraUSBDisconnectedError as e:
            print(f'{e}: Failed to access camera')
            return False
        else:
            print(f'{"Camera model".ljust(ljust_space)}: {camera.GetDeviceInfo().GetModelName()}')
            camera.PixelFormat.Value='BGR8' if colored else 'Mono8' #BGR8 for color, Mono8 for gray
            camera.GainAuto.SetValue(gain_auto)
            camera.ExposureAuto.SetValue(exposure_auto)
            if exposure_auto=='Off':
                camera.ExposureTime.SetValue(exposure_time)
            camera.Width.SetValue(img_width)
            camera.Height.SetValue(img_height)
            # camera.OutputQueueSize.Value=50
            # camera.StartGrabbing(pylon.GrabStrategy_LatestImages)
            camera.StartGrabbing(GrabStrategy_LatestImageOnly)
            print('Camera initialization successful')
            del tlf,devices
            return True
    if __camera_init():
        time_sleep(1.5)
        return
    start=time()
    while True:
        if time()-start>=camera_init_timeout:
            print('Retrying to initialize camera')
            if __camera_init():
                return
            else:
                start=time()
                continue
# def _camera_init_child()->bool:
#     global camera
#     try:
#         tlf=TlFactory.GetInstance()
#         devices=tlf.EnumerateDevices()
#         if len(devices)==0:
#             raise CameraUSBDisconnectedError
#         camera=InstantCamera(tlf.CreateDevice(devices[0]))
#         #camera=InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
#         camera.Open()
#     except CameraUSBDisconnectedError as e:
#         print(f'{e}: Failed to access camera')
#         return False
#     else:
#         print(f'{"Camera model".ljust(ljust_space)}: {camera.GetDeviceInfo().GetModelName()}')
#         camera.PixelFormat.Value='BGR8' if colored else 'Mono8' #BGR8 for color, Mono8 for gray
#         camera.GainAuto.SetValue(gain_auto)
#         camera.ExposureAuto.SetValue(exposure_auto)
#         if exposure_auto=='Off':
#             camera.ExposureTime.SetValue(exposure_time)
#         camera.Width.SetValue(img_width)
#         camera.Height.SetValue(img_height)
#         # camera.OutputQueueSize.Value=50
#         # camera.StartGrabbing(pylon.GrabStrategy_LatestImages)
#         camera.StartGrabbing(GrabStrategy_LatestImageOnly)
#         print('Camera initialization successful')
#         del tlf,devices
#         return True

def close_cam():
    camera.StopGrabbing()
    camera.Close()

def disp_img():
    winname=f'{ip}:{port}/stream'
    while master_loop.is_set():
        try:
            imshow(winname,image)
        except cv2_error as e:
            print(e)
            pass
        else:
            waitKey(1)
    destroyWindow(winname)
# def _usb_disconn_routine():
#     global put_fps,image
#     put_fps_temp=None
#     if put_fps:
#         put_fps_temp=True
#         put_fps=False
#     image=standby
#     #print('Trying to reinitialize camera...')
#     close_cam()
#     camera_init()
#     if put_fps_temp is not None and put_fps_temp:
#         put_fps=True
def run_cam():
    def __usb_disconn_routine():
        global put_fps,image
        put_fps_temp=None
        if put_fps:
            put_fps_temp=True
            put_fps=False
        image=standby
        #print('Trying to reinitialize camera...')
        close_cam()
        camera_init()
        if put_fps_temp is not None and put_fps_temp:
            put_fps=True
    global image
    frame=0
    fps=0
    grab_retry_count=0
    start=time()
    while master_loop.is_set():
        try:
            grabResult=camera.RetrieveResult(4000,TimeoutHandling_ThrowException)
        except TimeoutException:
            grab_retry_count+=1
            if grab_retry_count>=3:
                raise CameraUSBDisconnectedError()
            print('Image grab timed out')
            continue
        except CameraUSBDisconnectedError:
            __usb_disconn_routine()
        except:
            if not camera.IsGrabbing():
                __usb_disconn_routine()
        if grabResult.GrabSucceeded():
            image=grabResult.Array
            if put_fps:
                putText(image,str(fps),(10,30),FONT_HERSHEY_SIMPLEX,1,(0,255,0),2)
            frame+=1
            stop=time()
            duration=stop-start
            if duration>=1.0:
                fps=f'{frame/duration:.1f}'
                print(f'{fps} fps',end='\r')
                frame=0
                start=time()
            grabResult.Release()
    else:
        close_cam()
        print('Camera closed')

@app.route('/')
def index():
    return __copyright__

def gen():
    while master_loop.is_set():
        jpeg=imencode('.jpg',image,(int(IMWRITE_JPEG_QUALITY),img_quality))[1]
        frame=jpeg.tobytes()
        yield(b'--frame\r\n'
              b'Content-Type:image/jpeg\r\n'
              b'Content-Length: '+f"{len(frame)}".encode()+b'\r\n'
              b'\r\n'+frame+b'\r\n')
    # print(f'{gen.__name__}() ended')

@app.route('/stream')
def stream():
    return Response(gen(),mimetype='multipart/x-mixed-replace; boundary=frame')

def get_cable_status(interface_name):
    network_info=net_if_stats()
    if interface_name in network_info:
        return network_info[interface_name].isup
    else:
        return False

def check_cable_periodically(server):
    while master_loop.is_set().is_set():
        if not get_cable_status(net_interface):
            print(f'{net_interface} cable might have been unplugged. Server will be stopped')
            server.stop()
            break
        gevent_sleep(check_cable_interval)
    else:
        server.stop()
        print('Server stopped')

if __name__=='__main__':
    cam_server=WSGIServer((ip,port),app)
    camera_init()
    run_cam_thread=Thread(target=run_cam,daemon=True)
    run_cam_thread.start()
    if show_img:
        disp_img_thread=Thread(target=disp_img,daemon=True)
        disp_img_thread.start()
    print(cam_server.address)
    if net_interface.lower()=='localhost':
        cam_server_greenlet=None
        try:
            cam_server.serve_forever()
        except KeyboardInterrupt:
            master_loop.clear()
            cam_server.stop()
            run_cam_thread.join()
            if show_img:
                disp_img_thread.join()
            exit()           
    while True:
        try:
            cam_server_greenlet=gevent_spawn(cam_server.serve_forever)
            print('Server is up')
            check_cable_greenlet=gevent_spawn(check_cable_periodically,cam_server)
            joinall([cam_server_greenlet,check_cable_greenlet])
        except KeyboardInterrupt:
            master_loop.clear()
            joinall([cam_server_greenlet,check_cable_greenlet])
            run_cam_thread.join()
            if show_img:
                disp_img_thread.join()
            exit()
        print('Checking ethernet cable status')
        start=time()
        while True:
            if time()-start>=check_cable_interval:
                if get_cable_status(net_interface):
                    print(f'{net_interface} is up')
                    break
                else:
                    print(f'{net_interface} is down')
                    start=time()
