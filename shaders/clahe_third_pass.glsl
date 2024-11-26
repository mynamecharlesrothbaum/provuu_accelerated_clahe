#version 430

layout(local_size_x = 39, local_size_y = 39) in;

layout(binding = 0, r16) uniform image2D img;

layout(std430, binding = 1) buffer HistogramBuffer {
    uint histograms[];
};

const uint num_bins = 256u;

uint numTilesX = 33;
uint numTilesY = 18;

void main() {
    uint tileX = gl_WorkGroupID.x;
    uint tileY = gl_WorkGroupID.y;
    uint tileIndex = tileY * numTilesX + tileX;

    ivec2 pos = ivec2(gl_GlobalInvocationID.xy);

    uint bin = uint(imageLoad(img, pos).r * 256.0);

    float cdf_value = histograms[tileIndex * 256 + bin];
    float equalized_intensity = (cdf_value / float(histograms[tileIndex * num_bins + 255]));

    //if(gl_LocalInvocationIndex < 256){
    //    histograms[gl_LocalInvocationIndex] = histograms[255];
    //}


    imageStore(img, pos, vec4(equalized_intensity, 0.0, 0.0, 1.0));
}
