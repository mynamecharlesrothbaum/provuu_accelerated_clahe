#version 430

layout(local_size_x = 39, local_size_y = 39) in;

layout(binding = 0, r16) uniform image2D img;

layout(std430, binding = 1) buffer HistogramBuffer {
    uint histograms[];
};

const uint num_bins = 256u;
uniform uint clipLimit = 10u;

uint numTilesX = 33;

void main() {
    uint tileX = gl_WorkGroupID.x;
    uint tileY = gl_WorkGroupID.y;
    uint tileIndex = tileY * numTilesX + tileX;

    ivec2 pos = ivec2(gl_GlobalInvocationID.xy);
    float intensity = imageLoad(img, pos).r; // [0.0 - 1.0]
    float scaled_intensity = (intensity * 100); //because decimal values normalized 0-1024 get too small.
    uint uint_scaled_intensity = uint(intensity  * 65535.0); // range [0 - 1023]

    uint bin = (uint_scaled_intensity * num_bins) / 1024u;

    atomicAdd(histograms[tileIndex * 256 + bin], 1u);
  
    barrier();

    if (gl_LocalInvocationIndex < num_bins){
        uint num_bins_at_index = histograms[tileIndex * 256 + gl_LocalInvocationIndex];
        if(num_bins_at_index > clipLimit){
            histograms[tileIndex * 256 + gl_LocalInvocationIndex] = clipLimit;
        }
    }
    barrier();

    //imageStore(img, pos, vec4(scaled_intensity, 0.0, 0.0, 1.0));
}
