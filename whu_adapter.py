"""
武汉大学(WHU)教务系统专用适配器
支持CAS统一身份认证登录
网址: https://jwgl.whu.edu.cn/

版本: 1.0
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from typing import Tuple
import logging
import time

# 配置日志
logger = logging.getLogger(__name__)


class WHUAdapter:
    """武汉大学教务系统适配器"""
    
    def __init__(self, username=None, password=None, driver=None, captcha_manager=None):
        """
        初始化适配器
        
        Args:
            username: 学号
            password: 密码
            driver: Selenium WebDriver实例
            captcha_manager: 验证码管理器
        """
        self.username = username
        self.password = password
        self.driver = driver
        self.captcha_manager = captcha_manager
        self.login_url = "https://cas.whu.edu.cn/authserver/login?service=https%3A%2F%2Fjwgl.whu.edu.cn%2Fsso%2Fjznewsixlogin"
        self.selection_url = "https://jwgl.whu.edu.cn/xsxk/zzxkyzb_cxZzxkYzbIndex.html?gnmkdm=N253512&layout=default"
        self.course_api_url = "https://jwgl.whu.edu.cn/xsxk/zzxkyzb_loadTableData"
        
    def login(self):
        """
        登录到武汉大学教务系统
        
        步骤:
        1. 访问CAS登录页面
        2. 处理可能的验证码
        3. 输入学号和密码
        4. 提交登录
        5. 等待重定向到选课系统
        
        Returns:
            bool: 登录成功返回True，失败返回False
        """
        try:
            logger.info("开始登录武汉大学教务系统...")
            
            # 步骤1: 访问登录页面
            self.driver.get(self.login_url)
            logger.info(f"已访问登录页面: {self.login_url}")
            
            # 等待登录表单加载
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            logger.info("登录表单已加载")
            
            # 步骤2: 检测并处理验证码（如果有）
            if self.captcha_manager:
                self._handle_captcha_if_present()
            
            # 步骤3: 填写学号
            username_input = self.driver.find_element(By.ID, "username")
            username_input.clear()
            username_input.send_keys(self.username)
            logger.info(f"已输入学号: {self.username}")
            
            # 步骤4: 填写密码
            password_input = self.driver.find_element(By.ID, "password")
            password_input.clear()
            password_input.send_keys(self.password)
            logger.info("已输入密码")
            
            # 步骤5: 提交登录
            login_button = self.driver.find_element(By.XPATH, "//button[contains(text(), '登录')]")
            login_button.click()
            logger.info("已点击登录按钮，等待页面加载...")
            
            # 等待登录完成和重定向
            time.sleep(3)
            
            # 判断登录是否成功：
            # 1. URL包含jwgl.whu.edu.cn（教务系统域名）
            # 2. 登录后可能跳转到多个页面：
            #    - 选课页面: xsxk
            #    - 首页: xtgl/index_initMenu
            #    - 其他系统页面
            # 只要不在cas.whu.edu.cn，说明已经登录成功
            
            def check_login_success(driver):
                current_url = driver.current_url
                # 如果还在CAS登录页面，说明登录失败
                if "cas.whu.edu.cn" in current_url:
                    return False
                # 如果已经进入教务系统的任何页面，说明登录成功
                if "jwgl.whu.edu.cn" in current_url:
                    return True
                return False
            
            WebDriverWait(self.driver, 15).until(check_login_success)
            
            current_url = self.driver.current_url
            logger.info(f"✅ 登录成功! 当前页面: {current_url}")
            
            # 如果不在选课页面，尝试导航到选课页面
            if "xsxk" not in current_url:
                logger.info("当前页面不是选课页面，正在导航到选课页面...")
                try:
                    self.driver.get(self.selection_url)
                    time.sleep(2)
                    logger.info(f"已导航到选课页面: {self.driver.current_url}")
                except Exception as e:
                    logger.warning(f"导航到选课页面失败，但登录已成功: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 登录失败: {str(e)}")
            logger.error(f"当前URL: {self.driver.current_url}")
            return False
    
    def _handle_captcha_if_present(self):
        """
        检测并处理CAS登录页面上的验证码
        
        WHU的CAS系统可能包含：
        1. 图片验证码（行为验证）
        2. 滑动验证码（极验或网易易盾）
        """
        try:
            logger.info("检测验证码...")
            
            # 检测极验滑动验证码
            try:
                geetest_box = self.driver.find_element(By.CLASS_NAME, "geetest_box")
                if geetest_box:
                    logger.info("检测到极验验证码，调用验证码管理器处理...")
                    self.captcha_manager.handle_captcha()
                    time.sleep(2)
                    return
            except:
                pass
            
            # 检测网易易盾验证码
            try:
                nc_box = self.driver.find_element(By.CLASS_NAME, "nc_box")
                if nc_box:
                    logger.info("检测到网易易盾验证码，调用验证码管理器处理...")
                    self.captcha_manager.handle_captcha()
                    time.sleep(2)
                    return
            except:
                pass
            
            # 检测行为验证码（有时是iframe）
            try:
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                for iframe in iframes:
                    if "captcha" in iframe.get_attribute("src").lower():
                        logger.info("检测到验证码iframe，调用验证码管理器处理...")
                        self.captcha_manager.handle_captcha()
                        time.sleep(2)
                        return
            except:
                pass
            
            logger.info("未检测到验证码，继续登录...")
            
        except Exception as e:
            logger.warning(f"验证码处理出错: {str(e)}，将继续尝试登录")
    
    def get_courses(self):
        """
        获取选课列表
        
        Returns:
            list: 课程列表，每个课程包含：
                {
                    'id': '课程ID',
                    'name': '课程名称',
                    'teacher': '教师',
                    'time': '上课时间',
                    'location': '上课地点',
                    'capacity': '容量',
                    'enrolled': '已选人数'
                }
        """
        try:
            logger.info("开始获取选课列表...")
            
            # 确保在选课页面
            if "xsxk" not in self.driver.current_url:
                self.driver.get(self.selection_url)
                time.sleep(2)
            
            # 等待课程表加载
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "tbody"))
            )
            
            # 获取所有可见课程行（支持分页或无限滚动）
            courses = []
            seen_keys = set()

            def extract_rows():
                rows = self.driver.find_elements(By.CSS_SELECTOR, "tbody tr")
                logger.info(f"找到 {len(rows)} 行数据")
                for row in rows:
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) >= 7:
                            course = {
                                'id': cells[0].text.strip(),
                                'name': cells[1].text.strip(),
                                'teacher': cells[2].text.strip(),
                                'time': cells[3].text.strip(),
                                'location': cells[4].text.strip(),
                                'capacity': cells[5].text.strip(),
                                'enrolled': cells[6].text.strip(),
                            }
                            # 去重：用课程ID+时间作为唯一键
                            key = f"{course['id']}|{course['time']}"
                            if key not in seen_keys:
                                seen_keys.add(key)
                                courses.append(course)
                                logger.debug(f"课程: {course['name']} {course['time']}")
                    except Exception as e:
                        logger.warning(f"解析课程行失败: {str(e)}")
                        continue

            # 1) 先抓取当前页
            extract_rows()

            # 2) 尝试翻页（如果存在“下一页”按钮）
            for _ in range(10):
                try:
                    next_btn = self.driver.find_element(By.XPATH,
                        "//a[contains(text(),'下一页') or contains(text(),'下一页>') or contains(text(),'>')]"
                    )
                    if not next_btn.is_enabled() or 'disabled' in next_btn.get_attribute('class'):
                        break
                    # 点击下一页并等待
                    next_btn.click()
                    time.sleep(1)
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.TAG_NAME, "tbody"))
                    )
                    extract_rows()
                    continue
                except Exception:
                    break

            # 3) 如果是无限滚动，尝试滚动加载更多
            last_count = len(courses)
            for _ in range(5):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
                extract_rows()
                if len(courses) == last_count:
                    break
                last_count = len(courses)

            logger.info(f"✅ 成功获取 {len(courses)} 门课程")
            return courses
            
        except Exception as e:
            logger.error(f"❌ 获取选课列表失败: {str(e)}")

            # 重试机制：刷新页面后再次尝试抓取（避免瞬时网络/页面崩溃）
            for attempt in range(2):
                try:
                    logger.info(f"重试获取选课列表 (第{attempt+1}次)...")
                    self.driver.refresh()
                    time.sleep(1)
                    return self.get_courses()
                except Exception as e2:
                    logger.warning(f"重试失败: {e2}")
                    time.sleep(1)

            logger.error("❌ 多次重试后仍无法获取选课列表，放弃本次抓取")
            return []
    
    def _parse_select_result(self) -> Tuple[bool, str]:
        """尝试解析页面选课结果提示信息。

        Returns:
            Tuple[bool, str]: (是否成功, 提示信息)
        """
        try:
            # 常见的提示信息包含在 toast/alert 或弹窗中
            # 通过文本匹配来判断是否成功或失败
            common_xpath = (
                "//div[contains(@class,'toast') or contains(@class,'alert') or contains(@class,'message')"
                " or contains(@class,'layui-layer-content') or contains(@class,'modal-body')]")
            elems = self.driver.find_elements(By.XPATH, common_xpath)
            messages = [e.text.strip() for e in elems if e.text.strip()]

            # 进一步收集页面上的明显提示文本
            if not messages:
                candidates = self.driver.find_elements(By.XPATH,
                    "//div[contains(text(),'已选') or contains(text(),'已满') or contains(text(),'选课成功')"
                    " or contains(text(),'选课失败') or contains(text(),'失败') or contains(text(),'已选中')]"
                )
                messages = [e.text.strip() for e in candidates if e.text.strip()]

            msg = ' '.join(messages) if messages else ''

            if not msg:
                return True, "未检测到明确提示，假定成功"

            # 关键字判断
            if any(k in msg for k in ['选课成功', '已选中', '已选', '选课完成']):
                return True, msg
            if any(k in msg for k in ['已满', '已满选课', '选课失败', '失败', '未通过']):
                return False, msg

            # 默认返回成功但带提示信息
            return True, msg
        except Exception as e:
            logger.warning(f"⚠️ 解析选课结果提示失败: {e}")
            return False, f"解析提示失败: {e}"

    def select_course(self, course_id) -> Tuple[bool, str]:
        """选择一门课程

        Args:
            course_id: 课程ID

        Returns:
            Tuple[bool, str]: (选课是否成功, 结果提示)
        """
        try:
            logger.info(f"开始选课: {course_id}")

            # 找到对应课程的选课按钮
            rows = self.driver.find_elements(By.CSS_SELECTOR, "tbody tr")

            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if cells and cells[0].text.strip() == course_id:
                    # 找到选课按钮
                    try:
                        select_btn = row.find_element(By.CLASS_NAME, "btn-select")
                        select_btn.click()
                    except Exception:
                        logger.warning("⚠️ 找不到选课按钮，可能已选中或不允许选课")

                    logger.info("已点击选课按钮，等待确认...")
                    time.sleep(1)

                    # 处理可能的确认弹框
                    try:
                        confirm_btn = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.CLASS_NAME, "btn-confirm"))
                        )
                        confirm_btn.click()
                        time.sleep(1)
                    except Exception:
                        # 没有确认框也正常
                        pass

                    success, reason = self._parse_select_result()

                    # 如果抓取不到明确提示，进一步通过课程列表确认是否已消失（即已被选中）
                    if success and reason.startswith("未检测到明确提示"):
                        available = self.get_courses()
                        if available is None:
                            # 读取失败时不作成功判断
                            return False, "获取课程列表失败，无法确认是否已选上"

                        exists = any(c.get('id') == course_id or c.get('course_id') == course_id for c in available)
                        if not exists:
                            reason = "已从列表中消失，可能已选中"
                            logger.info(f"✅ 课程 {course_id} 选课成功: {reason}")
                            return True, reason

                        # 仍在列表中，视为未成功
                        reason = f"未检测到成功提示，且课程仍在列表中 ({course_id})"
                        logger.warning(f"❌ 课程 {course_id} 选课失败: {reason}")
                        return False, reason

                    if success:
                        logger.info(f"✅ 课程 {course_id} 选课成功: {reason}")
                    else:
                        logger.warning(f"❌ 课程 {course_id} 选课失败: {reason}")
                    return success, reason

            logger.error(f"❌ 未找到课程: {course_id}")
            return False, "未找到课程"

        except Exception as e:
            logger.error(f"❌ 选课失败: {str(e)}")
            return False, str(e)
    
    def check_login_status(self):
        """
        检查登录状态
        
        Returns:
            bool: 已登录返回True，未登录返回False
        """
        try:
            # 检查是否有登出按钮（说明已登录）
            self.driver.find_element(By.CLASS_NAME, "logout-btn")
            logger.info("✅ 已确认登录状态")
            return True
        except:
            logger.warning("⚠️ 未检测到登录标识")
            return False


# 工厂函数
def get_whu_adapter(username, password, driver, captcha_manager=None):
    """
    创建WHU适配器实例
    
    Args:
        username: 学号
        password: 密码
        driver: Selenium WebDriver
        captcha_manager: 验证码管理器（可选）
        
    Returns:
        WHUAdapter: 适配器实例
    """
    return WHUAdapter(username, password, driver, captcha_manager)
