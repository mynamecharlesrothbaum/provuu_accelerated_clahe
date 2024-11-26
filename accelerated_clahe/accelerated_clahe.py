# accelerated_clahe.py
# PROVUU
#
# Pipeline:
# 1. Gstreamer sends camera image buffers to the appsink (CPU)
# 2. App loads the CPU memory buffers from the appsink in to an openGL shared memory buffer.
# 3. CLAHE image is computed from three passes of three different openGL Shader Language programs.
#   1. clahe_first_pass.glsl computes the histograms of each image tile and 
#      saves each histogram to shared memory
#   2. clahe_second_pass.glsl applies clip limiting to each histogram and then saves the cdf
#      function of each histogram to shared memory.
#   3. clahe_third_pass.glsl computes the equalized intensities of each pixel, and writes
#      them back to the original image buffer using bilinear interpolation to remove tile
#      artifacts
# 4. OpenGL builtin GL_LINEAR scaling is used to map the input image to a fullscreen image.
# 5. Final image is rendered to screen. 

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

# source files for compute shaders
first_pass_compute_shader = open("accelerated_clahe/shaders/clahe_first_pass.glsl")
first_pass_compute_shader_src = first_pass_compute_shader.read()

second_pass_compute_shader = open("accelerated_clahe/shaders/clahe_second_pass.glsl")
second_pass_compute_shader_src = second_pass_compute_shader.read()

third_pass_compute_shader = open("accelerated_clahe/shaders/clahe_third_pass.glsl")
third_pass_compute_shader_src = third_pass_compute_shader.read()


# width and height of input frames
w, h = 1280, 720

# width and height out output frames
output_w, output_h = 1920, 1080

#number of tiles for CLAHE. 
# 39x39 is the maximum openGL work group size the Nano can support.
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

    caps = Gst.Caps.from_string(f'video/x-raw, width={w}, height={h}, format=GRAY16_LE, framerate=30/1')
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

#Create image buffer that will contain the input image until it is scaled to fullscreen. 
def create_texture(w,h):
    texture_id = glGenTextures(1)

    glBindTexture(GL_TEXTURE_2D, texture_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)

    # have to tell red and blue channel to use red channel because all of
    # the pixel values are written to the red channel
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_SWIZZLE_R, GL_RED)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_SWIZZLE_G, GL_RED)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_SWIZZLE_B, GL_RED)

    glBindTexture(GL_TEXTURE_2D, 0)

    return texture_id

# create the image buffer that will contain the final scaled image to render to screen.
def create_framebuffer(output_width, output_height):
    framebuffer_texture = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, framebuffer_texture)

    glTexImage2D(GL_TEXTURE_2D, 0, GL_R16, output_width, output_height, 0, GL_RED, GL_UNSIGNED_SHORT, None)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

    framebuffer = glGenFramebuffers(1)
    glBindFramebuffer(GL_FRAMEBUFFER, framebuffer)
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, framebuffer_texture, 0)

    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_SWIZZLE_R, GL_RED)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_SWIZZLE_G, GL_RED)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_SWIZZLE_B, GL_RED)

    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    return framebuffer, framebuffer_texture


