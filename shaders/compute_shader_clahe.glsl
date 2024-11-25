#version 430

precision mediump float;

layout(local_size_x = 39, local_size_y = 39) in;

layout(binding = 0, r16) uniform image2D img;

const uint num_bins = 256;

shared uint histogram[num_bins];
shared uint cdf[num_bins];

uniform uint clipLimit = 1u;

uint low_bins;
uint zero_bins;

void main() {
    if(gl_LocalInvocationIndex < num_bins){
        histogram[gl_LocalInvocationIndex] = 0u;
        cdf[gl_LocalInvocationIndex] = 0u;
    }

    ivec2 pos = ivec2(gl_GlobalInvocationID.xy);
    float intensity = imageLoad(img, pos).r;

    //convert 16 bit [0, 1] float to a [0, 65535] int
    uint value = uint(pow(intensity, 0.5) * 65535.0);

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
            cdf[i] = sum;
        }
    }
    barrier();

    uint cdf_value = cdf[bin];

    float equalized_intensity = (float(cdf_value) / float(cdf[num_bins - 1]));

    imageStore(img, pos, vec4(equalized_intensity, 0.0, 0.0, 1.0));


}
