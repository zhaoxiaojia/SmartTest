"""
Xiaomi base control

This module is part of the AsusRouter package.
"""
from ..RouterControl import RouterTools
import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from ..RouterControl import ConfigError


class XiaomiBaseControl(RouterTools):
    """
        Xiaomi base control
            Parameters
            ----------
            None
                This class is instantiated without additional parameters.
            Returns
            -------
            None
                Classes return instances implicitly when constructed.
    """
    BAND_2 = '2.4G'
    BAND_5 = '5G'

    CHANNEL_2 = {
        'auto': '1',
        '1': '2',
        '2': '3',
        '3': '4',
        '4': '5',
        '5': '6',
        '6': '7',
        '7': '8',
        '8': '9',
        '9': '10',
        '10': '11',
        '11': '12',
        '12': '13',
        '13': '14',
    }

    CHANNEL_5 = {
        'auto': '1',
        '36': '2',
        '40': '3',
        '44': '4',
        '48': '5',
        '52': '6',
        '56': '7',
        '60': '8',
        '64': '9',
        '149': '10',
        '153': '11',
        '157': '12',
        '161': '13',
        '165': '14'
    }

    AUTHENTICATION_METHOD = {
        '超强加密(WPA3个人版)': '1',
        '强混合加密(WPA3/WPA2个人版)': '2',
        '强加密(WPA2个人版)': '3',
        '混合加密(WPA/WPA2个人版)': '4',
        '无加密(允许所有人连接)': '5'
    }

    SECURITY_MODE_MAP = {
        "Open System": "无加密(允许所有人连接)",
        "WPA2-Personal": "强加密(WPA2个人版)",
        "WPA3-Personal": "超强加密(WPA3个人版)",

    }

    BANDWIDTH_5 = {
        '20/40/80 MHz': '1',
        '20 MHz': '2',
        '40 MHz': '3',
        '80 MHz': '4'
    }

    BANDWIDTH_2 = {
        '20/40 MHz': '1',
        '20 MHz': '2',
        '40 MHz': '3'
    }

    WIRELESS_2 = ['11n', '11ax']
    WIRELESS_5 = ['11ac', '11ax']

    def login(self):
        """
            Login
                Interacts with the router's web interface using Selenium WebDriver.
                Waits for specific web elements to satisfy conditions using WebDriverWait.
                Pauses execution for a specified duration to allow operations to complete.
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                None
                    This function does not return a value.
        """
        super()._init()

        self.driver.get(f"http://{self.address}")

        self.driver.find_element(By.ID, self.xpath['password_element']).click()
        self.driver.find_element(By.ID, self.xpath['password_element']).clear()
        time.sleep(1)
        self.driver.find_element(By.ID, self.xpath['password_element']).send_keys(
            self.xpath['passwd'])

        self.driver.find_element(By.ID, self.xpath['signin_element']).click()

        WebDriverWait(driver=self.driver, timeout=10, poll_frequency=0.5).until(
            EC.presence_of_element_located((By.ID, self.xpath['signin_done_element'])))

        time.sleep(1)

    def change_setting(self, router):
        """
            Change setting
                Interacts with the router's web interface using Selenium WebDriver.
                Waits for specific web elements to satisfy conditions using WebDriverWait.
                Performs router login or authentication before executing actions.
                Pauses execution for a specified duration to allow operations to complete.
                Logs informational or debugging messages for tracing execution.
                Parameters
                ----------
                router : object
                    Router control object or router information required to perform operations.
                Returns
                -------
                None
                    This function does not return a value.
        """
        logging.info('Try to set router')

        self.login()
        WebDriverWait(driver=self.driver, timeout=10, poll_frequency=0.5).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.mask-menu")))
        element = self.driver.find_element(By.CSS_SELECTOR, "a.btn_wifi")
        self.driver.execute_script("arguments[0].click();", element)

        wait = WebDriverWait(driver=self.driver, timeout=5, poll_frequency=0.5)
        wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="wifiset24"]/div[1]')))

        if router.band == self.BAND_5:
            wait_for = self.driver.find_element(By.XPATH, '//*[@id="wifiset50"]/div[1]/span[1]')
            self.scroll_to(wait_for)

        if router.ssid:
            primary_band = router.band
            secondary_band = self.BAND_5 if primary_band == self.BAND_2 else self.BAND_2

            secondary_ssid = f"{router.ssid}bat"

            self.driver.find_element(By.XPATH, self.xpath["ssid_element"][primary_band]).clear()
            self.driver.find_element(By.XPATH, self.xpath["ssid_element"][primary_band]).send_keys(router.ssid)

            self.driver.find_element(By.XPATH, self.xpath["ssid_element"][secondary_band]).clear()
            self.driver.find_element(By.XPATH, self.xpath["ssid_element"][secondary_band]).send_keys(secondary_ssid)

        hide_2g = self.driver.find_element(
            By.ID, self.xpath['hide_ssid']['hide_2g'])
        hide_5g = self.driver.find_element(
            By.ID, self.xpath['hide_ssid']['hide_5g'])

        if self.BAND_2 == router.band:
            target = hide_2g
        else:
            target = hide_5g

        if router.hide_ssid:
            if router.hide_ssid == '是' and not target.is_selected():
                target.click()
            if router.hide_ssid == '否' and target.is_selected():
                target.click()
        else:
            if target.is_selected():
                target.click()

        if router.security_mode:
            try:
                mode = self.SECURITY_MODE_MAP.get(router.security_mode, router.security_mode)
                index = self.AUTHENTICATION_METHOD[mode]
            except KeyError:
                raise ConfigError('security protocol method element error')
            target = 'authentication_2g' if self.BAND_2 == router.band else 'authentication_5g'
            self.driver.find_element(
                By.XPATH, self.xpath['authentication_select_element'][target]).click()

            self.driver.find_element(
                By.XPATH, self.xpath['authentication_regu_element'].format(index)).click()

        if router.password:
            if self.BAND_2 == router.band:
                target = 'passwd_2g'
            else:
                target = 'passwd_5g'
            self.driver.find_element(
                By.XPATH, self.xpath['passwd_element'][target]).clear()
            self.driver.find_element(
                By.XPATH, self.xpath['passwd_element'][target]).send_keys(router.password)

        if router.channel:
            channel = str(router.channel)
            try:
                if router.band == '2.4G':
                    index = self.CHANNEL_2[channel]
                    target = 'channel_2g'
                else:
                    index = self.CHANNEL_5[channel]
                    target = 'channel_5g'
            except KeyError:
                raise ConfigError('channel element error')

            self.driver.find_element(
                By.XPATH, self.xpath['channel_select_element'][target]).click()
            wait_for = self.driver.find_element(
                By.XPATH, self.xpath['channel_regu_element'].format(index))
            self.scroll_to(wait_for)
            time.sleep(1)
            wait_for.click()
            try:
                self.driver.find_element(By.XPATH, '//*[@id="meshDialogOpen"]').click()
            except Exception:
                ...

            try:
                self.driver.find_element(By.XPATH, "/html/body/div[1]/div/div[3]/div/a").click()
            except Exception:
                ...

        if router.bandwidth:
            if router.band == self.BAND_2:
                target_dict = self.BANDWIDTH_2
                target = 'bandwidth_2g'
            else:
                target_dict = self.BANDWIDTH_5
                target = 'bandwidth_5g'
            self.driver.find_element(
                By.XPATH, self.xpath['bandwidth_select_element'][target]).click()
            time.sleep(1)
            index = target_dict[router.bandwidth]
            self.driver.find_element(
                By.XPATH, self.xpath['bandwidth_element'].format(index)).click()

        time.sleep(5)
