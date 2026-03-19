#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎓 武汉大学教务系统自动选课脚本
=========================================

使用配置文件 whu_config.json 中的课程信息自动选课

功能特性：
  ✅ 从 whu_config.json 读取课程ID
  ✅ 支持定时开始选课（grab_time）
  ✅ 支持多线程并发选课
  ✅ 完整的错误处理和日志记录
  ✅ 与 whu_login.py 集成使用

使用方法：

【方法1】直接配置文件式（推荐）
  1. 编辑 whu_config.json，在 courses 字段加入课程ID
  2. 编辑 schedule.grab_time 设置选课时间
  3. 运行此脚本：
     python grab_whu_courses.py
  4. 首次会提示输入学号和密码
  5. 到达选课时间会自动选课

【方法2】命令行指定配置文件
  python grab_whu_courses.py /path/to/custom_config.json

配置文件格式（whu_config.json）：
  
  {
    "system_type": "WHU",
    "schedule": {
      "enabled": true,
      "grab_time": "2026-03-20 10:00:00"
    },
    "courses": [
      {"course_id": "000001", "name": "课程1"},
      {"course_id": "000002", "name": "课程2"}
    ]
  }

提示：
  1. 学号和密码只在运行时输入，不会保存到文件
  2. 选课时间必须是 "YYYY-MM-DD HH:MM:SS" 格式
  3. course_id 必须是字符串格式
  4. 每个课程独立选课，避免过快触发限制
