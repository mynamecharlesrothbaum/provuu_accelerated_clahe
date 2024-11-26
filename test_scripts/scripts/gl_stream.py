import numpy as np
import subprocess
from gi.repository import Gst
import glfw
import OpenGL.GL as gl
from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader
import sys
import gi
gi.require_version('Gst', '1.0')


def main():
    w, h = 1280, 720

    Gst.init(None)

    #initialize GLFW
    if not glfw.init():
        print("Failed to initialize GLFW")
        sys.exit(1)

    window = glfw.create_window(w, h, "OpenGL with GLFW Test", None, None)
    if not window:
        glfw.terminate()
        print("Failed to create GLFW window")
        sys.exit(1)

    # Set context for OpenGL
    glfw.make_context_current(window)

    # Initialize OpenGL texture
    texture_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    glBindTexture(GL_TEXTURE_2D, 0)

    #create PBO
    pbo = glGenBuffers(1)
    glBindBuffer(GL_PIXEL_UNPACK_BUFFER, pbo)
    glBufferData(GL_PIXEL_UNPACK_BUFFER, w * h * 2, None,
                 GL_STREAM_DRAW)  # Assuming 16-bit grayscale data
    glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0)

    # Set the viewport
    width, height = glfw.get_framebuffer_size(window)
    glViewport(0, 0, w, h)

    # Camera setup
  

    subprocess.run([f'v4l2-ctl', '-d', '/dev/video0','--set-fmt-video=width={w},height={h}'])

    pipeline = Gst.Pipeline()
    source = Gst.ElementFactory.make('v4l2src', 'camera')
    source.set_property('device', '/dev/video0')
    source.set_property('io-mode', 4)

    caps = Gst.Caps.from_string(f'video/x-raw, width={w}, height={h}, format=GRAY16_LE')
    caps_filter = Gst.ElementFactory.make('capsfilter', 'caps_filter')
    caps_filter.set_property('caps', caps)

    sink = Gst.ElementFactory.make('appsink', 'sink')
    sink.set_property('emit-signals', True)
    sink.set_property('sync', False)
    sink.set_property('drop', False)

    pipeline.add(source)
    pipeline.add(caps_filter)
    pipeline.add(sink)

    source.link(caps_filter)
    caps_filter.link(sink)

    pipeline.set_state(Gst.State.PLAYING)

    count = 0
    skip_count = 0

    import cv2
    while not glfw.window_should_close(window):
        count += 1
       # if count >= 5000:
        #    break

        if count % 2 == 0 and count > 20:
            skip_count += 1
            continue

        # Get camera frame
        sample = sink.emit('pull-sample')
        if sample is None:
            print("Error: no sample")
            skip_count += 1
            continue

        buffer = sample.get_buffer()
        info = buffer.extract_dup(0, buffer.get_size())

        data = np.frombuffer(info, dtype=np.uint16).reshape(w, h)
        data = cv2.normalize(data, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        # cv2.imshow('frame',data)
        # cv2.waitKey(1)

        #Copy the frame data to the PBO
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, pbo)
        glBufferSubData(GL_PIXEL_UNPACK_BUFFER, 0, data.nbytes, data)

        # Bind texture and upload PBO data
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_LUMINANCE, w, h,
                     0, GL_LUMINANCE, GL_UNSIGNED_BYTE, None)

        # Clear the screen to a solid color
        glClearColor(0.2, 0.3, 0.3, 1.0)
        glClear(GL_COLOR_BUFFER_BIT)

        #write image to texture
        glEnable(GL_TEXTURE_2D)
        glBegin(GL_QUADS)
        glTexCoord2f(0.0, 1.0)
        glVertex2f(-1.0, -1.0)
        glTexCoord2f(1.0, 1.0)
        glVertex2f(1.0, -1.0)
        glTexCoord2f(1.0, 0.0)
        glVertex2f(1.0, 1.0)
        glTexCoord2f(0.0, 0.0)
        glVertex2f(-1.0, 1.0)
        glEnd()

        # Swap buffers and check for events
        glfw.swap_buffers(window)
        glfw.poll_events()

    # Clean up
    glfw.destroy_window(window)
    glfw.terminate()
    pipeline.set_state(Gst.State.NULL)


if __name__ == "__main__":
    main()