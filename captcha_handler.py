#!/usr/bin/env python3
"""
验证码处理增强模块
支持滑动验证码和图片验证码的自动识别和处理
"""

import time
import logging
import base64
from typing import Optional, Tuple
from PIL import Image
import io

logger = logging.getLogger(__name__)


class SliderCaptchaHandler:
    """滑动验证码处理器"""
    
    def __init__(self, driver):
        """
        初始化滑动验证码处理器
        
        Args:
            driver: Selenium WebDriver实例
        """
        self.driver = driver
    
    def detect_slider_captcha(self) -> bool:
        """
        检测是否存在滑动验证码
        
        Returns:
            是否检测到滑动验证码
        """
        try:
            # 检查常见的滑动验证码框架
            selectors = [
                '[class*="slider"]',
                '[id*="slider"]',
                '[class*="slide"]',
                '[class*="captcha"]',
                '.geetest_box',  # 极验验证码
                '.nc_box',       # 网易易盾
                '.freecap',      # 免费验证码
            ]
            
            for selector in selectors:
                try:
                    element = self.driver.find_element('css selector', selector)
                    if element.is_displayed():
                        logger.warning(f"检测到滑动验证码: {selector}")
                        return True
                except:
                    pass
            
            return False
        except Exception as e:
            logger.error(f"检测滑动验证码异常: {e}")
            return False
    
    def auto_slide(self, distance: Optional[int] = None) -> bool:
        """
        自动滑动验证码（简单版本）
        
        Args:
            distance: 滑动距离，如为None则自动计算
            
        Returns:
            是否成功
        """
        try:
            from selenium.webdriver.common.action_chains import ActionChains
            from selenium.webdriver.common.by import By
            
            # 查找滑块元素
            slider_button = None
            selectors = [
                '.geetest_slider_button',
                '.slider-button',
                '[class*="slider-button"]',
                '.nc-slider',
            ]
            
            for selector in selectors:
                try:
                    slider_button = self.driver.find_element('css selector', selector)
                    if slider_button.is_displayed():
                        break
                except:
                    pass
            
            if not slider_button:
                logger.warning("未找到滑块按钮，可能需要手动处理")
                return False
            
            # 计算滑动距离（如果未指定）
            if distance is None:
                # 获取滑块容器宽度，通常需要滑动到末尾
                container = self.driver.find_element('css selector', '[class*="slider-track"]')
                container_width = container.size['width']
                distance = int(container_width * 0.95)  # 滑动到95%位置
            
            # 执行滑动
            logger.info(f"执行滑块滑动，距离: {distance}px")
            actions = ActionChains(self.driver)
            actions.click_and_hold(slider_button)
            actions.move_by_offset(distance, 0)
            actions.release()
            actions.perform()
            
            # 等待验证完成
            time.sleep(2)
            
            # 检查验证是否通过
            if self._check_captcha_passed():
                logger.info("✓ 滑动验证码已通过")
                return True
            else:
                logger.warning("✗ 滑动验证码验证失败")
                return False
            
        except Exception as e:
            logger.error(f"滑动验证码处理异常: {e}")
            return False
    
    def _check_captcha_passed(self) -> bool:
        """
        检查验证是否通过
        
        Returns:
            是否通过验证
        """
        try:
            # 检查是否存在"验证成功"提示
            success_indicators = [
                '[class*="success"]',
                '[class*="passed"]',
                '.geetest_success',
            ]
            
            for selector in success_indicators:
                try:
                    element = self.driver.find_element('css selector', selector)
                    if element.is_displayed():
                        return True
                except:
                    pass
            
            # 检查验证框是否消失
            try:
                captcha = self.driver.find_element('css selector', '[class*="captcha"]')
                return not captcha.is_displayed()
            except:
                return True
                
        except Exception as e:
            logger.error(f"检查验证状态异常: {e}")
            return False
    
    def manual_slider_prompt(self):
        """
        提示用户手动处理滑动验证码
        """
        logger.warning("\n" + "="*60)
        logger.warning("⚠️  检测到滑动验证码，需要您的协助")
        logger.warning("="*60)
        logger.warning("请按照以下步骤操作：")
        logger.warning("1. 在浏览器窗口中手动完成滑动验证码")
        logger.warning("2. 完成后按Enter键继续")
        logger.warning("="*60 + "\n")
        
        input("请输入任意内容后按Enter继续: ")
        return True


