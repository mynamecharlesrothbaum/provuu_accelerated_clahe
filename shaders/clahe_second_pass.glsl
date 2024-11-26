/*  
clahe_second_pass.glsl
Charles Rothbaum
PROVUU

Second pass:

spawms 256 parallel threads to span the histograms buffer object, and compute the clip limit
for each bin in the histograms buffer, and redistributes the clipped values evenly across
the histogram.

One thread is delegated to finally compute the cdf for the histogram, overwriting the histograms
buffer with the cdf values.
*/

#version 430

layout(local_size_x = 16, local_size_y = 16) in;

layout(std430, binding = 1) buffer HistogramBuffer {
    uint histograms[];
};

const uint numBins = 256u;
uniform uint clipLimit = 40u;
uint numTilesX = 33;
uint numTilesY = 19;
shared uint excess_values;

void main() {
    if(gl_LocalInvocationIndex == 0){
        excess_values = 0u;
    }

    uint tileX = gl_WorkGroupID.x;
    uint tileY = gl_WorkGroupID.y;
    uint tileIndex = tileY * numTilesX + tileX;
    uint num_bins_at_index = histograms[tileIndex * 256 + gl_LocalInvocationIndex];

    // clip histogram where it exceeds clipLimit
    // keep track of excess values for later.
    if(num_bins_at_index > clipLimit){
        histograms[tileIndex * 256 + gl_LocalInvocationIndex] = clipLimit;
        atomicAdd(excess_values, (num_bins_at_index - clipLimit));
    }

    // distribute clipped value excess across all bins uniformly
    atomicAdd(histograms[tileIndex * 256 + gl_LocalInvocationIndex], uint(excess_values / numBins));

    barrier(); //make sure all threads are finished before thread 0 computes the cdf

    //compute cdf
    if (gl_LocalInvocationIndex == 0){
        uint sum = 0u;
        for(uint i = 0u; i < numBins; i++){
            sum += histograms[tileIndex * 256 + i];
            histograms[tileIndex * 256 + i] = sum;
        }
    }
}
