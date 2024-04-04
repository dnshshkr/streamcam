__ver__=[1,0,0]
__release__='-alpha'
__version__='.'.join([str(_) for _ in __ver__])+__release__
print(__version__)
import av
from pypylon import pylon
from io import BytesIO
from PIL import Image
from flask import Flask, Response
import threading
import asyncio
import aiohttp
import signal
import socket

app = Flask(__name__)
loop = asyncio.get_event_loop()

# Connect to the Basler camera
camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
camera.Open()

# Set camera IP address and port
camera_ip = '192.168.1.201'
camera_port = 2608

# Function to check Ethernet connection asynchronously
async def check_ethernet_connection():
    while True:
        try:
            # Attempt to create a socket connection
            async with aiohttp.ClientSession() as session:
                async with session.get(f'http://{camera_ip}:{camera_port}') as resp:
                    connected = resp.status == 200
        except aiohttp.ClientConnectorError:
            connected = False
        except asyncio.CancelledError:
            break

        app.ethernet_connected = connected
        await asyncio.sleep(1)  # Check connection every second

# Function to stream video frames
async def stream_video():
    stream = BytesIO()
    with av.open(stream, 'w', format='mjpeg') as container:
        video_stream = container.add_stream('mjpeg')
        async for grabResult in camera.StreamGrabber:
            img = Image.fromarray(grabResult.Array)
            img_bytes = img.tobytes()
            frame = av.VideoFrame.from_ndarray(img_bytes, format='rgb24')
            packet = video_stream.encode(frame)
            if packet is not None:
                yield packet
            stream.seek(0)
            stream.truncate()

# Function to handle HTTP requests
@app.route('/stream')
def stream():
    if getattr(app, 'ethernet_connected', False):
        return Response(stream_video(), mimetype='multipart/x-mixed-replace; boundary=frame')
    else:
        return "Ethernet cable disconnected"

# Function to handle SIGINT signal (Ctrl+C)
def handle_exit_signal(signal, frame):
    loop.stop()
    camera.Close()

if __name__ == '__main__':
    app.ethernet_connected = False

    # Start asyncio task to check Ethernet connection
    asyncio.ensure_future(check_ethernet_connection())

    # Register signal handler for SIGINT
    signal.signal(signal.SIGINT, handle_exit_signal)

    # Start Flask app in a separate thread
    t = threading.Thread(target=app.run, kwargs={'host': '0.0.0.0', 'port': 2608, 'debug': False})
    t.daemon = True
    t.start()

    # Start asyncio event loop
    loop.run_forever()
