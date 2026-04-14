"""
Playback tooling is currently disabled.

The Wi-Fi test framework is being refactored around DUT polymorphism + mixins.
Playback features will be re-enabled after the core DUT APIs are stabilized.
"""

from testing.tool.playback_tool.OnlinePlayback import Online


class Youtube(Online):
    def __init__(self, *args, **kwargs):
        raise NotImplementedError("Playback tooling is disabled for now.")

