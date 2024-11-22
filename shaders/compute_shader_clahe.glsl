#version 430

layout(local_size_x = 16, local_size_y = 16) in;

layout(binding = 0, r16) uniform image2D img;

shared uint histogram[256];
shared uint cdf[256];

void main() {
    ivec2 pos = ivec2(gl_GlobalInvocationID.xy);

    float pixel = imageLoad(img, pos).r;
    float intensity = pixel.r;

    //convert 16 bit [0, 1] float to a [0, 65535] int
    uint value = uint(intensity * 65535.0 + 0.5); //0.5 added for rounding

    //map the value to a histogram bin.
    uint bin = value * 255u / 65535u;

    histogram[bin] = 0u; //make sure index is empty for this work group
    barrier();

    atomicAdd(histogram[bin],1u);
    barrier();

    // compute cumulative distribution function values for every bin
    // make them accesible in cdf[bin]
    if(gl_LocalInvocationIndex == 0){
        uint sum = 0u;

        for(uint i = 0u; i < 256u; i++){
            sum += histogram[i];
            cdf[i] = sum;
        }
    }
    barrier();

    uint cdf_value = cdf[bin];

    float equalized_intensity = (float(cdf_value) / float(cdf[255]));

    imageStore(img, pos, vec4(equalized_intensity, 0.0, 0.0, 1.0));


}
