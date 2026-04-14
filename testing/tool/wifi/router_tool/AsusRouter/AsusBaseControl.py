"""
Asus base control

This module is part of the AsusRouter package.
"""
from ..RouterControl import RouterTools, ConfigError
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
import time
import logging
import time

logger = logging.getLogger(__name__)
logger.info(">>> [DEBUG] ENTER change_country_v2 <<<")

class AsusBaseControl(RouterTools):
    """
        Asus base control
            Parameters
            ----------
            None
                This class is instantiated without additional parameters.
            Returns
            -------
            None
                Classes return instances implicitly when constructed.
    """
    CHANNEL_2_DICT = {
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
    CHANNEL_5_DICT = {
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
    }
    BAND_MAP = {"2.4G": "2.4 GHz", "5G": "5 GHz"}
    WIRELESS_MAP = {
        "auto": "自动",
        "11n": "N only",
        "11ax": '自动',
        "11ac": "自动",
        "11a": "自动"
    }

    def change_wireless_mode(self, mode):
        """
            Change wireless mode
                Interacts with the router's web interface using Selenium WebDriver.
                Asserts conditions to validate the success of operations.
                Parameters
                ----------
                mode : object
                    Wireless mode to configure on the router (e.g. 11n, 11ax).
                Returns
                -------
                None
                    This function does not return a value.
        """
        ui_mode = self.WIRELESS_MAP[mode]
        wireless_mode_select = Select(
            self.driver.find_element(By.XPATH, self.xpath['wireless_mode_element'][self.router_info]))
        wireless_mode_select.select_by_visible_text(ui_mode)
        assert wireless_mode_select.first_selected_option.text == ui_mode, "Wireless mode not selected"
        if mode == '11ax':
            index = '1'
        else:
            index = '2'
        self.driver.find_element(By.XPATH,
                                 self.xpath['wireless_ax_element'][self.router_info].format(index)).click()

    def change_country_v2(self, country_code):
        """
        支持多语言 UI 的国家码设置
        :param country_code: 标准代码 (e.g., 'US', 'CN', 'EU')
        """
        import logging
        import time
        logger = logging.getLogger(__name__)
        logger.info(">>> [DEBUG] ENTER change_country_v2 <<<")

        try:
            self.login()
            logger.info(">>> [DEBUG] Login completed")

            # 进入专业设置页
            wireless_menu = self.driver.find_element(By.ID, 'Advanced_Wireless_Content_menu')
            wireless_menu.click()
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, 'FormTitle')))

            professional_tab = self.driver.find_element(By.XPATH, '//*[@id="Advanced_WAdvanced_Content_tab"]/div')
            professional_tab.click()
            WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.ID, 'titl_desc')))
            logger.info(">>> [DEBUG] Professional settings loaded")

            # 👉 自动检测 UI 语言
            ui_lang = self.detect_ui_language()
            logger.info(f">>> [DEBUG] Detected UI language: {ui_lang}")

            # 👉 获取目标显示名称

            if country_code not in self.COUNTRY_DISPLAY_NAMES:
                supported = ', '.join(self.COUNTRY_DISPLAY_NAMES.keys())
                raise ConfigError(f"Unsupported country code: {country_code}. Supported: {supported}")

            # ✅ 修正 2: 检查 ui_lang 是否支持该 country_code
            if ui_lang not in self.COUNTRY_DISPLAY_NAMES[country_code]:
                available_langs = ', '.join(self.COUNTRY_DISPLAY_NAMES[country_code].keys())
                raise ConfigError(
                    f"Language '{ui_lang}' not supported for country code '{country_code}'. Available languages: {available_langs}")

            target_display_name = self.COUNTRY_DISPLAY_NAMES[country_code][ui_lang]
            logger.info(f">>> [DEBUG] Mapping '{country_code}' → '{target_display_name}' ({ui_lang})")

            # 👉 真实点击选择（与之前相同）
            try:
                country_select = self.driver.find_element(By.NAME, "ui_location_code")
            except:
                country_select = self.driver.find_element(By.NAME, "location_code")
            country_select.click()
            time.sleep(1)

            options = country_select.find_elements(By.TAG_NAME, "option")
            target_index = None
            for i, option in enumerate(options):
                if option.text.strip() == target_display_name:
                    target_index = i
                    break

            if target_index is None:
                available = [opt.text for opt in options]
                raise ConfigError(
                    f"'{target_display_name}' not found in dropdown. "
                    f"Available options: {available}"
                )

            options[target_index].click()
            logger.info(f">>> [DEBUG] Selected: {target_display_name}")
            time.sleep(1)

            # 👉 Apply + 弹窗处理（复用成功逻辑）
            apply_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="apply_btn"]/input'))
            )
            apply_btn.click()
            logger.info(">>> [DEBUG] APPLY clicked")

            # 处理所有弹窗
            alert_count = 0
            while alert_count < 5:
                try:
                    WebDriverWait(self.driver, 5).until(EC.alert_is_present())
                    alert = self.driver.switch_to.alert
                    logger.info(f">>> [DEBUG] Alert: {alert.text}")
                    alert.accept()
                    alert_count += 1
                    time.sleep(2)
                except:
                    break
            logger.info(f">>> [DEBUG] Handled {alert_count} alert(s)")

            # 等待完成
            WebDriverWait(self.driver, 120).until_not(
                EC.visibility_of_element_located((By.XPATH, '//*[@id="loadingBlock"]'))
            )

            logger.info(">>> [DEBUG] Country changed successfully")
            return True

        except Exception as e:
            logger.error(f">>> [ERROR] Failed: {e}", exc_info=True)
            raise

    def change_country(self, router_or_code):
        """
            Change country
                Interacts with the router's web interface using Selenium WebDriver.
                Waits for specific web elements to satisfy conditions using WebDriverWait.
                Performs router login or authentication before executing actions.
                Parameters
                ----------
                router_or_code : object
                    Either a router instance or a string containing the country code to configure.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self.login()
        self.driver.find_element(By.ID, 'Advanced_Wireless_Content_menu').click()

        WebDriverWait(driver=self.driver, timeout=5, poll_frequency=0.5).until(
            EC.presence_of_element_located((By.ID, 'FormTitle'))
        )

        if isinstance(router_or_code, str):
            country_code = router_or_code
        else:
            country_code = getattr(router_or_code, "country_code", None)

        if country_code:
            if country_code not in self.COUNTRY_CODE:
                raise ConfigError('country code error')

            self.driver.find_element(
                By.XPATH, '//*[@id="Advanced_WAdvanced_Content_tab"]/div'
            ).click()

            WebDriverWait(driver=self.driver, timeout=5, poll_frequency=0.5).until(
                EC.presence_of_element_located((By.ID, 'titl_desc'))
            )

            index = self.COUNTRY_CODE[country_code]
            self.driver.find_element(
                By.XPATH,
                self.xpath['country_code_element'][self.router_info].format(index)
            ).click()

            self.driver.find_element(
                By.XPATH, '//*[@id="apply_btn"]/input'
            ).click()

            for _ in range(2):
                try:
                    self.driver.switch_to.alert.accept()
                except Exception:
                    ...

            WebDriverWait(driver=self.driver, timeout=120, poll_frequency=0.5).until_not(
                EC.visibility_of_element_located((By.XPATH, '//*[@id="loadingBlock"]/tbody'))
            )

    def detect_ui_language(self):
        """通过页面特征自动判断语言"""
        try:
            # 方法1: 检查页面标题或固定文本
            title = self.driver.title
            if "路由器" in title or "设置" in title:
                return 'zh'

            # 方法2: 检查已知元素的文本
            wireless_menu = self.driver.find_element(By.ID, 'Advanced_Wireless_Content_menu')
            menu_text = wireless_menu.text
            if "无线" in menu_text or "网络" in menu_text:
                return 'zh'
            elif "Wireless" in menu_text or "Network" in menu_text:
                return 'en'

        except Exception as e:
            logging.warning(f"Language detection failed: {e}")

        # 默认 fallback
        return 'zh'  # 或根据路由器配置决定
