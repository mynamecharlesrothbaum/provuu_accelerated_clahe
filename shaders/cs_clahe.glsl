#version 430

precision mediump float;

layout(local_size_x = 39, local_size_y = 39) in;

layout(binding = 0, r16) uniform image2D img;

layout(std430, binding = 1) buffer HistogramBuffer {
    uint histograms[];
};

const uint num_bins = 256;
const uint numTilesX = 33;
shared uint histogram[num_bins];
uniform uint clipLimit = 10u;

uint low_bins;
uint zero_bins;

void main() {


    ivec2 pos = ivec2(gl_GlobalInvocationID.xy);
    float intensity = imageLoad(img, pos).r;

    //convert 16 bit [0, 1] float to a [0, 65535] int
    uint value = uint(intensity * 65535.0 + 0.5); //0.5 added for rounding

    //map the value to a histogram bin.
    uint bin = min(value * num_bins / 65535u, num_bins - 1u);

    atomicAdd(histogram[bin],1u);

    barrier();


    // compute cumulative distribution function values for every bin
    // make them accesible in cdf[bin]
    if(gl_LocalInvocationIndex == 0){
        uint sum = 0u;

        for(uint i = 0u; i < num_bins; i++){
            if(histogram[i] > clipLimit){
                histogram[i] = clipLimit;
            }
            sum += histogram[i];
        }
    }
    barrier();


}
