from __future__ import annotations

import re
import signal
import subprocess


def expand_capacity(dut) -> None:
    dut.run_device_shell("logcat -G 40m")
    dut.run_device_shell("renice -n -50 `pidof logd`")


def clear(dut) -> None:
    dut.adb_call("logcat", "-b", "all", "-c")


def save(dut, filepath, *, tag=""):
    target_path = dut.logdir + "/" + filepath
    logcat_file = open(target_path, "w")
    base_cmd = dut.adb_command("shell logcat -v time", tag)
    if tag and ("grep -E" not in tag) and ("all" not in tag):
        tag = f"-s {tag}"
        log = dut.command_runner.popen(
            dut.adb_command("shell logcat -v time", tag).split(),
            stdout=logcat_file,
            stderr=subprocess.STDOUT,
        )
    else:
        log = dut.command_runner.popen(
            base_cmd,
            shell=True,
            stdout=logcat_file,
            stderr=subprocess.STDOUT,
        )
    return log, logcat_file


def stop_save(dut, log, filepath) -> None:
    filter_pid(dut)
    log.terminate()
    log.send_signal(signal.SIGINT)
    filepath.close()


def filter_pid(dut):
    output = dut.run_device_shell("ps -e | grep logcat")
    if "logcat" in output:
        p_logcat_pid = re.search("(.*?) logcat", output, re.M | re.I).group(1).strip().split(" ")
        if "S" in p_logcat_pid:
            for one in p_logcat_pid:
                if re.findall(r".*\d+", one):
                    dut.run_device_shell(f"kill -9 {one}")
                    break
    return output


def kill_pid(dut) -> None:
    dut.run_device_shell("killall logcat")
