from __future__ import annotations
from dataclasses import dataclass

SELECTED_SOURCE_IDS = (4,5,10,18,20,21,29,31,32,33,49,52,53,54,55,57,58,59,60,61,62,63,64,65,66,67,68,69,95,96,97,98,114)

@dataclass(frozen=True)
class Checkpoint:
    definition_id: str
    expected: str
    pass_rule: str

@dataclass(frozen=True)
class MiddleScreenCase:
    source_id: int
    source_rows: tuple[int, ...]
    title: str
    executor: str
    steps: tuple[str, ...]
    checkpoints: tuple[Checkpoint, ...]
    parameters: tuple[str, ...] = ()
    media_sources: tuple[str, ...] = ()
    pre_actions: tuple[str, ...] = ()
    manual_boundaries: tuple[str, ...] = ()
    equipment_boundaries: tuple[str, ...] = ()
    source_file: str = "\u4e2d\u5c4f\u7528\u4f8b\u8bc4\u4f30.xlsx"
    source_sheet: str = "SmartTest\u8986\u76d6\u8bc4\u4f30"
    @property
    def source_row(self): return self.source_rows[0]
    @property
    def pytest_id(self): return f"source-{self.source_id:03d}-{self.executor.replace('_','-')}"

def _cp(i, expected): return (Checkpoint(f"iptv.{i:03d}.objective", expected, f"objective evidence: {expected}"),)
P="iptv_middle_screen:"
AV=("Playback state is objective; image quality, smoothness, artifacts and A/V sync remain manual/capture-equipment boundaries.",)
MEDIA=(P+"media_source_override",P+"playback_timeout_s")

def _case(i,row,title,executor,expected,params=(),sources=(),manual=(),equipment=(),steps=("Execute workbook action through shared capability",)):
    return MiddleScreenCase(i,(row,),title,executor,steps,_cp(i,expected),params,sources,manual_boundaries=manual,equipment_boundaries=equipment)

