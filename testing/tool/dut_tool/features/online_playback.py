from __future__ import annotations

from testing.tool.dut_tool.features.base import FeatureBase


class OnlinePlaybackFeature(FeatureBase):
    def play_exoplayer_demo_video(self, url: str = ""):
        """
        Return from the current page and launch the vendor ExoPlayer demo player.
        """
        video_url = url or self.dut.DEFAULT_EXOPLAYER_DEMO_VIDEO_URL
        command = (
            "input keyevent 4;"
            "am start -a android.intent.action.VIEW "
            f"-n {self.dut.EXOPLAYER_DEMO_COMPONENT} "
            f'-d "{video_url}"'
        )
        return self.dut.run_device_shell(command)