class ImageCaptchaHandler:
    """图片验证码处理器"""
    
    def __init__(self, driver, ocr_service: str = 'manual'):
        """
        初始化图片验证码处理器
        
        Args:
            driver: Selenium WebDriver实例
            ocr_service: OCR服务类型 ('manual', 'paddleocr', '2captcha', 'anticaptcha')
        """
        self.driver = driver
        self.ocr_service = ocr_service
        self.paddle_ocr = None
        
        if ocr_service == 'paddleocr':
            try:
                from paddleocr import PaddleOCR
                self.paddle_ocr = PaddleOCR(use_angle_cls=True, lang='ch')
                logger.info("PaddleOCR已初始化")
            except ImportError:
                logger.warning("PaddleOCR未安装，将使用手动输入")
                self.ocr_service = 'manual'
    
    def detect_image_captcha(self) -> Optional[str]:
        """
        检测图片验证码
        
        Returns:
            验证码输入框的选择器，如果未找到则返回None
        """
        selectors = [
            'input[id*="captcha"]',
            'input[name*="captcha"]',
            'input[placeholder*="验证码"]',
            'input[placeholder*="code"]',
            '.captcha-input',
            '[class*="verify-input"]',
        ]
        
        for selector in selectors:
            try:
                element = self.driver.find_element('css selector', selector)
                if element.is_displayed():
                    logger.info(f"检测到验证码输入框: {selector}")
                    return selector
            except:
                pass
        
        return None
    
    def get_captcha_image(self) -> Optional[bytes]:
        """
        获取验证码图片
        
        Returns:
            验证码图片的字节数据
        """
        try:
            image_selectors = [
                'img[id*="captcha"]',
                'img[src*="captcha"]',
                '.captcha-image img',
                '[class*="verify-image"] img',
            ]
            
            for selector in image_selectors:
                try:
                    img_element = self.driver.find_element('css selector', selector)
                    
                    # 方法1: 截图元素
                    img_data = img_element.screenshot_as_png
                    
                    if img_data:
                        logger.info("已获取验证码图片")
                        return img_data
                except:
                    pass
            
            return None
        except Exception as e:
            logger.error(f"获取验证码图片异常: {e}")
            return None
    
    def recognize_captcha(self, image_data: bytes) -> str:
        """
        识别验证码
        
        Args:
            image_data: 验证码图片数据
            
        Returns:
            识别结果
        """
        if self.ocr_service == 'paddleocr':
            return self._recognize_with_paddleocr(image_data)
        elif self.ocr_service == '2captcha':
            return self._recognize_with_2captcha(image_data)
        elif self.ocr_service == 'anticaptcha':
            return self._recognize_with_anticaptcha(image_data)
        else:
            return self._recognize_manual(image_data)
    
    def _recognize_with_paddleocr(self, image_data: bytes) -> str:
        """使用PaddleOCR识别"""
        try:
            if not self.paddle_ocr:
                return self._recognize_manual(image_data)
            
            img = Image.open(io.BytesIO(image_data))
            result = self.paddle_ocr.ocr(img, cls=True)
            
            # 提取文本
            text = ''.join([line[0][1] for line in result[0]])
            logger.info(f"PaddleOCR识别结果: {text}")
            
            return text
        except Exception as e:
            logger.error(f"PaddleOCR识别失败: {e}")
            return self._recognize_manual(image_data)
    
    def _recognize_with_2captcha(self, image_data: bytes) -> str:
        """使用2Captcha识别"""
        try:
            import requests
            api_key = '你的2captcha_key'  # 需要配置
            
            # 上传到2Captcha
            response = requests.post(
                'http://2captcha.com/api/upload',
                files={'captchafile': io.BytesIO(image_data)},
                data={'key': api_key, 'method': 'post'}
            )
            
            if response.status_code != 200:
                logger.error("2Captcha上传失败")
                return self._recognize_manual(image_data)
            
            captcha_id = response.text
            
            # 轮询获取结果
            for i in range(30):
                time.sleep(1)
                result = requests.get(
                    f'http://2captcha.com/api/res.php?key={api_key}&action=get&id={captcha_id}'
                )
                
                if 'OK' in result.text:
                    text = result.text.split('|')[1]
                    logger.info(f"2Captcha识别结果: {text}")
                    return text
            
            logger.error("2Captcha识别超时")
            return self._recognize_manual(image_data)
            
        except Exception as e:
            logger.error(f"2Captcha识别异常: {e}")
            return self._recognize_manual(image_data)
    
    def _recognize_with_anticaptcha(self, image_data: bytes) -> str:
        """使用AntiCaptcha识别"""
        try:
            import requests
            api_key = '你的anticaptcha_key'  # 需要配置
            
            image_base64 = base64.b64encode(image_data).decode()
            
            response = requests.post(
                'https://api.anti-captcha.com/createTask',
                json={
                    'clientKey': api_key,
                    'task': {
                        'type': 'ImageToTextTask',
                        'body': image_base64,
                    }
                }
            )
            
            if response.status_code != 200:
                logger.error("AntiCaptcha请求失败")
                return self._recognize_manual(image_data)
            
            task_id = response.json().get('taskId')
            
            # 轮询获取结果
            for i in range(30):
                time.sleep(1)
                result = requests.post(
                    'https://api.anti-captcha.com/getTaskResult',
                    json={'clientKey': api_key, 'taskId': task_id}
                )
                
                if result.json().get('status') == 'ready':
                    text = result.json()['solution']['text']
                    logger.info(f"AntiCaptcha识别结果: {text}")
                    return text
            
            logger.error("AntiCaptcha识别超时")
            return self._recognize_manual(image_data)
            
        except Exception as e:
            logger.error(f"AntiCaptcha识别异常: {e}")
            return self._recognize_manual(image_data)
    
    def _recognize_manual(self, image_data: bytes) -> str:
        """手动识别验证码"""
        try:
            # 将图片保存到临时文件
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                f.write(image_data)
                temp_path = f.name
            
            logger.warning("\n" + "="*60)
            logger.warning("需要输入验证码")
            logger.warning("="*60)
            logger.warning(f"验证码图片已保存到: {temp_path}")
            logger.warning("请打开此文件查看验证码内容")
            logger.warning("="*60 + "\n")
            
            text = input("请输入验证码: ").strip()
            return text
            
        except Exception as e:
            logger.error(f"手动输入失败: {e}")
            return input("请输入验证码: ").strip()
    
    def submit_captcha(self, input_selector: str, captcha_text: str) -> bool:
        """
        提交验证码
        
        Args:
            input_selector: 输入框选择器
            captcha_text: 验证码文本
            
        Returns:
            是否成功提交
        """
        try:
            input_element = self.driver.find_element('css selector', input_selector)
            input_element.clear()
            input_element.send_keys(captcha_text)
            
            # 寻找提交按钮
            submit_selectors = [
                'button[type="submit"]',
                'button[id*="submit"]',
                'button[class*="confirm"]',
                '.captcha-submit',
            ]
            
            for selector in submit_selectors:
                try:
                    submit_btn = self.driver.find_element('css selector', selector)
                    if submit_btn.is_displayed():
                        submit_btn.click()
                        time.sleep(2)
                        logger.info("✓ 已提交验证码")
                        return True
                except:
                    pass
            
            # 如果没找到提交按钮，按Enter键
            input_element.submit()
            time.sleep(2)
            logger.info("✓ 已提交验证码")
            return True
            
        except Exception as e:
            logger.error(f"提交验证码异常: {e}")
            return False


