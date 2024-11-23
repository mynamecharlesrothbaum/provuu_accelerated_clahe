#version 430

layout(local_size_x = 39, local_size_y = 39) in;

layout(binding = 0, r16) uniform image2D img;

const uint num_bins = 256 * 2;

shared uint histogram[num_bins];
shared uint cdf[num_bins];

uniform uint clipLimit = 8u;

void main() {
    if(gl_LocalInvocationIndex < num_bins){
        histogram[gl_LocalInvocationIndex] = 0u;
        cdf[gl_LocalInvocationIndex] = 0u;
    }

    ivec2 pos = ivec2(gl_GlobalInvocationID.xy);
    float intensity = imageLoad(img, pos).r;

    //convert 16 bit [0, 1] float to a [0, 65535] int
    uint value = uint(intensity * 65535.0);

    //map the value to a histogram bin.
    uint bin = min(value * num_bins / 65535u, num_bins - 1u);

    atomicAdd(histogram[bin],1u);

    barrier();

    // compute cumulative distribution function values for every bin
    // make them accesible in cdf[bin]
    // Up-sweep (reduce) phase
    for (uint offset = 1u; offset < num_bins; offset <<= 1u) {
        uint index = (gl_LocalInvocationIndex + 1u) * offset * 2u - 1u;
        if (index < num_bins) {
            histogram[index] += histogram[index - offset];
        }
        barrier();
    }

    // Set the last element to zero
    if (gl_LocalInvocationIndex == 0) {
        histogram[num_bins - 1u] = 0u;
    }
    barrier();

    // Down-sweep phase
    for (uint offset = num_bins >> 1u; offset > 0u; offset >>= 1u) {
        uint index = (gl_LocalInvocationIndex + 1u) * offset * 2u - 1u;
        if (index < num_bins) {
            uint temp = histogram[index - offset];
            histogram[index - offset] = histogram[index];
            histogram[index] += temp;
        }
        barrier();
    }

    // Copy to CDF
    cdf[gl_LocalInvocationIndex] = histogram[gl_LocalInvocationIndex];
    barrier();


    uint cdf_value = cdf[bin];

    float equalized_intensity = (float(cdf_value) / float(cdf[num_bins - 1]));

    imageStore(img, pos, vec4(equalized_intensity, 0.0, 0.0, 1.0));


}