MIDDLE_SCREEN_CASES=(
 _case(4,5,"USB storage recognition","usb_storage","USB storage recognized",(P+"usb_match",),equipment=("Attach workbook U-disk/HDD.",)),
 _case(5,6,"HDMI connection/output evidence","hdmi_objective","connector connected and output mode active",(P+"hdmi_state_command",),manual=("TV picture and black-border judgement remain manual.",),equipment=("Connect TV/HDMI sink.",)),
 _case(10,11,"Wired Ethernet IP and speed","ethernet_speed","IP exists and speed matches configured link",(P+"interface",P+"expected_speed_mbps"),equipment=("Connect requested 100/1000 Mbps link.",)),
 _case(18,19,"CPU frequency points work and lock","cpu_frequency","every selected point locks and original is restored",("cpu_frequency:frequencies",)),
 _case(20,21,"eMMC HS400 mode","emmc_hs400","MMC evidence contains HS400"),
 _case(21,22,"Wi-Fi driver scan connect and IP","wifi","driver/interface, scan, connection and IP evidence",(P+"wifi_2g_ssid",P+"wifi_2g_password",P+"wifi_5g_ssid",P+"wifi_5g_password"),equipment=("Configured access point required.",)),
 _case(29,30,"CPU thermal node","thermal","numeric CPU temperature"),
 _case(31,32,"USB ADB connectivity","adb_transport","USB ADB ready",equipment=("Select USB ADB serial.",)),
 _case(32,33,"Network ADB connectivity","adb_transport","network ADB ready",equipment=("Select network ADB serial.",)),
 _case(33,34,"UI mode up to 1080p","wm_size","effective UI dimensions at least 1920x1080"),
 _case(49,50,"DHCP dual-stack","network","IPv4/global IPv6 and reachability",(P+"interface",P+"ipv4_ping_target",P+"ipv6_ping_target"),equipment=("Dual-stack network required.",)),
 _case(52,53,"Wired IPv4","network","IPv4 and reachability",(P+"interface",P+"ipv4_ping_target")),
 _case(53,54,"Wired IPv6","network","global IPv6 and reachability",(P+"interface",P+"ipv6_ping_target")),
 _case(54,55,"Wireless IPv4","network","IPv4 and reachability",(P+"interface",P+"ipv4_ping_target")),
 _case(55,56,"Wireless IPv6","network","global IPv6 and reachability",(P+"interface",P+"ipv6_ping_target")),
 _case(57,58,"H.264 decode","media","both sources reach PLAYING",MEDIA,("[4K123]Hercules The Thracian Wars.mp4","\u534e\u4e3a-\u9891\u905311-\u4e1c\u65b9\u536b\u89c6HD.ts"),AV),
 _case(58,59,"H.265 decode","media","both sources reach PLAYING",MEDIA,("[4KH265_21.1Mbps_59.940fps_10bit]worldcup2014_10bit_19m_60p.ts","[H.265_4K]_4K-HD.Club-2013-Taipei 101 Fireworks Trailer.mp4"),AV),
 _case(59,60,"AVS2 decode","media","both sources reach PLAYING",MEDIA,("case2.ts","case5.ts"),AV),
 _case(60,61,"H.264 4K60","media","source reaches PLAYING",MEDIA,("http://qa-sz.amlogic.com:8881/chfs/shared/Streams/Test_Files/REF_QA/4K_Video/4K-H264/60fps_59.94fps/4K_H264_SDR_Main@L5.2_3840x2160_100Mbps_59.94fps_8bit_AAC_2ch.ts",),AV),
 _case(61,62,"H.265 4K120","media","source reaches PLAYING",MEDIA,("http://qa-sz.amlogic.com:8881/chfs/shared/Streams/Test_Files/REF_QA/4K_Video/4K-H265-10bit/120FPS/4K_120fps_H265_Main_10@L6.1@High_3840x1608_80Mbps_5min_AAC2ch.ts",),AV),
 _case(62,63,"AV1 4K120","media","source reaches PLAYING",MEDIA,("http://qa-sz.amlogic.com:8881/chfs/shared/Streams/Test_Files/REF_QA/AV1/download_from_youtube/4K/120fps/4K_120fps_AV1_Main@L6.1_3840x1608_81Mbps_OGG2ch.mp4",),AV),
 _case(63,64,"VP9 4K120","media","source reaches PLAYING",MEDIA,("http://qa-sz.amlogic.com:8881/chfs/shared/Streams/Test_Files/REF_QA/4K_Video/4K-VP9/120fps/4K_120fps_VP9_3840x1608_90Mbps_2min_Vorbis2ch.webm",),AV),
 _case(64,65,"AVS2 4K120","media","source reaches PLAYING",MEDIA,("http://qa-sz.amlogic.com:8881/chfs/shared/Streams/Test_Files/REF_QA/4K_Video/4K-AVS2/120fps/4K_120fps_AVS2_3840x1608_100Mbps_AAC2ch.ts",),("Workbook notes source artifacts; assert playback state only.",)),
 _case(65,66,"AVS3 4K50","media","source reaches PLAYING",MEDIA,("http://qa-sz.amlogic.com:8881/chfs/shared/Test_File/Basicfunction_testing/IPTV-China-operator/CUVA-HDR/AVS3.0/%E9%A3%8E%E5%91%B3%E4%BA%BA%E9%97%B4-AVS3/01_01_HDR_FW-AVS3-Vivid.ts",),AV),
 _case(66,67,"MJPEG 4K30","media","source reaches PLAYING",MEDIA,("https://eng-sw-shared.amlogic.com/chfs/shared/ENG_QA/Test_File/Video%26Audio_release_test_files/006-avi/3840x2160_mjpeg.avi?v=1",),AV),
 _case(67,68,"JPEG GIF BMP PNG images","image","viewer focus for each configured image",(P+"media_source_override",),manual=("Image fidelity remains manual.",),equipment=("Configure workbook-format image paths.",)),
 _case(68,69,"SBS/TAB 3D video","media","configured sources reach PLAYING",MEDIA,manual=("3D switching and visual/A-V quality remain manual.",),equipment=("Workbook gives no exact source; configure SBS/TAB paths.",)),
 _case(69,70,"VR video","media","configured source reaches PLAYING",MEDIA,manual=("VR interaction and visual/A-V quality remain manual.",),equipment=("Workbook gives no exact source; configure it.",)),
 _case(95,96,"HTTP playback","media","configured HTTP stream reaches PLAYING",MEDIA,manual=AV,equipment=("Configure PC HTTP URL.",)),
 _case(96,97,"HLS playback","media","configured HLS stream reaches PLAYING",MEDIA,manual=AV,equipment=("Configure PC HLS URL.",)),
 _case(97,98,"UDP playback","media","configured UDP stream reaches PLAYING",MEDIA,manual=AV,equipment=("Configure PC UDP URL.",)),
 _case(98,99,"RTSP playback","media","configured RTSP stream reaches PLAYING",MEDIA,manual=AV,equipment=("Configure PC RTSP URL.",)),
 _case(114,115,"4K local playback 24H","media","playback remains PLAYING for configured duration",(P+"media_source_override",P+"playback_timeout_s",P+"playback_duration_s"),manual=AV,equipment=("Workbook gives no exact 4K file; configure it.",)),
)
assert tuple(c.source_id for c in MIDDLE_SCREEN_CASES)==SELECTED_SOURCE_IDS
def case_by_source_id(source_id): return next(c for c in MIDDLE_SCREEN_CASES if c.source_id==source_id)
