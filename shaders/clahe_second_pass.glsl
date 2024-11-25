#version 430

layout(local_size_x = 16, local_size_y = 16) in;

layout(std430, binding = 1) buffer HistogramBuffer {
    uint histograms[];
};

const uint num_bins = 256u;
uniform uint clipLimit = 10u;
shared uint excess_values;
uint numTilesX = 33;
uint numTilesY = 19;

void main() {
    if(gl_LocalInvocationIndex == 0){
        excess_values = 0u;
    }

    uint tileX = gl_WorkGroupID.x;
    uint tileY = gl_WorkGroupID.y;
    uint tileIndex = tileY * numTilesX + tileX;
    uint num_bins_at_index = histograms[tileIndex * 256 + gl_LocalInvocationIndex];

    //clip histogram where it exceeds clipLimit
    //keep track of excess values for later.
    if(num_bins_at_index > clipLimit){
        histograms[tileIndex * 256 + gl_LocalInvocationIndex] = clipLimit;
        atomicAdd(excess_values, (num_bins_at_index - clipLimit));
    }
    
    barrier();

    //distribute clipped value excess across all bins uniformly
    atomicAdd(histograms[tileIndex * 256 + gl_LocalInvocationIndex], uint(excess_values / num_bins));
    barrier();

    compute cdf
    if (gl_LocalInvocationIndex == 0){
        uint sum = 0u;
       for(uint i = 0u; i < num_bins; i++){
            sum += histograms[tileIndex * 256 + i];
            histograms[tileIndex * 256 + i] = sum;
        }
    }
}
