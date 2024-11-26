/*  
clahe_third_pass.glsl
Charles Rothbaum
PROVUU

Third pass:

spawns work group of 1521 threads that access the stored bin values for each pixel in the 
image buffer, and the cdf functions for each tile in the histograms buffer. The uses
bilinear interpolation to finally compute the equalized intensity for each pixel, and writes
the equalized intensities to the image buffer.
*/

#version 430

layout(local_size_x = 39, local_size_y = 39) in;

layout(binding = 0, r16) uniform image2D img;

layout(std430, binding = 1) buffer HistogramBuffer {
    uint histograms[];
};

const uint numBins = 256u;
const uint numTilesX = 33u;
const uint numTilesY = 18u;
const uint tileWidth = 39u;
const uint tileHeight = 39u;

void main() {
    ivec2 imgSize = imageSize(img);
    ivec2 pos = ivec2(gl_GlobalInvocationID.xy);

    uint tileX = pos.x / tileWidth;
    uint tileY = pos.y / tileHeight;

    // Calculate relative position within the tile as fraction
    float fx = float(pos.x % tileWidth) / float(tileWidth);
    float fy = float(pos.y % tileHeight) / float(tileHeight);

    // interpolation weights
    float top_left_weight = (1.0 - fx) * (1.0 - fy);
    float top_right_weight = fx * (1.0 - fy);
    float bottom_left_weight = (1.0 - fx) * fy;
    float bottom_right_weight = fx * fy;

    // next-neighbor tile indices
    uint tileX1 = tileX + 1u;
    uint tileY1 = tileY + 1u;

    // tile indices for the four neighboring tiles
    uint tile_idx_top_left = tileY * numTilesX + tileX;
    uint tile_idx_top_right = tileY * numTilesX + tileX1;
    uint tile_idx_bottom_left = tileY1 * numTilesX + tileX;
    uint tile_idx_bottom_right = tileY1 * numTilesX + tileX1;

    // retrieve saved bins for each pixel from image buffer
    uint bin = uint(imageLoad(img, pos).r * 255.0);

    // Fetch CDF value at current pixel bin for adjacent tiles
    uint cdf_top_left = histograms[tile_idx_top_left * numBins + bin];
    uint cdf_top_right = histograms[tile_idx_top_right * numBins + bin];
    uint cdf_bottom_left = histograms[tile_idx_bottom_left * numBins + bin];
    uint cdf_bottom_right = histograms[tile_idx_bottom_right * numBins + bin];

    // Fetch the total number of pixels (last CDF value) for normalization
    uint cdf_max_top_left = histograms[tile_idx_top_left * numBins + numBins - 1u];
    uint cdf_max_top_right = histograms[tile_idx_top_right * numBins + numBins - 1u];
    uint cdf_max_bottom_left = histograms[tile_idx_bottom_left * numBins + numBins - 1u];
    uint cdf_max_bottom_right = histograms[tile_idx_bottom_right * numBins + numBins - 1u];

    // Normalize CDF values to [0,1]
    float normal_cdf_top_left = float(cdf_top_left) / float(cdf_max_top_left);
    float normal_cdf_top_right = float(cdf_top_right) / float(cdf_max_top_right);
    float normal_cdf_bottom_left = float(cdf_bottom_left) / float(cdf_max_bottom_left);
    float normal_cdf_bottom_right = float(cdf_bottom_right) / float(cdf_max_bottom_right);

    // interpolation of the CDF values
    float equalized_intensity = normal_cdf_top_left * top_left_weight + normal_cdf_top_right * top_right_weight +
                                normal_cdf_bottom_left * bottom_left_weight + normal_cdf_bottom_right * bottom_right_weight;

    // Write the equalized intensity back to the image
    imageStore(img, pos, vec4(equalized_intensity, 0.0, 0.0, 1.0));
}
