"""Source Video Locator MVP — media layer (video I/O).

The media layer is the only place in the product that talks to the ffmpeg /
ffprobe binaries. Nothing above this layer (DeviceBackend / FeatureStore /
Engine / UI) is allowed to spawn a subprocess against a video, or to use
OpenCV ``CAP_PROP_POS_MSEC`` for random access (unsafe on MKV). See
``media.ffmpeg`` for the production video I/O module.
"""