"""

import json
import logging
import time
import sys
from datetime import datetime
from getpass import getpass
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple

from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver

try:
    from captcha_handler import CaptchaManager
    from whu_adapter import WHUAdapter
except ImportError:
    print("⚠️ 缺少必要模块，请确保在项目目录下运行")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('grab_whu_courses.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class WHUCourseGrabber:
    """武汉大学教务系统自动选课器"""
    
    def __init__(self, config: Dict, username: str = None, password: str = None):
        """
        初始化选课器
        
        Args:
            config: 配置字典
            username: 学号（可选，如为None则运行时提示输入）
            password: 密码（可选，如为None则运行时提示输入）
        """
        self.config = config
        self.username = username
        self.password = password
        self.courses = config.get('courses', [])
        self.schedule = config.get('schedule', {})
        self.grab_time = self.schedule.get('grab_time')
        self.max_workers = config.get('max_workers', 3)
        
        logger.info(f"✓ 选课器已初始化 - 课程数: {len(self.courses)}")
    
    def setup_driver(self):
        """设置Chrome驱动"""
        logger.info("正在启动浏览器...")
        
        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        
        try:
            logger.info("配置 ChromeDriver...")
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            logger.info("✅ 浏览器启动成功")
            return driver
        except Exception as e:
            logger.error(f"❌ 浏览器启动失败: {e}")
            raise
    
    def get_credentials(self):
        """从命令行获取学号和密码"""
        if self.username and self.password:
            return self.username, self.password
        
        print("\n" + "="*70)
        print("🎓 武汉大学教务系统 - 自动选课")
        print("="*70)
        print("\n📝 请输入你的凭证：")
        print("   (不会保存到任何文件中)\n")
        
        # 获取学号
        while True:
            username = input("学号: ").strip()
            if username:
                break
            print("⚠️ 学号不能为空，请重新输入")
        
        # 获取密码
        print("\n🔐 请输入密码：")
        print("   (密码不会显示，直接输入后按 Enter)\n")
        
        while True:
            password = getpass("密码: ")
            if password:
                break
            print("⚠️ 密码不能为空，请重新输入")
        
        return username, password
    
    def wait_for_grab_time(self):
        """等待指定的选课时间"""
        if not self.grab_time:
            logger.info("未设置选课时间，立即开始选课...")
            return
        
        try:
            target_time = datetime.strptime(self.grab_time, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            logger.error(f"⚠️ 时间格式错误: {self.grab_time}，使用 YYYY-MM-DD HH:MM:SS")
            return
        
        now = datetime.now()
        if target_time <= now:
            logger.info(f"⚠️ 选课时间已过，立即开始选课")
            return
        
        wait_seconds = (target_time - now).total_seconds()
        logger.info(f"📅 等待选课时间: {self.grab_time}")
        logger.info(f"⏱️ 还需等待: {int(wait_seconds)} 秒")
        
        # 在倒计时最后10秒时每秒打印一次
        while wait_seconds > 10:
            time.sleep(min(wait_seconds - 10, 60))
            now = datetime.now()
            wait_seconds = (target_time - now).total_seconds()
        
        # 最后10秒倒计时
        while wait_seconds > 0:
            logger.info(f"⏳ 倒计时: {int(wait_seconds)} 秒")
            time.sleep(1)
            now = datetime.now()
            wait_seconds = (target_time - now).total_seconds()
        
        logger.info("🚀 选课时间已到！开始选课...")
    
    def select_single_course(self, adapter: WHUAdapter, course: Dict) -> Tuple[str, bool]:
        """
        选择单个课程
        
        Args:
            adapter: WHU适配器
            course: 课程信息
            
        Returns:
            (课程信息, 是否成功)
        """
        course_id = course.get('course_id', '')
        course_name = course.get('name', '未知课程')
        
        try:
            logger.info(f"正在选课: {course_name} (ID: {course_id})")
            success, reason = adapter.select_course(course_id)
            
            if success:
                logger.info(f"✅ 选课成功: {course_name} ({reason})")
            else:
                logger.warning(f"⚠️ 选课失败: {course_name} ({reason})")
            
            return (course_name, success)
        except Exception as e:
            logger.error(f"❌ 选课异常 {course_name}: {e}")
            return (course_name, False)
    
    def run(self):
        """运行选课流程"""
        driver = None
        
        try:
            # 获取凭证
            username, password = self.get_credentials()
            
            # 启动浏览器
            driver = self.setup_driver()
            
            # 初始化验证码管理器和适配器
            logger.info("初始化验证码管理器...")
            captcha_manager = CaptchaManager(driver=driver, ocr_service='manual')
            
            logger.info("初始化WHU适配器...")
            adapter = WHUAdapter(
                username=username,
                password=password,
                driver=driver,
                captcha_manager=captcha_manager
            )
            
            # 登录
            print("\n" + "="*70)
            print("🚀 开始登录")
            print("="*70)
            
            if not adapter.login():
                logger.error("❌ 登录失败，无法选课")
                return False
            
            logger.info("✅ 登录成功")
            
            # 等待选课时间
            self.wait_for_grab_time()
            
            # 执行选课
            print("\n" + "="*70)
            print(f"📚 开始选课 - 共 {len(self.courses)} 门课程")
            print("="*70)
            
            results = {}
            
            # 单线程选课（避免冲突）
            for course in self.courses:
                course_name, success = self.select_single_course(adapter, course)
                results[course_name] = success
                
                # 延迟，避免过快触发限制
                time.sleep(1)
            
            # 输出结果统计
            print("\n" + "="*70)
            print("📊 选课结果统计")
            print("="*70)
            
            success_count = sum(1 for success in results.values() if success)
            total_count = len(results)
            
            for course_name, success in results.items():
                status = "✅" if success else "❌"
                print(f"{status} {course_name}")
            
            print("="*70)
            print(f"\n总计: {success_count}/{total_count} 门课程选课成功")
            print("="*70)
            
            if success_count == total_count:
                logger.info("🎉 全部课程选课成功！")
                return True
            else:
                logger.warning(f"⚠️ 部分课程选课失败 ({total_count - success_count} 门)")
                return False
            
        except KeyboardInterrupt:
            logger.warning("⚠️ 用户中断")
            print("\n⚠️ 用户中断")
            return False
        
        except Exception as e:
            logger.error(f"❌ 选课过程出错: {e}", exc_info=True)
            print(f"\n❌ 错误: {e}")
            return False
        
        finally:
            if driver:
                try:
                    logger.info("关闭浏览器...")
                    driver.quit()
                    logger.info("✅ 浏览器已关闭")
                except:
                    pass


def load_config(config_file: str) -> Dict:
    """加载配置文件"""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"配置文件不存在: {config_file}")
        raise
    except json.JSONDecodeError:
        logger.error(f"配置文件格式错误: {config_file}")
        raise


if __name__ == '__main__':
    # 默认配置文件
    config_file = 'whu_config.json'
    
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    
    try:
        config = load_config(config_file)
        grabber = WHUCourseGrabber(config)
        success = grabber.run()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"启动失败: {e}")
        print(f"\n❌ 启动失败: {e}")
        sys.exit(1)
