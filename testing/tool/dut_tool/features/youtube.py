from __future__ import annotations

import time
from pathlib import Path

from testing.tool.dut_tool.features.base import FeatureBase


class YoutubeFeature(FeatureBase):
    def playback(self, sleep_time: int = 60, seek: bool = False, seek_time: int = 3, video_id: str = ""):
        """
        Launch the YouTube TV app with a video and optionally keep seeking.
        """
        selected_video_id = video_id or self.dut.VIDEO_TAG_LIST[0]["link"]
        self.dut.run_device_shell(self.dut.PLAYERACTIVITY_REGU.format(selected_video_id))
        time.sleep(10)
        if seek:
            for _ in range(60 * 24):
                self.dut.keyevent(23)
                self.dut.send_event(106, seek_time)
                self.dut.keyevent(23)
                time.sleep(30)
                self.dut.keyevent(23)
                self.dut.send_event(105, seek_time)
                self.dut.keyevent(23)
                time.sleep(30)
        else:
            time.sleep(sleep_time)
        self.dut.home()
        return None

    def launch_and_search(self, query: str = "NASA", logdir: str | Path | None = None):
        """
        Launch the YouTube TV app and search for a keyword through DUT UI automation.
        """
        target_logdir = Path(logdir) if logdir else Path.cwd()
        return self.dut.ui.launch_youtube_tv_and_search(
            serial=self.dut.serialnumber,
            logdir=target_logdir,
            query=query,
        )

