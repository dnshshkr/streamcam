from flask import Flask,Response
import cv2
import pypylon.pylon as py
from gevent.pywsgi import WSGIServer
import time
import threading
import get_ip
app=Flask(__name__)
show_img=False #default is False to avoid lagging
compression_percent=80
convert_color=False
put_fps=False
ip=get_ip.get_ip_linux('eth0')
#ip='192.168.0.3'
port=2608
try:
    camera=py.InstantCamera(py.TlFactory.GetInstance().CreateFirstDevice())
    camera.Open()
except Exception as e:
    print(f'{e}: failed to access camera')
    exit(0)
else:
    #camera.PixelFormat='RGB8'
    camera.GainAuto.SetValue('Continuous')
    camera.ExposureAuto.SetValue('Off')
    camera.ExposureTime.SetValue(16600.0) #16600.0 for 60fps
    camera.Width.SetValue(1920)
    camera.Height.SetValue(1080)
    # camera.OutputQueueSize.Value=50
    # camera.StartGrabbing(py.GrabStrategy_LatestImages)
    camera.StartGrabbing(py.GrabStrategy_LatestImageOnly)
# converter=py.ImageFormatConverter()
# converter.OutputPixelFormat=py.PixelType_BGR8packed
# converter.OutputBitAlignment=py.OutputBitAlignment_MsbAligned
image=None
fps=None
def disp_img():
    time.sleep(1)
    while show_img:
        cv2.putText(image,str(fps),(10,30),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,0),2)
        cv2.imshow(f'{ip}:{port}/stream',image)
        cv2.waitKey(1)
def run_cam():
    global image,fps
    frame=0
    fps=0
    start=time.time()
    while camera.IsGrabbing():
        try:
            grabResult=camera.RetrieveResult(5000,py.TimeoutHandling_ThrowException)
        except:
            continue
        if grabResult.GrabSucceeded():
            image=cv2.cvtColor(grabResult.Array,cv2.COLOR_RGB2BGR) if convert_color else grabResult.Array
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
    camera.StopGrabbing()
    camera.Close()
@app.route('/')
def index():
    return 'Basler'
def gen():
    while camera.IsGrabbing():
        # frame_count=0
        # fps=0
        # start=time.time()
        # grabResult=camera.RetrieveResult(5000,py.TimeoutHandling_ThrowException)
        # if grabResult.GrabSucceeded():
        #     #image=cv2.cvtColor(grabResult.Array,cv2.COLOR_RGB2BGR)
        #     image=grabResult.Array
        #     frame_count+=1
        #     stop=time.time()
        #     duration=stop-start
        #     if duration>=1.0:
        #         fps=f'{frame_count/duration:.1f}'
        #         frame_count=0
        #         start=time.time()
        #     cv2.putText(image,str(fps),(10,30),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,0),2)
        #     if show_img:
        #         cv2.imshow('frame',image)
        #         cv2.waitKey(1)
        # grabResult.Release()
        jpeg=cv2.imencode('.jpg',image,[int(cv2.IMWRITE_JPEG_QUALITY),compression_percent])[1]
        frame=jpeg.tobytes()
        yield(b'--frame\r\n'
                b'Content-Type:image/jpeg\r\n'
                b'Content-Length: '+f"{len(frame)}".encode()+b'\r\n'
                b'\r\n'+frame+b'\r\n')
        #grabResult.Release()


        # grabResult=camera.RetrieveResult(4000,py.TimeoutHandling_ThrowException)
        # if grabResult.GrabSucceeded():
        #     #image=converter.Convert(grabResult).GetArray()
        #     image=grabResult.Array
        #     jpeg=cv2.imencode('.jpg',image)[1]
        #     cv2.putText(jpeg,str(int(1/(time.time()-start))),(10,30),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,0),2)
        #     cv2.imshow('frame',jpeg)
        #     frame=jpeg.tobytes()
        #     yield(b'--frame\r\n'
        #           b'Content-Type:image/jpeg\r\n'
        #           b'Content-Length: '+f"{len(frame)}".encode()+b'\r\n'
        #           b'\r\n'+frame+b'\r\n')
        # grabResult.Release()
        # start=time.time()

        # if grabResult.GrabSucceeded(): #without cv2
        #     frame=grabResult.Array
        #     frame=frame.tobytes()
        #     yield(b'--frame\r\n'
        #           b'Content-Type:image/jpeg'
        #           b'\r\n'+frame+b'\r\n')
        # grabResult.Release()
@app.route('/stream')
def stream():
    return Response(gen(),mimetype='multipart/x-mixed-replace; boundary=frame')
if __name__=='__main__':
    threading.Thread(target=run_cam,daemon=True).start()
    if show_img:
        threading.Thread(target=disp_img,daemon=True).start()
    http_server=WSGIServer((ip,port),app)
    #http_server=WSGIServer((socket.gethostbyname(socket.gethostname()),2608),app)
    #http_server=WSGIServer(('192.168.0.1',2608),app)
    print(http_server.address)
    http_server.serve_forever()

    #app.run(host='0.0.0.0',port=2608,threaded=True)
