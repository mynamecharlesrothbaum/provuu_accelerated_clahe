import numpy as np
import subprocess
import glfw
import OpenGL.GL as gl
from OpenGL.GL import *
import sys
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

compute_shader_file = open("shaders/compute_shader_clahe.glsl")
compute_shader_src = compute_shader_file.read()

# width and height of camera frames
w, h = 1280, 720

def start_camera_stream():
    # Start gstreamer pipeline to send frames to appsink
    Gst.init(None)
    
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

    return sink

def compile_shader(source, shader_type):
    shader = glCreateShader(shader_type)
    glShaderSource(shader, source)
    glCompileShader(shader)
    if glGetShaderiv(shader, GL_COMPILE_STATUS) != GL_TRUE:
        raise RuntimeError(glGetShaderInfoLog(shader).decode())
    return shader

def create_compute_program():
    #compile and link compute shader to program 

    compute_shader = compile_shader(compute_shader_src, GL_COMPUTE_SHADER)
    program = glCreateProgram()
    glAttachShader(program, compute_shader)
    glLinkProgram(program)

    if glGetProgramiv(program, GL_LINK_STATUS) != GL_TRUE:
        raise RuntimeError(glGetProgramInfoLog(program).decode())

    glDeleteShader(compute_shader)
    return program

def create_texture(w,h):
    #parametrize texture that will contain image data in gpu memory
    texture_id = glGenTextures(1)

    glBindTexture(GL_TEXTURE_2D, texture_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)

    # have to copy red channel to empty green and blue channel so that the r16
    # image renders as grayscale.
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_SWIZZLE_R, GL_RED)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_SWIZZLE_G, GL_RED)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_SWIZZLE_B, GL_RED)

    glBindTexture(GL_TEXTURE_2D, 0)

    return texture_id


def main():
    #initialize GLFW
    if not glfw.init():
        print("Failed to initialize GLFW")
        sys.exit(1)

    window = glfw.create_window(w, h, "pipeline test", None, None)

    if not window:
        glfw.terminate()
        print("Failed to create GLFW window")
        sys.exit(1)

    # Set context for OpenGL
    glfw.make_context_current(window)

    texture_id = create_texture(w,h)
    compute_program = create_compute_program()

    # Set the viewport
    glViewport(0, 0, w, h)

    sink = start_camera_stream()
    count = 1


    ### bind texture object at texture_id to the GL_TEXTURE_2D target. 
    # future operations on GL_TEXTURE_2D will affect this texture in memory.
    glBindTexture(GL_TEXTURE_2D, texture_id)
    # GL_R16 -> 16 bit unsigned values stored in red channel.
    glTexImage2D(GL_TEXTURE_2D, 0, GL_R16, w, h, 0, GL_RED, GL_UNSIGNED_SHORT, None) 
    glBindImageTexture(0, texture_id, 0, GL_FALSE, 0, GL_READ_WRITE, GL_R16)

    while not glfw.window_should_close(window):
        count += 1

        if (count % 9 != 0):
            continue

        # Pull camera frame and update texture
        sample = sink.emit('pull-sample')
        if sample is None:
            continue

        buffer = sample.get_buffer()
        info = buffer.extract_dup(0, buffer.get_size())

        # Update texture with new data
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_RED, GL_UNSIGNED_SHORT, info)

        ### Dispatch the compute_shader 
        # will spawn a number of 16x16 work groups which run in parallel 
        glUseProgram(compute_program)
        glDispatchCompute(round(w/39), round(h/39), 1)
        # ensure that all threads are done writing to the texture before it is rendered.
        glMemoryBarrier(GL_SHADER_IMAGE_ACCESS_BARRIER_BIT)

        ### Render to screen
        # clear data leftover from last frame
        glClear(GL_COLOR_BUFFER_BIT)
        # enable fixed-function mapping for 2D texture
        glEnable(GL_TEXTURE_2D)
        #map pixels to a full screen quad.
        glBegin(GL_QUADS)
        glTexCoord2f(0.0, 1.0); glVertex2f(-1.0, -1.0)
        glTexCoord2f(1.0, 1.0); glVertex2f(1.0, -1.0)
        glTexCoord2f(1.0, 0.0); glVertex2f(1.0, 1.0)
        glTexCoord2f(0.0, 0.0); glVertex2f(-1.0, 1.0)
        glEnd()

        # render current buffer to the screen
        glfw.swap_buffers(window)
        glfw.poll_events()

    glfw.terminate()


if __name__ == "__main__":
    main()