import cv2
import numpy as np
from datetime import datetime
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
import pycuda.driver as cuda
import pycuda.autoinit
from OpenGL.GL import *
from OpenGL.EGL import *

# EGL setup
def init_egl():
    egl_display = eglGetDisplay(EGL_DEFAULT_DISPLAY)
    eglInitialize(egl_display, None, None)
    
    egl_config_attribs = [
        EGL_SURFACE_TYPE, EGL_PBUFFER_BIT,
        EGL_RED_SIZE, 8,
        EGL_GREEN_SIZE, 8,
        EGL_BLUE_SIZE, 8,
        EGL_ALPHA_SIZE, 8,
        EGL_DEPTH_SIZE, 24,
        EGL_RENDERABLE_TYPE, EGL_OPENGL_BIT,
        EGL_NONE
    ]
    
    egl_configs = eglChooseConfig(egl_display, egl_config_attribs, 1)
    egl_context_attribs = [EGL_CONTEXT_MAJOR_VERSION, 3, EGL_NONE]
    egl_context = eglCreateContext(egl_display, egl_configs[0], EGL_NO_CONTEXT, egl_context_attribs)
    eglMakeCurrent(egl_display, EGL_NO_SURFACE, EGL_NO_SURFACE, egl_context)

    return egl_display, egl_context

# Initialize EGL
egl_display, egl_context = init_egl()

# Define image dimensions and exposure
w = 1920
h = 1200
exposure = 500

# Create OpenGL texture
texture = glGenTextures(1)
glBindTexture(GL_TEXTURE_2D, texture)
glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

# Initialize GStreamer pipeline
pipeline = Gst.Pipeline()
source = Gst.ElementFactory.make('v4l2src', 'camera')
source.set_property('device', '/dev/video0')

caps = Gst.Caps.from_string('video/x-raw, format=gray16le, width=1920, height=1200')
caps_filter = Gst.ElementFactory.make('capsfilter', 'caps')

sink = Gst.ElementFactory.make('appsink', 'sink')

pipeline.add(source)
pipeline.add(caps_filter)
pipeline.add(sink)

# Link the elements together
source.link(caps_filter)
caps_filter.link(sink)

# Define variables for image processing frames
src = cv2.cuda_GpuMat(w, h, cv2.CV_16UC1)
dst = cv2.cuda_GpuMat(w, h, cv2.CV_16UC1)
clahe = cv2.cuda.createCLAHE(clipLimit=36000, tileGridSize=(8, 8))

# Start the pipeline
pipeline.set_state(Gst.State.PLAYING)

# Set exposure
subprocess.run(["v4l2-ctl", "-d", "/dev/video0", "-c", f"exposure={exposure}"]) 
start = datetime.now()

# Main loop to process and display frames
while True:
    # Get the camera frame
    sample = sink.emit('pull-sample')
    buffer = sample.get_buffer()
    info = buffer.extract_dup(0, buffer.get_size())
    data = np.frombuffer(info, dtype=np.uint16).reshape(h, w)

    # Perform contrast enhancement using GPU
    src.upload(data)
    dst = clahe.apply(src, cv2.cuda_Stream.Null())
    processed_image = dst.download()

    # Upload the processed image to the OpenGL texture
    glBindTexture(GL_TEXTURE_2D, texture)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RED, w, h, 0, GL_RED, GL_UNSIGNED_SHORT, processed_image)

    # Clear the screen and render the texture
    glClear(GL_COLOR_BUFFER_BIT)
    glBegin(GL_QUADS)
    glTexCoord2f(0.0, 0.0)
    glVertex2f(-1.0, -1.0)
    glTexCoord2f(1.0, 0.0)
    glVertex2f(1.0, -1.0)
    glTexCoord2f(1.0, 1.0)
    glVertex2f(1.0, 1.0)
    glTexCoord2f(0.0, 1.0)
    glVertex2f(-1.0, 1.0)
    glEnd()

    # Swap OpenGL buffers to display the image
    eglSwapBuffers(egl_display, EGL_NO_SURFACE)

    # Poll for input or exit conditions (optional)
    # if any exit condition, break

# Clean up after exit
pipeline.set_state(Gst.State.NULL)
eglTerminate(egl_display)
