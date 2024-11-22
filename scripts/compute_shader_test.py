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
compute_shader_src = """
#version 430

layout(local_size_x = 16, local_size_y = 16) in;  

layout(binding = 0, rgba16) uniform image2D img_frame;

void main() {
    ivec2 pixel_coords = ivec2(gl_GlobalInvocationID.xy);
    vec4 pixel = imageLoad(img_frame, pixel_coords);

    // Transform the pixel
    pixel.rgb = pixel.rgb * 100.0;

    imageStore(img_frame, pixel_coords, pixel);
}
    """

def compile_shader(source, shader_type):
    shader = glCreateShader(shader_type)
    glShaderSource(shader, source)
    glCompileShader(shader)
    if glGetShaderiv(shader, GL_COMPILE_STATUS) != GL_TRUE:
        raise RuntimeError(glGetShaderInfoLog(shader).decode())
    return shader

def create_compute_program():
    compute_shader = compile_shader(compute_shader_src, GL_COMPUTE_SHADER)
    program = glCreateProgram()
    glAttachShader(program, compute_shader)
    glLinkProgram(program)

    if glGetProgramiv(program, GL_LINK_STATUS) != GL_TRUE:
        raise RuntimeError(glGetProgramInfoLog(program).decode())

    glDeleteShader(compute_shader)
    return program

# Create and bind a texture
def create_texture():
    texture_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    glBindTexture(GL_TEXTURE_2D, 0)
    return texture_id


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


    texture_id = create_texture()
    glBindImageTexture(0, texture_id, 0, GL_FALSE, 0, GL_WRITE_ONLY, GL_RGBA32F)

    compute_program = create_compute_program()

    #create PBO
    pbo = glGenBuffers(1)
    glBindBuffer(GL_PIXEL_UNPACK_BUFFER, pbo)
    glBufferData(GL_PIXEL_UNPACK_BUFFER, w * h * 2, None,
                 GL_STREAM_DRAW) 
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

    count = 1
    skip_count = 0

    glUseProgram(compute_program)

    # Create texture and bind it for compute shader use
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA16, w, h, 0, GL_RGBA, GL_UNSIGNED_SHORT, None)
    glBindImageTexture(0, texture_id, 0, GL_FALSE, 0, GL_WRITE_ONLY, GL_RGBA16)

    # Run the compute shader
    glDispatchCompute(round(w/16), round(w/16), 1)
    glMemoryBarrier(GL_SHADER_IMAGE_ACCESS_BARRIER_BIT)

    #import cv2
    while not glfw.window_should_close(window):
        count += 1

        if (count % 3 == 0):
            continue

        # Pull camera frame and update texture
        sample = sink.emit('pull-sample')
        if sample is None:
            continue

        buffer = sample.get_buffer()
        info = buffer.extract_dup(0, buffer.get_size())

        # Update texture with new data
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_LUMINANCE, GL_UNSIGNED_SHORT, info)

        # Re-run compute shader to process the new texture
        glUseProgram(compute_program)
        glDispatchCompute(round(w/16), round(w/16), 1)
        glMemoryBarrier(GL_SHADER_IMAGE_ACCESS_BARRIER_BIT)

        # Render to screen
        glClear(GL_COLOR_BUFFER_BIT)
        glEnable(GL_TEXTURE_2D)
        glBegin(GL_QUADS)
        glTexCoord2f(0.0, 1.0); glVertex2f(-1.0, -1.0)
        glTexCoord2f(1.0, 1.0); glVertex2f(1.0, -1.0)
        glTexCoord2f(1.0, 0.0); glVertex2f(1.0, 1.0)
        glTexCoord2f(0.0, 0.0); glVertex2f(-1.0, 1.0)
        glEnd()

        glfw.swap_buffers(window)
        glfw.poll_events()

    glfw.terminate()


if __name__ == "__main__":
    main()