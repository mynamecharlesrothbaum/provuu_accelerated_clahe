import glfw
from OpenGL.GL import *
import numpy as np

# Initialize GLFW and create a window
if not glfw.init():
    raise Exception("GLFW initialization failed")

window = glfw.create_window(800, 600, "Compute Shader Example", None, None)
if not window:
    glfw.terminate()
    raise Exception("Failed to create GLFW window")

glfw.make_context_current(window)

# Vertex and Fragment Shader sources for rendering
vertex_shader_src = """
#version 330 core
layout (location = 0) in vec2 pos;
layout (location = 1) in vec2 texCoord;
out vec2 fragTexCoord;
void main() {
    fragTexCoord = texCoord;
    gl_Position = vec4(pos, 0.0, 1.0);
}
"""

fragment_shader_src = """
#version 330 core
in vec2 fragTexCoord;
out vec4 color;
uniform sampler2D renderedTexture;
void main() {
    color = texture(renderedTexture, fragTexCoord);
}
"""

# Compute Shader source
compute_shader_src = """
#version 430

layout(local_size_x = 32, local_size_y = 32) in;  // Adjust based on work group size

layout(binding = 0, rgba8) uniform image2D img_output;

void main() {
    ivec2 pixel_coords = ivec2(gl_GlobalInvocationID.xy);
    vec4 pixel = imageLoad(img_output, pixel_coords);

    // Transform the pixel, e.g., invert colors or adjust brightness
    pixel.rgb = 1.0 - pixel.rgb;

    imageStore(img_output, pixel_coords, pixel);
}
"""

# Compile shaders and link program
def compile_shader(source, shader_type):
    shader = glCreateShader(shader_type)
    glShaderSource(shader, source)
    glCompileShader(shader)
    if glGetShaderiv(shader, GL_COMPILE_STATUS) != GL_TRUE:
        raise RuntimeError(glGetShaderInfoLog(shader).decode())
    return shader

def create_render_program():
    vertex_shader = compile_shader(vertex_shader_src, GL_VERTEX_SHADER)
    fragment_shader = compile_shader(fragment_shader_src, GL_FRAGMENT_SHADER)

    program = glCreateProgram()
    glAttachShader(program, vertex_shader)
    glAttachShader(program, fragment_shader)
    glLinkProgram(program)

    if glGetProgramiv(program, GL_LINK_STATUS) != GL_TRUE:
        raise RuntimeError(glGetProgramInfoLog(program).decode())
    
    glDeleteShader(vertex_shader)
    glDeleteShader(fragment_shader)

    return program

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
    texture = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, texture)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA32F, 512, 512, 0, GL_RGBA, GL_FLOAT, None)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    return texture

# Main code
texture = create_texture()
compute_program = create_compute_program()
render_program = create_render_program()

# Bind the texture to image unit 0 for the compute shader
glBindImageTexture(0, texture, 0, GL_FALSE, 0, GL_WRITE_ONLY, GL_RGBA32F)

# Quad data for rendering
quad_vertices = np.array([
    -1.0, -1.0, 0.0, 0.0,
     1.0, -1.0, 1.0, 0.0,
     1.0,  1.0, 1.0, 1.0,
    -1.0,  1.0, 0.0, 1.0,
], dtype=np.float32)

quad_indices = np.array([0, 1, 2, 2, 3, 0], dtype=np.uint32)

# Create VAO and VBOs
vao = glGenVertexArrays(1)
vbo = glGenBuffers(1)
ebo = glGenBuffers(1)

glBindVertexArray(vao)
glBindBuffer(GL_ARRAY_BUFFER, vbo)
glBufferData(GL_ARRAY_BUFFER, quad_vertices.nbytes, quad_vertices, GL_STATIC_DRAW)

glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
glBufferData(GL_ELEMENT_ARRAY_BUFFER, quad_indices.nbytes, quad_indices, GL_STATIC_DRAW)

glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4 * quad_vertices.itemsize, ctypes.c_void_p(0))
glEnableVertexAttribArray(0)

glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4 * quad_vertices.itemsize, ctypes.c_void_p(2 * quad_vertices.itemsize))
glEnableVertexAttribArray(1)

glBindBuffer(GL_ARRAY_BUFFER, 0)
glBindVertexArray(0)

# Run the compute shader
glUseProgram(compute_program)
glDispatchCompute(32, 32, 1)  # Adjust for your texture size and work group size
glMemoryBarrier(GL_SHADER_IMAGE_ACCESS_BARRIER_BIT)

# Render loop
while not glfw.window_should_close(window):
    glClear(GL_COLOR_BUFFER_BIT)

    # Render the texture to a quad
    glUseProgram(render_program)
    glBindVertexArray(vao)
    glActiveTexture(GL_TEXTURE0)
    glBindTexture(GL_TEXTURE_2D, texture)
    glUniform1i(glGetUniformLocation(render_program, "renderedTexture"), 0)
    
    glDrawElements(GL_TRIANGLES, len(quad_indices), GL_UNSIGNED_INT, None)

    glfw.swap_buffers(window)
    glfw.poll_events()

# Cleanup
glDeleteVertexArrays(1, vao)
glDeleteBuffers(1, vbo)
glDeleteBuffers(1, ebo)
glDeleteTextures([texture])
glDeleteProgram(compute_program)
glDeleteProgram(render_program)
glfw.terminate()
