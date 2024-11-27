# README - provuu_accelerated_clahe

**Pipeline description:**
1. GStreamer pipeline
    * Receive 1200x720 GRAY16_LE frame from camera.
    * Send frame buffers to application memory through `appsink`.
2. App loads CPU memory buffers from `appsink` into an openGL image buffer in shared memory.
3. CLAHE image is computed from three passes of openGL compute shaders:
    * First pass: `clahe_first_pass.glsl` computes the histogram of each image tile and saves the histogram to the corresponding index of a storage buffer in shared memory.
    * Second pass: `clahe_second_pass.glsl` applies clip limiting to the histogram of each file, and then computes the cumulative distribution functions (CDF) of each histogram, writing the CDFs back to the storage buffer.
    * Third pass: `clahe_third_pass.glsl` computes the equalized intensity for each pixel using the CDFs and bilinear interpolation to remove visible borders between tiles. 
4. OpenGL builtin GL_LINEAR bilinear scaling maps the processed image to the full screen dimensions.
5. Final image is rendered to the screen.

### Instructions

1. Clone the repository:
```bash
git clone https://github.com/mynamecharlesrothbaum/provuu_accelerated_clahe.git
```

2. Run the accelerated CLAHE pipeline:

```bash
python3 accelerated_clahe.py
```
