#version 430

layout(local_size_x = 39, local_size_y = 39) in;

layout(binding = 0, r16) uniform image2D img;

layout(std430, binding = 1) buffer HistogramBuffer {
    uint histograms[];
};

const uint num_bins = 256;

shared uint histogram[num_bins];
shared uint cdf[num_bins];

uniform uint clipLimit = 8u;

uint numTilesX = 33;

void main() {
    uint tileX = gl_WorkGroupID.x;
    uint tileY = gl_WorkGroupID.y;
    uint tileIndex = tileY * numTilesX + tileX;

    if(gl_LocalInvocationIndex < num_bins){
        histogram[gl_LocalInvocationIndex] = 0u;
        cdf[gl_LocalInvocationIndex] = 0u;
    }

    ivec2 pos = ivec2(gl_GlobalInvocationID.xy);
    float intensity = imageLoad(img, pos).r; // [0.0 - 1.0]
    float scaled_intensity = (intensity * 100); //because decimal values normalized 0-1024 get too small.
    uint normal_intensity = uint(intensity * 65535.0); //this gets us back to 0-1024

    uint bin = (normal_intensity * num_bins) / 1024u;


    if (gl_LocalInvocationIndex < 256){
        histograms[gl_LocalInvocationIndex] = bin;
    }   

    barrier();

    imageStore(img, pos, vec4(scaled_intensity, 0.0, 0.0, 1.0));

}
