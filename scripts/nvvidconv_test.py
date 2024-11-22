import numpy as np
import subprocess
from gi.repository import Gst
import glfw
import OpenGL.GL as gl
from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader
import sys
import gi
gi.require_version('Gst', '1.0')


def main():
    Gst.init(None)

    # Camera setup
    w, h = 1280, 720

    subprocess.run(["v4l2-ctl", "-d", "/dev/video0",
                   "--set-fmt-video=width=1280,height=720"])

    pipeline = Gst.Pipeline()
    source = Gst.ElementFactory.make('v4l2src', 'camera')
    source.set_property('device', '/dev/video0')
    source.set_property('io-mode', 4)

    caps = Gst.Caps.from_string('video/x-raw, width=1280, height=720')
    caps_filter = Gst.ElementFactory.make('capsfilter', 'caps_filter')
    caps_filter.set_property('caps', caps)

    sink = Gst.ElementFactory.make('appsink', 'sink')
    sink.set_property('emit-signals', True)
    sink.set_property('sync', False)
    sink.set_property('drop', False)

    videoconvert = Gst.ElementFactory.make('videoconvert', 'videoconvert')

    nvvidconv = Gst.ElementFactory.make('nvvidconv', 'nvvidconv')
    if not nvvidconv:
        print("Error: Could not create nvvidconv element.")
        sys.exit(1)

    pipeline.add(videoconvert)
    pipeline.add(nvvidconv)

    pipeline.add(source)
    pipeline.add(caps_filter)
    pipeline.add(sink)

    source.link(caps_filter)
    caps_filter.link(videoconvert)
    
    if not videoconvert.link(nvvidconv):
        print("could not link videovonvert to nvvidconv")
        sys.exit(1)

    if not nvvidconv.link(sink):
        print("could not link nvvidconv to sink")
        sys.exit(1)

        

    pipeline.set_state(Gst.State.PLAYING)

    count = 0
    skip_count = 0

    import cv2
    while True:
        count += 1
        if count >= 15:
            break

        if count % 3 == 0:
            skip_count += 1
            continue

        # Get camera frame
        sample = sink.emit('pull-sample')
        if sample is None:
            print("Error: no sample")
            skip_count += 1
            continue
        print("frame")

    # Clean up
    pipeline.set_state(Gst.State.NULL)


if __name__ == "__main__":
    main()
