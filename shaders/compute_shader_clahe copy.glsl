#version 430

layout(local_size_x = 16, local_size_y = 16) in;

// Use 'r16' to match the texture's internal format
layout(binding = 0, r16) uniform image2D img_frame;

// Adjust histogram size as per your requirements and shared memory limits
// For demonstration, we'll use 256 bins
shared uint histogram[256];
shared uint cdf[256];

void main() {
    ivec2 pixel_coords = ivec2(gl_GlobalInvocationID.xy);
    
    // Load the pixel value (normalized between 0.0 and 1.0)
    vec4 pixel = imageLoad(img_frame, pixel_coords);
    float intensity = pixel.r;

    // Convert normalized intensity back to 16-bit unsigned integer
    uint value = uint(intensity * 65535.0 + 0.5); // Add 0.5 for rounding

    // Map the value to histogram bins (e.g., 256 bins)
    uint bin = value * 255u / 65535u;

    // Initialize histogram (only once per workgroup)
    if (gl_LocalInvocationIndex < 256) {
        histogram[gl_LocalInvocationIndex] = 0u;
    }
    barrier(); // Ensure all threads reach this point

    // Atomically increment the histogram bin
    atomicAdd(histogram[bin], 1u);
    barrier(); // Wait for all threads to finish histogram calculation

    // Compute the cumulative distribution function (CDF)
    if (gl_LocalInvocationIndex == 0) {
        uint sum = 0u;
        for (uint i = 0u; i < 256u; ++i) {
            sum += histogram[i];
            cdf[i] = sum;
        }
    }
    barrier(); // Ensure CDF is computed

    // Apply CLAHE or any desired histogram equalization technique
    // For simplicity, we'll perform histogram equalization here

    // Get the CDF value for the current bin
    uint cdf_value = cdf[bin];

    // Normalize the CDF value to [0, 1]
    float equalized_intensity = float(cdf_value) / float(cdf[255]);

    // Write the equalized intensity back to the image
    imageStore(img_frame, pixel_coords, vec4(equalized_intensity, 0.0, 0.0, 1.0));
}
