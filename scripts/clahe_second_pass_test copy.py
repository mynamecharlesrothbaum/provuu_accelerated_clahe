import numpy as np
import subprocess
import glfw
import OpenGL.GL as gl
from OpenGL.GL import *
import sys
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
import matplotlib.pyplot as plt

first_pass_compute_shader = open("shaders/clahe_first_pass.glsl")
first_pass_compute_shader_src = first_pass_compute_shader.read()

second_pass_compute_shader = open("shaders/clahe_second_pass.glsl")
second_pass_compute_shader_src = second_pass_compute_shader.read()

# width and height of camera frames
w, h = 1280, 720
numTilesX = round(w/39)
numTilesY = round(h/39)

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

def create_compute_program(compute_shader_src):
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
    np.set_printoptions(threshold=sys.maxsize)
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

    first_pass_compute_program = create_compute_program(first_pass_compute_shader_src)
    second_pass_compute_program = create_compute_program(second_pass_compute_shader_src)

    # Set the viewport
    glViewport(0, 0, w, h)

    sink = start_camera_stream()
    count = 1


    ### bind texture object at texture_id to the GL_TEXTURE_2D target. 
    # future operations on GL_TEXTURE_2D will affect this texture in memory.
    # Bind texture object
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_R16, w, h, 0, GL_RED, GL_UNSIGNED_SHORT, None)
    glBindImageTexture(0, texture_id, 0, GL_FALSE, 0, GL_READ_WRITE, GL_R16)

    # Create and allocate a shader storage buffer
    histogramBuffer = glGenBuffers(1)
    glBindBuffer(GL_SHADER_STORAGE_BUFFER, histogramBuffer)

    num_bins = 256
    num_tiles = numTilesX * numTilesY
    total_elements = num_tiles * num_bins

    totalBufferSize = 256 * num_tiles * np.dtype(np.uint32).itemsize

    assert totalBufferSize > 0

    # Allocate buffer storage
    glBufferData(GL_SHADER_STORAGE_BUFFER, totalBufferSize, None, GL_DYNAMIC_COPY)
    glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 1, histogramBuffer)

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

        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 1, histogramBuffer)

        buffer_size = glGetBufferParameteriv(GL_SHADER_STORAGE_BUFFER, GL_BUFFER_SIZE)

        ### Dispatch the compute_shader 
        # will spawn a number of 16x16 work groups which run in parallel 
        glUseProgram(first_pass_compute_program)
        glDispatchCompute(numTilesX, numTilesY, 1)
        # ensure that all threads are done writing to the texture before it is rendered.
        glMemoryBarrier(GL_SHADER_STORAGE_BARRIER_BIT | GL_SHADER_IMAGE_ACCESS_BARRIER_BIT)

        glUseProgram(second_pass_compute_program)
        glDispatchCompute(numTilesX, numTilesY, 1)
        glMemoryBarrier(GL_SHADER_STORAGE_BARRIER_BIT)

        histodata = np.zeros(totalBufferSize, dtype=np.uint8)
        glBindBuffer(GL_SHADER_STORAGE_BUFFER, histogramBuffer)
        glGetBufferSubData(GL_SHADER_STORAGE_BUFFER, 0, histodata.nbytes, histodata)
  
        histodata = histodata.view(np.uint32)
        histodata = histodata.reshape((numTilesX*numTilesY, 256))

        tile_index_to_plot = 420
        plt.bar(range(256), histodata[tile_index_to_plot])
        plt.show()

        #histodata_no_z = [x for x in histodata.view(np.uint32) if x != 0]
        #print(histodata_no_z)


        ### Render to screen
        # clear data leftover from last frame
        glClear(GL_COLOR_BUFFER_BIT)
        glEnable(GL_TEXTURE_2D)
        #glBindTexture(GL_TEXTURE_2D, texture_id)

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