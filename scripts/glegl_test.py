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

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib, GObject
import OpenGL.GL as gl
from OpenGL.GL import *
import sys

def main():
    # Initialize GStreamer
    Gst.init(None)

    # Create GStreamer pipeline
    pipeline = Gst.Pipeline()

    source = Gst.ElementFactory.make('v4l2src', 'source')
    source.set_property('device', '/dev/video0')

    caps_filter = Gst.ElementFactory.make('capsfilter', 'caps_filter')
    caps_filter.set_property('caps', Gst.Caps.from_string('video/x-raw, format=GRAY16_LE, width=1280, height=720'))

    videoconvert = Gst.ElementFactory.make('videoconvert', 'videoconvert')

    vidconvert_caps_filter = Gst.ElementFactory.make('capsfilter', 'caps_filter_convert')
    vidconvert_caps_filter.set_property('caps', Gst.Caps.from_string('video/x-raw, format=RGBA'))

    nvvidconv = Gst.ElementFactory.make('nvvidconv', 'nvvidconv')
    nvegltransform = Gst.ElementFactory.make('nvegltransform', 'egltransform')
    sink = Gst.ElementFactory.make('nveglglessink', 'sink')

    if not pipeline or not source or not caps_filter or not videoconvert or not nvvidconv or not nvegltransform or not sink:
        print("Failed to create elements for the pipeline")
        sys.exit(1)

    # Add elements to pipeline
    pipeline.add(source)
    pipeline.add(caps_filter)
    pipeline.add(videoconvert)
    pipeline.add(vidconvert_caps_filter)
    pipeline.add(nvvidconv)
    pipeline.add(nvegltransform)
    pipeline.add(sink)

    # Link elements
    if not source.link(caps_filter):
        print("Error: Could not link source to caps_filter.")
        sys.exit(1)

    if not caps_filter.link(videoconvert):
        print("Error: Could not link caps_filter to videoconvert.")
        sys.exit(1)

    if not videoconvert.link(vidconvert_caps_filter):
        print("Error: Could not link videoconvert to nvvidconv.")
        sys.exit(1)

    if not vidconvert_caps_filter.link(nvvidconv):
        print("Error: Could not link videoconvert to nvvidconv.")
        sys.exit(1)

    if not nvvidconv.link(nvegltransform):
        print("Error: Could not link nvvidconv to nvegltransform.")
        sys.exit(1)

    if not nvegltransform.link(sink):
        print("Error: Could not link nvegltransform to sink.")
        sys.exit(1)

    # Set the pipeline state to playing
    pipeline.set_state(Gst.State.PLAYING)

    # Start the main loop to process the video stream
    try:
        loop = GLib.MainLoop()
        loop.run()
    except KeyboardInterrupt:
        print("Received interrupt. Shutting down...")

    # Clean up
    pipeline.set_state(Gst.State.NULL)

if __name__ == "__main__":
    main()
