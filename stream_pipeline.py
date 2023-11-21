import pypylon.pylon as py
import cv2
import get_ip
ip=get_ip.get_ip_linux('eth0')
fps=60
width=1920
height=1080
out = cv2.VideoWriter('appsrc ! videoconvert' + \
    ' ! video/x-raw,format=I420' + \
    ' ! x264enc speed-preset=ultrafast bitrate=600 key-int-max=' + str(fps * 2) + \
    ' ! video/x-h264,profile=baseline' + \
    f' ! rtspclientsink location=rtsp://{ip}:8554/mystream',
    cv2.CAP_GSTREAMER, 0, fps, (width, height), True)
if not out.isOpened():
    raise Exception("can't open video writer")
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
while True:
    grabResult=camera.RetrieveResult(5000,py.TimeoutHandling_ThrowException)
    if grabResult.GrabSucceeded():
        image=grabResult.Array
        out.write(image)
    grabResult.Release()