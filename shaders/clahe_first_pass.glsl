/*  
clahe_first_pass.glsl
Charles Rothbaum
PROVUU

First pass:

Spawns a work group of 1521 parallel threads that read the intensity value 
of each pixel in a 39x39 tile and compute the histogram of the tile.

Each work group saves the histogram to the corresponding index in the shared 
histograms buffer, and also saves the computed bin for each pixel in the shared
image buffer.
*/

#version 430

layout(local_size_x = 39, local_size_y = 39) in;

layout(binding = 0, r16) uniform image2D img;

layout(std430, binding = 1) buffer HistogramBuffer {
    uint histograms[];
};

const uint numBins = 256u;
uniform uint clipLimit = 10u;

uint numTilesX = 33;

void main() {
    uint tileX = gl_WorkGroupID.x;
    uint tileY = gl_WorkGroupID.y;
    uint tileIndex = tileY * numTilesX + tileX;

    ivec2 pos = ivec2(gl_GlobalInvocationID.xy);
    float intensity = imageLoad(img, pos).r; // range [0.0 - 0.015625]
    uint uint_scaled_intensity = uint(intensity  * 65535.0); // range [0 - 1023]

    uint bin = (uint_scaled_intensity * numBins) / 1024u; // range [0 - 256]

    atomicAdd(histograms[tileIndex * numBins + bin], 1u); //increment histogram for the bin.

    // store bin for each pixel so they can be retrieved in the 3rd pass.
    float float_bin = float(bin) / numBins; // have to make bin fractional so that it fits in r16 image buffer.
    imageStore(img, pos, vec4(float_bin, 0.0, 0.0, 1.0));
}
