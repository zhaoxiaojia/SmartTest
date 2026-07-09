from __future__ import annotations

import time
import os
import signal

from tools.logging import smart_log


def screencap(dut, filepath, layer="osd", app_level=28) -> None:
    if layer == "osd":
        dut.adb_call("shell", "screencap", "-p", filepath)
        return

    png_type = 1
    if layer == "video" or layer == dut.OSD_VIDEO_LAYER:
        if app_level > 28:
            screencatch(dut, layer)
        else:
            if layer == "video":
                png_type = 0
            dut.run_device_shell("pngtest " + str(png_type))
        return

    smart_log("please check the set screen layer arg", level="info")


def screenshot(dut, destination, layer="osd", app_level=28) -> None:
    if layer == "osd":
        device_path = "/sdcard/screen.png"
        destination = dut.logdir + "/" + "screencap_" + destination + ".png"
    else:
        dirs = dut.mkdir_temp()
        if app_level > 28:
            device_path = dirs + "/1.bmp"
            destination = dut.logdir + "/" + "screencatch_" + destination + ".bmp"
        else:
            device_path = dirs + "/1.jpeg"
            destination = dut.logdir + "/" + "pngtest_" + destination + ".jpeg"
    screencap(dut, device_path, layer, app_level)
    time.sleep(2)
    dut.pull(device_path, destination)
    time.sleep(2)
    if layer == "osd":
        dut.rm("", device_path)
    else:
        dut.rm("-r", dirs)


def continuous_screenshot(dut, destination, layer="osd+video", app_level=30, screenshot_counter=3) -> None:
    dirs = dut.mkdir_temp()
    if app_level > 28 and screenshot_counter > 1 and (layer == "video" or layer == dut.OSD_VIDEO_LAYER):
        screencatch(dut, layer, screenshot_counter)
        time.sleep(5)
        for i in range(screenshot_counter):
            index = i + 1
            device_path = dirs + "/" + str(index) + ".bmp"
            smart_log(device_path, level="info")
            destination_temp = dut.logdir + "/" + "screencatch_" + destination + "_" + str(index) + ".bmp"
            dut.pull(device_path, destination_temp)
            time.sleep(2)
    else:
        smart_log("you can use screenshot cmd", level="info")
    dut.rm("-r", dirs)


def screencatch(dut, layer="osd+video", counter=1) -> None:
    capture_type = "1" if layer == dut.OSD_VIDEO_LAYER else "0"
    dut.run_shell_cmd("screencatch -m " + " -t " + capture_type + " -c " + str(counter))


def video_record(dut, destination, app_level=28, record_time=30, sleep_time=30, frame=30, bits=4000000, type=1) -> None:
    destination = dut.logdir + "/" + "video_record_" + destination + ".ts"
    dirs = dut.mkdir_temp()
    if app_level <= 28:
        video_record_process = dut.popen("shell tspacktest")
        time.sleep(sleep_time)
        os.kill(video_record_process.pid, signal.SIGTERM)
    else:
        command = "tspacktest -f " + str(frame) + " -b " + str(bits) + " -t " + str(type) + " -s " + str(record_time)
        dut.run_shell_cmd(command)
    time.sleep(2)
    dut.pull(dirs + "/video.ts", destination)
    time.sleep(5)
    dut.rm("-r", dirs)