def main():
    #np.set_printoptions(threshold=sys.maxsize) # for printing full data when debugging

    #initialize GLFW
    if not glfw.init():
        print("Failed to initialize GLFW")
        sys.exit(1)

    window = glfw.create_window(output_w, output_h, "pipeline test", None, None)
    if not window:
        glfw.terminate()
        print("Failed to create GLFW window")
        sys.exit(1)

    # Set context for OpenG
    glfw.make_context_current(window)

    texture_id = create_texture(w,h)

    # compile glsl compute shader programs 
    first_pass_compute_program = create_compute_program(first_pass_compute_shader_src)
    second_pass_compute_program = create_compute_program(second_pass_compute_shader_src)
    third_pass_compute_program = create_compute_program(third_pass_compute_shader_src)

    # begin running gstreamer pipeline to send camera frame buffers to appsink.
    sink = start_camera_stream()

    # bind texture object at texture_id to the GL_TEXTURE_2D target. 
    # (future operations on GL_TEXTURE_2D will affect this texture in memory.)
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_R16, w, h, 0, GL_RED, GL_UNSIGNED_SHORT, None)
    glBindImageTexture(0, texture_id, 0, GL_FALSE, 0, GL_READ_WRITE, GL_R16)

    # create the buffer that will contain the output image
    framebuffer, framebuffer_texture = create_framebuffer(output_w, output_h)

    # Create and allocate a shader storage buffer to persistently store histograms
    # and cdf functions for each tile of frame.
    histogramBuffer = glGenBuffers(1)
    glBindBuffer(GL_SHADER_STORAGE_BUFFER, histogramBuffer)

    # calculate total buffer size
    numBins = 256
    numTiles = numTilesX * numTilesY
    totalBufferSize = numBins * numTiles * np.dtype(np.uint32).itemsize

    # Allocate memory for histograms buffer
    glBufferData(GL_SHADER_STORAGE_BUFFER, totalBufferSize, None, GL_DYNAMIC_COPY)

    while not glfw.window_should_close(window):
        # recieve input image buffer from appsink
        sample = sink.emit('pull-sample')
        if sample is None:
            continue

        buffer = sample.get_buffer()
        info = buffer.extract_dup(0, buffer.get_size())

        # Update image buffer with new data
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_RED, GL_UNSIGNED_SHORT, info)

        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 1, histogramBuffer)
        # clean histograms buffer for each new input frame.
        glClearBufferData(GL_SHADER_STORAGE_BUFFER, GL_R32UI, GL_RED_INTEGER, GL_UNSIGNED_INT, None)

        # Dispatch the compute_shaders:
        # First pass: compute histograms for each tile. 
        # (each dispatch deploys a workgroup of 1521 threads to process each image tile)
        glUseProgram(first_pass_compute_program)
        glDispatchCompute(numTilesX, numTilesY, 1)
        # ensure that all threads are done writing to the buffer before moving on.
        glMemoryBarrier(GL_SHADER_STORAGE_BARRIER_BIT)
        
        # Second pass: apply clip limiting and compute cdf on each histogram.
        # (each dispatch deploys a workgroup of 256 threads to process each tile's histogram).
        glUseProgram(second_pass_compute_program)
        glDispatchCompute(numTilesX, numTilesY, 1)
        glMemoryBarrier(GL_SHADER_STORAGE_BARRIER_BIT)
  
        # Third pass: compute equalized and interpolated pixel values, and write them back 
        # to the image buffer.
        # (each dispatch deploys a workgroup of 1521 threads to process each image tile)
        glUseProgram(third_pass_compute_program)
        glDispatchCompute(numTilesX, numTilesY, 1)
        glMemoryBarrier(GL_SHADER_IMAGE_ACCESS_BARRIER_BIT)

        ### Use this block to bring histogram buffer into cpu memory as a numpy object
        #histodata = np.zeros(totalBufferSize, dtype=np.uint8)
        #glBindBuffer(GL_SHADER_STORAGE_BUFFER, histogramBuffer)
        #glGetBufferSubData(GL_SHADER_STORAGE_BUFFER, 0, histodata.nbytes, histodata)

        ### use this block to plot histogram data after loading it into a numpy object
        #histodata = histodata.view(np.uint32)
        #histodata = histodata.reshape((numTilesX*numTilesY, 256))
        #tile_index_to_plot = 0
        #plt.bar(range(256), histodata[tile_index_to_plot])
        #plt.show()

        # Bind the framebuffer for rendering the scaled image
        glBindFramebuffer(GL_FRAMEBUFFER, framebuffer)
        glViewport(0, 0, output_w, output_h)  # Match the target 1080p resolution

        # Clear previous framebuffer content
        glClear(GL_COLOR_BUFFER_BIT)

        # Enable texturing and bind the source texture
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, texture_id)

        # Render the source texture onto a fullscreen quad
        glBegin(GL_QUADS)
        glTexCoord2f(0.0, 1.0); glVertex2f(-1.0, -1.0)
        glTexCoord2f(1.0, 1.0); glVertex2f(1.0, -1.0)
        glTexCoord2f(1.0, 0.0); glVertex2f(1.0, 1.0)
        glTexCoord2f(0.0, 0.0); glVertex2f(-1.0, 1.0)
        glEnd()

        # reset the framebuffer for screen rendering
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

        # Clear the window content
        glClear(GL_COLOR_BUFFER_BIT)

        # Bind the scaled framebuffer texture
        glBindTexture(GL_TEXTURE_2D, framebuffer_texture)

        # render the scaled texture onto the screen
        # for some reason i have to horizontally and vertically flip the texture
        glBegin(GL_QUADS)
        glTexCoord2f(-1.0, -1.0); glVertex2f(-1.0, -1.0)
        glTexCoord2f(0.0, -1.0); glVertex2f(1.0, -1.0)
        glTexCoord2f(0.0, 0.0); glVertex2f(1.0, 1.0)
        glTexCoord2f(-1.0, 0.0); glVertex2f(-1.0, 1.0)
        glEnd()


        # render current buffer to the screen
        glfw.swap_buffers(window)
        glfw.poll_events()

    glfw.terminate()


if __name__ == "__main__":
    main()