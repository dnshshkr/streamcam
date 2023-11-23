from flask import Flask,Response
import cv2
import pypylon.pylon as py
import gevent
from gevent.pywsgi import WSGIServer
import gevent
import psutil
import time
import threading
import platform
import get_ip
import configparser
app=Flask(__name__)
config=configparser.ConfigParser()
config.read('config.ini')
show_img=True if config['DEFAULT']['show_image_locally']=='1' else False
img_quality=int(config['DEFAULT']['image_quality'])
colored=True if config['DEFAULT']['colored_image']=='1' else False
put_fps=True if config['DEFAULT']['put_fps']=='1' else False
image=None
camera=None
camera_init_timeout=float(config['DEFAULT']['camera_initialization_timeout'])
check_cable_interval=int(config['DEFAULT']['check_cable_interval'])
fps=None
sys_platform=platform.system().lower()
net_interface=config['DEFAULT']['network_interface']
gain_auto=config['DEFAULT']['gain_auto']
exposure_auto=config['DEFAULT']['exposure_auto']
exposure_time=float(config['DEFAULT']['exposure_time'])
img_width=int(config['DEFAULT']['image_width'])
img_height=int(config['DEFAULT']['image_height'])
CAMERA_USB_DISCONNECTED='Camera USB disconnected'
try:
    standby=cv2.imread('standby.jpg')
    if standby is None:
        raise FileNotFoundError('standby.jpg not found. Creating new one')
except FileNotFoundError as e:
    print(e)
    import numpy as np
    standby=np.zeros((img_height,img_width,3 if colored else 1),dtype=np.uint8)
    text_size=cv2.getTextSize(CAMERA_USB_DISCONNECTED,cv2.FONT_HERSHEY_SIMPLEX,1,2)[0]
    text_x=(img_width-text_size[0])//2
    text_y=(img_height+text_size[1])//2
    cv2.putText(standby,CAMERA_USB_DISCONNECTED,(text_x,text_y),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
    cv2.imwrite('standby.jpg',standby)
    del np,text_size,text_x,text_y
else:
    standby=standby if colored else cv2.cvtColor(standby,cv2.COLOR_BGR2GRAY)
if sys_platform=='linux':
    ip=get_ip.get_ip_linux(net_interface)
elif sys_platform=='windows':
    ip=get_ip.get_ip_windows(net_interface)
del sys_platform,platform,get_ip
port=int(config['DEFAULT']['port'])
def camera_init():
    if _camera_init_child():
        return
    start=time.time()
    while True:
        if time.time()-start>=camera_init_timeout:
            print('Retrying to initialize camera')
            if _camera_init_child():
                return
            else:
                start=time.time()
                continue
def _camera_init_child():
    global camera
    try:
        camera=py.InstantCamera(py.TlFactory.GetInstance().CreateFirstDevice())
        camera.Open()
    except Exception as e:
        print(f'{e}: Failed to access camera')
        return False
    else:
        camera.PixelFormat.Value='BGR8' if colored else 'Mono8' #BGR8 for color, Mono8 for gray
        camera.GainAuto.SetValue(gain_auto)
        camera.ExposureAuto.SetValue(exposure_auto)
        if exposure_auto!='Continuous':
            camera.ExposureTime.SetValue(exposure_time)
        camera.Width.SetValue(img_width)
        camera.Height.SetValue(img_height)
        # camera.OutputQueueSize.Value=50
        # camera.StartGrabbing(py.GrabStrategy_LatestImages)
        camera.StartGrabbing(py.GrabStrategy_LatestImageOnly)
        print('Camera initialization successful')
        return True
def close_cam():
    camera.StopGrabbing()
    camera.Close()
def disp_img():
    while show_img:
        if put_fps:
            cv2.putText(image,str(fps),(10,30),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,0),2)
        cv2.imshow(f'{ip}:{port}/stream',image)
        cv2.waitKey(1)
def run_cam():
    global image,fps
    frame=0
    fps=0
    start=time.time()
    while True:
        try:
            grabResult=camera.RetrieveResult(5000,py.TimeoutHandling_ThrowException)
        except py.TimeoutException:
            print('Image grab timed out')
            continue
        except:
            if not camera.IsGrabbing():
                global put_fps
                put_fps_temp=None
                if put_fps:
                    put_fps_temp=True
                    put_fps=False
                image=standby
                print('Camera has been disconnected. Trying to reinitialize camera...')
                camera.StopGrabbing()
                camera.Close()
                camera_init()
                if put_fps_temp is not None and put_fps_temp:
                    put_fps=True
        if grabResult.GrabSucceeded():
            image=grabResult.Array
            if put_fps:
                cv2.putText(image,str(fps),(10,30),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,0),2)
            #image=grabResult.Array
            frame+=1
            stop=time.time()
            duration=stop-start
            if duration>=1.0:
                fps=f'{frame/duration:.1f}'
                print(f'{fps} fps',end='\r')
                frame=0
                start=time.time()
            grabResult.Release()
@app.route('/')
def index():
    return 'Basler'
def gen():
    while True:
        jpeg=cv2.imencode('.jpg',image,[int(cv2.IMWRITE_JPEG_QUALITY),img_quality])[1]
        frame=jpeg.tobytes()
        yield(b'--frame\r\n'
              b'Content-Type:image/jpeg\r\n'
              b'Content-Length: '+f"{len(frame)}".encode()+b'\r\n'
              b'\r\n'+frame+b'\r\n')
@app.route('/stream')
def stream():
    return Response(gen(),mimetype='multipart/x-mixed-replace; boundary=frame')
def get_cable_status(interface_name):
    network_info=psutil.net_if_stats()
    if interface_name in network_info:
        return network_info[interface_name].isup
    else:
        return False  # If interface is not found, consider it disconnected
def check_cable_periodically(server):
    while True:
        if not get_cable_status(net_interface):
            print('Cable might have been unplugged. Server will be stopped')
            server.stop()
            break
        gevent.sleep(check_cable_interval)
if __name__=='__main__':
    cam_server=WSGIServer((ip,port),app)
    camera_init()
    time.sleep(1)
    threading.Thread(target=run_cam,daemon=True).start()
    if show_img:
        threading.Thread(target=disp_img,daemon=True).start()
    print(cam_server.address)
    #http_server.serve_forever()
    while True:
        cam_server_greenlet=gevent.spawn(cam_server.serve_forever)
        print('Server is up')
        check_cable_greenlet=gevent.spawn(check_cable_periodically,cam_server)
        gevent.joinall([cam_server_greenlet,check_cable_greenlet])
        print('Checking cable status')
        start=time.time()
        while True:
            if time.time()-start>=check_cable_interval:
                if get_cable_status(net_interface):
                    print('Cable plugged')
                    break
                else:
                    print('Cable unplugged')
                    start=time.time()
