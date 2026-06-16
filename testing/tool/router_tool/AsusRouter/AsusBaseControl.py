"""
ASUS router browser-control placeholder.
"""

from __future__ import annotations

from ..RouterControl import RouterTools


class AsusBaseControl(RouterTools):
    CHANNEL_2_DICT = {
        "auto": "1",
        "1": "2",
        "2": "3",
        "3": "4",
        "4": "5",
        "5": "6",
        "6": "7",
        "7": "8",
        "8": "9",
        "9": "10",
        "10": "11",
        "11": "12",
        "12": "13",
        "13": "14",
    }
    CHANNEL_5_DICT = {
        "auto": "1",
        "36": "2",
        "40": "3",
        "44": "4",
        "48": "5",
        "52": "6",
        "56": "7",
        "60": "8",
        "64": "9",
        "149": "10",
        "153": "11",
        "157": "12",
        "161": "13",
    }
    BAND_MAP = {"2.4G": "2.4 GHz", "5G": "5 GHz"}
    WIRELESS_MAP = {
        "auto": "auto",
        "11n": "11n",
        "11ax": "11ax",
        "11ac": "11ac",
        "11a": "11a",
    }

    def change_wireless_mode(self, mode):
        self.browser_api_not_implemented(f"ASUS wireless mode change ({mode})")

    def change_country_v2(self, country_code):
        self.browser_api_not_implemented(f"ASUS country change ({country_code})")

    def change_country(self, router_or_code):
        self.browser_api_not_implemented("ASUS country change")

    def detect_ui_language(self):
        self.browser_api_not_implemented("ASUS UI language detection")
