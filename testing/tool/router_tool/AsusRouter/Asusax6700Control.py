"""
Asusax6700 control

This module is part of the AsusRouter package.
"""

import logging
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from ..RouterControl import ConfigError, RouterTools


class Asusax6700Control:
    """
        Asusax6700 control
            Parameters
            ----------
            None
                This class is instantiated without additional parameters.
            Returns
            -------
            None
                Classes return instances implicitly when constructed.
    """

    def __init__(self):
        """
            Init
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self.router_info = 'asus_6700'
        self.router_control = RouterTools(self.router_info)

        attrs = [
            'BAND_LIST', 'WIRELESS_2', 'WIRELESS_5', 'CHANNEL_2', 'CHANNEL_5',
            'BANDWIDTH_2', 'BANDWIDTH_5', 'AUTHENTICATION_METHOD',
            'AUTHENTICATION_METHOD_LEGCY', 'WEP_ENCRYPT', 'WPA_ENCRYPT',
            'PASSWD_INDEX_DICT', 'PROTECT_FRAME'
        ]
        for attr in attrs:
            setattr(self, attr, getattr(self.router_control, attr))

    def change_setting(self, router):
        """
            Change setting
                Interacts with the router's web interface using Selenium WebDriver.
                Waits for specific web elements to satisfy conditions using WebDriverWait.
                Pauses execution for a specified duration to allow operations to complete.
                Logs informational or debugging messages for tracing execution.
                Parameters
                ----------
                router : object
                    Router control object or router information required to perform operations.
                Returns
                -------
                object
                    Description of the returned value.
        """
        logging.info('Try to set router')
        try:
            self.router_control.login()
            self.router_control.driver.find_element(By.ID, 'Advanced_Wireless_Content_menu').click()

            WebDriverWait(driver=self.router_control.driver, timeout=5, poll_frequency=0.5).until(
                EC.presence_of_element_located((By.ID, 'FormTitle')))

            if (router.band):
                if router.band not in self.BAND_LIST: raise ConfigError('band element error')
                element = '//*[@id="wl_unit_field"]/td/select/option[{}]'
                index = '1' if router.band == '2.4G' else '2'
                self.router_control.driver.find_element(By.XPATH, element.format(index)).click()

            if router.wireless_mode:
                target_list = self.WIRELESS_2 if router.band == '2.4G' else self.WIRELESS_5
                if router.wireless_mode not in target_list:
                    raise ConfigError('channel element error')
                index = target_list.index(router.wireless_mode) + 1
                self.router_control.driver.find_element(
                    By.XPATH,
                    self.router_control.xpath['wireless_mode_element'][self.router_info].format(index)
                ).click()

            if (router.ssid):
                self.router_control.change_ssid(router.ssid)

            if (router.hide_ssid):
                if (router.hide_ssid) == '是':
                    self.router_control.driver.find_element(
                        By.XPATH, '//*[@id="WLgeneral"]/tbody/tr[5]/td/input[1]').click()
                elif (router.hide_ssid) == '否':
                    self.router_control.driver.find_element(
                        By.XPATH, '//*[@id="WLgeneral"]/tbody/tr[5]/td/input[2]').click()
            else:
                self.router_control.driver.find_element(By.XPATH, ".//input[@type='radio' and @value='0']").click()

            if (router.channel):
                channel = str(router.channel)

                self.router_control.change_channel(channel)

            if (router.bandwidth):
                if router.bandwidth not in \
                        {'2.4G': self.BANDWIDTH_2, '5G': self.BANDWIDTH_5}[
                            router.band]: raise ConfigError('bandwidth element error')
                self.router_control.change_bandwidth(router.bandwidth)

            if router.security_mode:
                auth_list = (self.AUTHENTICATION_METHOD
                             if router.wireless_mode != 'Legacy'
                             else self.AUTHENTICATION_METHOD_LEGCY)
                if router.security_mode not in auth_list:
                    raise ConfigError('security protocol method element error')
                self.router_control.change_authentication(router.security_mode)

            if (router.wep_encrypt):
                if router.wep_encrypt not in self.WEP_ENCRYPT: raise ConfigError('wep encrypt elemenr error')
                self.router_control.change_wep_encrypt(self.WEP_ENCRYPT[router.wep_encrypt])

            if (router.wpa_encrypt):
                if router.wpa_encrypt not in self.WPA_ENCRYPT: raise ConfigError('wpa encrypt elemenr error')
                self.router_control.change_wpa_encrypt(self.WPA_ENCRYPT[router.wpa_encrypt])

            if (router.passwd_index):
                if router.passwd_index not in self.PASSWD_INDEX_DICT: raise ConfigError(
                    'passwd index element error')
                self.router_control.change_passwd_index(router.passwd_index)

            if (router.wep_passwd):
                self.router_control.change_wep_passwd(router.wep_passwd)

            if (router.wpa_passwd):
                self.router_control.change_passwd(router.wpa_passwd)

            if (router.protect_frame):
                if router.protect_frame not in self.PROTECT_FRAME: raise ConfigError(
                    'protect frame element error')
                self.router_control.change_protect_frame(self.PROTECT_FRAME[router.protect_frame])

            time.sleep(5)

            self.router_control.apply_setting()
            try:
                self.router_control.driver.switch_to.alert.accept()
                self.router_control.driver.switch_to.alert.accept()
                self.router_control.driver.switch_to.alert.accept()
                self.router_control.driver.switch_to.alert.accept()
            except Exception as e:
                ...
            WebDriverWait(self.router_control.driver, 20).until_not(

                EC.visibility_of_element_located((By.XPATH, '//*[@id="loadingBlock"]/tbody/tr/td[2]'))
            )
            time.sleep(2)
            logging.info('Router setting done')
            return True
        except Exception as e:
            logging.info('Router change setting with error')
            logging.info(e)
            return False
        finally:
            self.router_control.driver.quit()