class CaptchaManager:
    """验证码管理器（综合处理滑动和图片验证码）"""
    
    def __init__(self, driver, ocr_service: str = 'manual'):
        """
        初始化验证码管理器
        
        Args:
            driver: Selenium WebDriver实例
            ocr_service: OCR服务类型
        """
        self.driver = driver
        self.slider_handler = SliderCaptchaHandler(driver)
        self.image_handler = ImageCaptchaHandler(driver, ocr_service)
    
    def handle_captcha(self) -> bool:
        """
        处理所有类型的验证码
        
        Returns:
            是否成功通过验证码
        """
        logger.info("开始检测和处理验证码...")
        
        # 1. 先处理滑动验证码
        if self.slider_handler.detect_slider_captcha():
            if not self.slider_handler.auto_slide():
                # 自动滑动失败，提示手动处理
                self.slider_handler.manual_slider_prompt()
        
        time.sleep(1)
        
        # 2. 再处理图片验证码
        input_selector = self.image_handler.detect_image_captcha()
        
        if input_selector:
            # 获取验证码图片
            img_data = self.image_handler.get_captcha_image()
            
            if img_data:
                # 识别验证码
                captcha_text = self.image_handler.recognize_captcha(img_data)
                
                if captcha_text:
                    # 提交验证码
                    return self.image_handler.submit_captcha(input_selector, captcha_text)
        
        logger.info("未检测到需要处理的验证码")
        return True


# 使用示例
if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    from selenium import webdriver
    
    driver = webdriver.Chrome()
    manager = CaptchaManager(driver, ocr_service='manual')
    
    try:
        driver.get('http://example.com/login')
        
        # 处理验证码
        if manager.handle_captcha():
            logger.info("验证码已通过")
        else:
            logger.error("验证码处理失败")
    finally:
        driver.quit()
