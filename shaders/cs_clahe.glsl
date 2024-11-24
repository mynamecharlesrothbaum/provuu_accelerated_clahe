#version 450

layout(local_size_x = 39, local_size_y = 29) in;

layout(std430, binding = 1) buffer HistogramBuffer {
    uint histograms[];
};

uniform int numTilesX;

const uint histogramSize = 256;

void main(){
    // histogram buffer is a 2d array. 
    // calculate index as if every row of histogram buffer has been lined up in 1D array.
    uint tileIndex = gl_WorkGroupID.y * uint(numTilesX) + gl_WorkGroupID.x;
    uint histogramOffset = tileIndex * histogramSize;


}