#version 430

layout(local_size_x = 16, local_size_y = 16) in;

layout(std430, binding = 1) buffer HistogramBuffer {
    uint histograms[];
};

const uint num_bins = 256u;
uniform uint clipLimit = 10u;
uint numTilesX = 33;
uint numTilesY = 19;

void main() {
    uint tileX = gl_WorkGroupID.x;
    uint tileY = gl_WorkGroupID.y;
    uint tileIndex = tileY * numTilesX + tileX;

    uint num_bins_at_index = histograms[tileIndex * 256 + gl_LocalInvocationIndex];
    if(num_bins_at_index > clipLimit){
        histograms[tileIndex * 256 + gl_LocalInvocationIndex] = clipLimit;
    }
    
    barrier();

    //imageStore(img, pos, vec4(scaled_intensity, 0.0, 0.0, 1.0));
}