#version 430

layout(local_size_x = 39, local_size_y = 39) in;

layout(binding = 0, r16) uniform image2D img;

layout(std430, binding = 1) buffer HistogramBuffer {
    uint histograms[];
};


void main() {
  
    if (gl_LocalInvocationIndex < 255){

        histograms[gl_LocalInvocationIndex] = 6;
        
    }   
    barrier();


}
