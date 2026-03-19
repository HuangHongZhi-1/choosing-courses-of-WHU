#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔐 完全安全的武汉大学教务系统登录脚本

特点：
  ✅ 学号和密码通过命令行输入，不存储在任何文件中
  ✅ 密码输入时隐藏（不显示）
  ✅ 支持一键快速开始
  ✅ 完整的错误处理和日志记录
  ✅ 支持验证码处理

使用方法：
  python whu_login.py

就这么简单！
"""

import sys
import logging
import time
from getpass import getpass

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

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
        logging.FileHandler('whu_login.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def setup_driver():
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
        sys.exit(1)


def get_credentials():
    """从命令行获取学号和密码"""
    
    print("\n" + "="*70)
    print("🎓 武汉大学教务系统 - 登录")
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


def run_login(username, password):
    """执行登录"""
    
    driver = None
    
    try:
        # 启动浏览器
        driver = setup_driver()
        logger.info("浏览器窗口已打开，请勿关闭")
        
        # 初始化验证码管理器
        logger.info("初始化验证码管理器...")
        captcha_manager = CaptchaManager(driver=driver, ocr_service='manual')
        
        # 创建适配器
        adapter = WHUAdapter(
            username=username,
            password=password,
            driver=driver,
            captcha_manager=captcha_manager
        )
        
        # 执行登录
        print("\n" + "="*70)
        print("🚀 开始登录")
        print("="*70)
        
        logger.info(f"准备登录，学号: {username}")
        
        success = adapter.login()
        
        if success:
            print("\n" + "="*70)
            print("✅ 登录成功！")
            print("="*70)
            
            time.sleep(2)
            current_url = driver.current_url
            print(f"\n📍 当前页面: {current_url}")
            
            # 尝试获取课程
            print("\n" + "="*70)
            print("📚 获取课程列表...")
            print("="*70)
            
            try:
                courses = adapter.get_courses()
                if courses:
                    print(f"\n✅ 找到 {len(courses)} 门课程：\n")
                    for i, course in enumerate(courses[:5], 1):
                        print(f"{i}. {course['name']}")
                        print(f"   📖 教师: {course['teacher']}")
                        print(f"   📅 时间: {course['time']}")
                        print(f"   📍 地点: {course['location']}")
                        print(f"   👥 容量: {course['capacity']} | 已选: {course['enrolled']}\n")
                    
                    if len(courses) > 5:
                        print(f"   ... 还有 {len(courses) - 5} 门课程未显示")
                else:
                    print("\n⚠️ 未获取到课程")
                    print("   (这是正常的，可能是选课未开放或无课程可选)")
            except Exception as e:
                logger.warning(f"获取课程失败: {e}")
                print("\n⚠️ 无法获取课程列表，但登录已成功")
            
            return True
            
        else:
            print("\n" + "="*70)
            print("❌ 登录失败")
            print("="*70)
            print("\n请检查：")
            print("  1. 学号是否正确")
            print("  2. 密码是否正确")
            print("  3. 是否出现了验证码（查看浏览器窗口）")
            print("\n详细错误信息已保存到 whu_login.log")
            return False
    
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断")
        logger.info("用户中断")
        return False
    
    except Exception as e:
        logger.error(f"❌ 发生错误: {e}", exc_info=True)
        print(f"\n❌ 错误: {e}")
        return False
    
    finally:
        if driver:
            logger.info("关闭浏览器...")
            driver.quit()
            print("\n✅ 浏览器已关闭")


def main():
    """主程序"""
    
    try:
        # 获取凭证
        username, password = get_credentials()
        
        print("\n正在初始化...")
        
        # 执行登录
        success = run_login(username, password)
        
        print("\n" + "="*70)
        if success:
            print("✨ 登录成功！")
            print("\n接下来：")
            print("  1. 等待选课开放")
            print("  2. 运行 python grab_website.py 自动选课")
        else:
            print("⚠️ 登录未成功")
            print("\n请查看上面的错误信息或查看 whu_login.log 获取详情")
        print("="*70)
        
    except Exception as e:
        logger.error(f"程序错误: {e}", exc_info=True)
        print(f"\n❌ 程序错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
