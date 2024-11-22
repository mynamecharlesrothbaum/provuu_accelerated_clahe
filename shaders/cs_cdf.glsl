#version 430

layout(local_size_x = 16, local_size_y = 16) in;  

layout(binding = 0, r16ui) uniform uimage2D img_frame;

shared float histogram[256];
shared uint cdf[256];

void calculate_cdf(){
    if(gl_GlobalInvocationID.x == 0 && gl_GlobalInvocationID.y==0){ //only 1 thread will perform the cdf to avoid redundancy
        uint cumulativeSum = 0;
        uint totalPixels = 0;

        for(int i =0; i < (256); i++){
            totalPixels += histogram[i];
            cumulativeSum += histogram[i];
            cdf[i] = cumulativeSum;
        }
        for(int i =0; i < (256); i++){
            cdf[i] /= totalPixels; //normalize each cumulativesum to [0,1]
        }
    }
    barrier();
}

void main() {
    ivec2 pixel_coords = ivec2(gl_GlobalInvocationID.xy);
    uint pixel = imageLoad(img_frame, pixel_coords).r;
    float intensity = float(pixel.r);

    //atomicAdd(histogram[intensity], 1); // atomic add to histogram
    //barrier(); // wait for histogram to update from all threads

   // float new_intensity = cdf[intensity];
    pixel *= 100u;

    imageStore(img_frame, pixel_coords, pixel);
}