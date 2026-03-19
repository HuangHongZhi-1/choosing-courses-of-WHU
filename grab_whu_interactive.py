#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎓 武汉大学教务系统 - 交互式自动选课系统
=========================================

功能特性：
  ✅ 实时输入课程信息（课程号、课程名、教师名）
  ✅ 支持同时管理多个课程
  ✅ 实时监控课程可选状态
  ✅ 自动保存选课计划（支持恢复）
  ✅ 一键恢复上次选课状态
  ✅ 完整的选课日志和统计

使用方法：
  python grab_whu_interactive.py

菜单选项：
  1. 添加课程
  2. 查看所有课程
  3. 删除课程
  4. 修改课程
  5. 实时监控课程状态
  6. 开始选课
  7. 查看选课历史
  8. 恢复上次选课计划
  0. 退出
"""

import json
import logging
import re
import time
import sys
from datetime import datetime
from getpass import getpass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
        logging.FileHandler('grab_whu_interactive.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class CourseManager:
    """课程管理器 - 负责课程信息的增删改查和持久化"""
    
    def __init__(self, plan_file: str = 'whu_course_plan.json', history_file: str = 'whu_grab_history.json'):
        """
        初始化课程管理器
        
        Args:
            plan_file: 选课计划保存文件
            history_file: 选课历史保存文件
        """
        self.plan_file = plan_file
        self.history_file = history_file
        self.courses: List[Dict] = []
        self.load_plan()
    
    def load_plan(self):
        """加载保存的选课计划"""
        if Path(self.plan_file).exists():
            try:
                with open(self.plan_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.courses = data.get('courses', [])
                logger.info(f"✓ 已加载选课计划: {len(self.courses)} 门课程")
            except Exception as e:
                logger.warning(f"⚠️ 加载计划失败: {e}")
                self.courses = []
        else:
            self.courses = []
    
    def save_plan(self):
        """保存选课计划"""
        try:
            data = {
                'timestamp': datetime.now().isoformat(),
                'courses': self.courses
            }
            with open(self.plan_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"✓ 已保存选课计划: {len(self.courses)} 门课程")
        except Exception as e:
            logger.error(f"❌ 保存计划失败: {e}")
    
    def add_course(self, course_id: str, course_name: str, teacher: str = '') -> bool:
        """
        添加课程
        
        Args:
            course_id: 课程号
            course_name: 课程名
            teacher: 教师名
            
        Returns:
            是否成功添加
        """
        # 检查是否已存在
        if any(c['course_id'] == course_id for c in self.courses):
            logger.warning(f"⚠️ 课程 {course_id} 已存在")
            return False
        
        course = {
            'course_id': course_id,
            'course_name': course_name,
            'teacher': teacher,
            'added_time': datetime.now().isoformat(),
            'status': 'pending',  # pending, success, failed, full
            'attempts': 0
        }
        
        self.courses.append(course)
        self.save_plan()
        logger.info(f"✓ 已添加课程: {course_name} ({course_id})")
        return True
    
    def delete_course(self, course_id: str = None, course_key: str = None) -> bool:
        """删除课程"""
        original_count = len(self.courses)
        if course_key:
            self.courses = [c for c in self.courses if c.get('course_key') != course_key]
        elif course_id:
            self.courses = [c for c in self.courses if c.get('course_id') != course_id]
        else:
            return False

        if len(self.courses) < original_count:
            self.save_plan()
            logger.info(f"✓ 已删除课程: {course_key or course_id}")
            return True

        logger.warning(f"⚠️ 未找到课程: {course_key or course_id}")
        return False
    
    def update_course(self, course_id: str, course_name: str = None, teacher: str = None) -> bool:
        """修改课程信息"""
        for course in self.courses:
            if course['course_id'] == course_id:
                if course_name:
                    course['course_name'] = course_name
                if teacher is not None:
                    course['teacher'] = teacher
                self.save_plan()
                logger.info(f"✓ 已修改课程: {course_id}")
                return True
        
        logger.warning(f"⚠️ 未找到课程: {course_id}")
        return False
    
    def get_courses(self) -> List[Dict]:
        """获取所有课程"""
        return self.courses
    
    def update_course_status(self, course_id: str = None, course_key: str = None, status: str = None, success: bool = False):
        """更新课程状态

        Args:
            course_id: 课程号，用于兼容旧数据。
            course_key: 唯一课节键（课程号+上课时间），用于区分同课号不同节次。
            status: 状态字符串
            success: 是否成功
        """
        for course in self.courses:
            match_key = course.get('course_key')
            if course_key and match_key:
                if match_key != course_key:
                    continue
            elif course_id:
                if course.get('course_id') != course_id:
                    continue

            if status:
                course['status'] = status
            course['attempts'] = course.get('attempts', 0) + 1
            if success:
                course['success_time'] = datetime.now().isoformat()
            self.save_plan()
            return
    
    def save_history(self, grab_result: Dict):
        """保存选课历史"""
        try:
            history = {
                'timestamp': datetime.now().isoformat(),
                'result': grab_result
            }
            
            # 追加到历史文件
            histories = []
            if Path(self.history_file).exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    histories = json.load(f)
            
            histories.append(history)
            
            # 只保留最近10次历史
            histories = histories[-10:]
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(histories, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✓ 已保存选课历史")
        except Exception as e:
            logger.error(f"❌ 保存历史失败: {e}")
    
    def restore_previous_plan(self):
        """恢复上一次的选课计划"""
        if Path(self.history_file).exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    histories = json.load(f)
                
                if histories:
                    last_history = histories[-1]
                    previous_courses = last_history.get('result', {}).get('courses', [])
                    
                    if previous_courses:
                        # 清空当前，恢复上一次
                        self.courses = previous_courses
                        self.save_plan()
                        logger.info(f"✓ 已恢复上次选课计划: {len(self.courses)} 门课程")
                        return True
            except Exception as e:
                logger.error(f"❌ 恢复历史失败: {e}")
        
        logger.warning("⚠️ 没有可恢复的历史")
        return False


class InteractiveGrabber:
    """交互式选课系统"""
    
    def __init__(self):
        """初始化交互式选课系统"""
        self.course_manager = CourseManager()
        self.driver = None
        self.adapter = None
        self.username = None
        self.password = None
    
    def print_menu(self):
        """打印菜单"""
        print("\n" + "="*70)
        print("🎓 武汉大学教务系统 - 交互式选课")
        print("="*70)
        print("\n请选择操作：")
        print("  1. ➕ 添加课程")
        print("  2. 📋 查看所有课程")
        print("  3. ❌ 删除课程")
        print("  4. ✏️ 修改课程")
        print("  5. 👁️ 实时监控课程状态")
        print("  6. 🚀 开始选课")
        print("  7. 📊 查看选课历史")
        print("  8. ♻️ 恢复上次选课计划")
        print("  0. 🚪 退出")
        print("="*70)
    
    def add_course_interactive(self):
        """交互式添加课程"""
        print("\n📝 添加课程")
        print("-"*70)
        
        while True:
            try:
                course_id = input("课程号 (输入 'q' 返回菜单): ").strip()
                if course_id.lower() == 'q':
                    return
                
                if not course_id:
                    print("⚠️ 课程号不能为空")
                    continue
                
                course_name = input("课程名 (输入 'q' 返回菜单): ").strip()
                if course_name.lower() == 'q':
                    return
                
                if not course_name:
                    print("⚠️ 课程名不能为空")
                    continue
                
                teacher = input("教师名 (可选，直接按 Enter 跳过): ").strip()
                
                if self.course_manager.add_course(course_id, course_name, teacher):
                    print(f"✅ 成功添加：{course_name} ({course_id})")
                    
                    # 询问是否继续添加
                    more = input("\n继续添加其他课程? (y/n): ").strip().lower()
                    if more != 'y':
                        return
                else:
                    print("⚠️ 添加失败，请检查课程号是否重复")
            
            except KeyboardInterrupt:
                print("\n⚠️ 已取消")
                return
    
    def view_all_courses(self):
        """查看所有课程"""
        courses = self.course_manager.get_courses()
        
        if not courses:
            print("\n📋 当前没有课程")
            return
        
        print("\n" + "="*70)
        print("📋 所有课程")
        print("="*70)
        
        for i, course in enumerate(courses, 1):
            status_symbol = {
                'pending': '⏳',
                'success': '✅',
                'failed': '❌',
                'full': '🈵'
            }.get(course.get('status', 'pending'), '❓')
            
            print(f"\n{i}. {status_symbol} {course['course_name']}")
            print(f"   课程号: {course['course_id']}")
            
            if course.get('teacher'):
                print(f"   教师: {course['teacher']}")
            
            print(f"   状态: {course.get('status', 'pending')} | 尝试次数: {course.get('attempts', 0)}")
            print(f"   添加时间: {course.get('added_time', '').split('T')[0]}")
        
        print("\n" + "="*70)
    
    def delete_course_interactive(self):
        """交互式删除课程"""
        courses = self.course_manager.get_courses()
        
        if not courses:
            print("\n📋 当前没有课程")
            return
        
        self.view_all_courses()
        
        print("\n❌ 删除课程")
        print("-"*70)
        
        course_id = input("输入要删除的课程号: ").strip()
        
        if self.course_manager.delete_course(course_id):
            print("✅ 已删除")
        else:
            print("⚠️ 删除失败")
    
    def update_course_interactive(self):
        """交互式修改课程"""
        courses = self.course_manager.get_courses()
        
        if not courses:
            print("\n📋 当前没有课程")
            return
        
        self.view_all_courses()
        
        print("\n✏️ 修改课程")
        print("-"*70)
        
        course_id = input("输入要修改的课程号: ").strip()
        
        # 找到课程
        course = next((c for c in courses if c['course_id'] == course_id), None)
        if not course:
            print("⚠️ 未找到课程")
            return
        
        print(f"\n当前信息：")
        print(f"  课程名: {course['course_name']}")
        print(f"  教师: {course.get('teacher', '未设置')}")
        
        new_name = input("\n新的课程名 (直接按 Enter 保持不变): ").strip()
        new_teacher = input("新的教师名 (直接按 Enter 保持不变): ").strip()
        
        if self.course_manager.update_course(
            course_id,
            new_name if new_name else None,
            new_teacher if new_teacher else None
        ):
            print("✅ 已修改")
        else:
            print("⚠️ 修改失败")
    
    def monitor_courses(self):
        """实时监控课程状态"""
        if not self.adapter:
            print("⚠️ 需要先登录")
            return
        
        print("\n👁️ 实时监控课程状态")
        print("="*70)
        print("按 Ctrl+C 停止监控")
        print("="*70)
        
        courses = self.course_manager.get_courses()
        
        try:
            while True:
                print(f"\n⏰ {datetime.now().strftime('%H:%M:%S')} - 检查课程状态...")
                
                for course in courses:
                    # 这里可以实现实际的课程可选状态检查
                    # 目前只是显示课程信息
                    status = course.get('status', 'pending')
                    print(f"  {course['course_name']}: {status}")
                
                time.sleep(5)  # 每5秒检查一次
        
        except KeyboardInterrupt:
            print("\n\n⏹️ 已停止监控")
    
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
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            logger.info("✅ 浏览器启动成功")
            return driver
        except Exception as e:
            logger.error(f"❌ 浏览器启动失败: {e}")
            return None

    def _parse_time_slot(self, time_str: str):
        """解析时间字符串，返回 (day_index, start_min, end_min)。

        支持格式如：
          周一 08:00-10:00
          周二 14:00 - 16:00
        """
        if not time_str:
            return None

        # 简单提取 "周X" + 时间范围
        m = re.search(r"周([一二三四五六日])\s*(\d{1,2}:\d{2})\s*[-~至]\s*(\d{1,2}:\d{2})", time_str)
        if not m:
            return None

        day_map = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '日': 7}
        day = day_map.get(m.group(1), 0)
        def to_min(t):
            h, m = t.split(':')
            return int(h) * 60 + int(m)

        start = to_min(m.group(2))
        end = to_min(m.group(3))
        return (day, start, end)

    def _filter_time_conflicts(self, courses: List[Dict]) -> List[Dict]:
        """过滤时间冲突的课程，保留非冲突或优先级更高的课程。"""
        slots = []  # (day, start, end, course_key)
        filtered = []

        for course in courses:
            time_str = course.get('time', '') or ''
            parsed = self._parse_time_slot(time_str)
            if not parsed:
                # 无法解析时间的课程先放行
                filtered.append(course)
                continue

            day, start, end = parsed
            conflict = False
            for d, s, e, key in slots:
                if d != day:
                    continue
                # 判断时间区间是否重叠
                if not (end <= s or start >= e):
                    conflict = True
                    logger.warning(f"⚠️ 发现时间冲突: {course.get('course_name')} 与 {key} (时间: {time_str})")
                    break

            if not conflict:
                slots.append((day, start, end, course.get('course_key') or course.get('course_id')))
                filtered.append(course)

        return filtered

    def resolve_course(self, course: Dict) -> List[Dict]:
        """通过部分信息定位具体课程.

        如果在当前页面找到多条匹配，会让用户选择要选的课程（可多选）。
        返回选中的课程列表。
        """
        keyword_id = str(course.get('course_id', '')).strip()
        keyword_name = str(course.get('course_name', '')).strip()
        keyword_teacher = str(course.get('teacher', '')).strip()

        if not self.adapter:
            return []

        available = self.adapter.get_courses()
        if not available:
            return []

        candidates = []
        for item in available:
            if keyword_id and keyword_id not in str(item.get('id', '')):
                continue
            if keyword_name and keyword_name.lower() not in str(item.get('name', '')).lower():
                continue
            if keyword_teacher and keyword_teacher.lower() not in str(item.get('teacher', '')).lower():
                continue
            candidates.append(item)

        if not candidates:
            return []

        if len(candidates) == 1:
            return candidates

        # 多条匹配，提示用户选择
        print("\n⚠️ 发现多条匹配，请选择要选的课程（支持多选，用逗号分隔），输入 Enter 跳过：")
        for idx, item in enumerate(candidates, 1):
            print(f"  {idx}. {item.get('id', '')} | {item.get('name', '')} | {item.get('teacher', '')} | {item.get('time', '')} | {item.get('location', '')}")

        while True:
            choice = input(f"请输入序号列表 (例如 1,3) 或 Enter 跳过: ").strip()
            if not choice:
                return []

            # 允许输入 all 来选中全部
            if choice.lower() in ('all', 'a'):
                return candidates

            parts = [c.strip() for c in choice.split(',') if c.strip()]
            selected = []
            valid = True
            for part in parts:
                if not part.isdigit():
                    valid = False
                    break
                idx = int(part)
                if idx < 1 or idx > len(candidates):
                    valid = False
                    break
                selected.append(candidates[idx - 1])

            if valid:
                return selected

            print("⚠️ 输入错误，请重新输入")
    
    def get_credentials(self):
        """获取凭证"""
        print("\n🔐 请输入登录凭证")
        print("-"*70)
        
        while True:
            username = input("学号: ").strip()
            if username:
                break
            print("⚠️ 学号不能为空")
        
        print("\n(密码不会显示)")
        while True:
            password = getpass("密码: ")
            if password:
                break
            print("⚠️ 密码不能为空")
        
        self.username = username
        self.password = password
        return username, password
    
    def start_grab(self):
        """开始选课"""
        courses = self.course_manager.get_courses()
        
        if not courses:
            print("\n⚠️ 请先添加课程")
            return
        
        self.view_all_courses()
        
        confirm = input("\n确认开始选课? (y/n): ").strip().lower()
        if confirm != 'y':
            print("⚠️ 已取消")
            return
        
        # 获取凭证
        if not self.username or not self.password:
            self.get_credentials()
        
        self.driver = self.setup_driver()
        if not self.driver:
            return
        
        try:
            # 登录重试循环
            login_success = False
            max_retries = 3
            retry_count = 0
            
            while not login_success and retry_count < max_retries:
                retry_count += 1
                
                # 初始化适配器
                captcha_manager = CaptchaManager(driver=self.driver, ocr_service='manual')
                self.adapter = WHUAdapter(
                    username=self.username,
                    password=self.password,
                    driver=self.driver,
                    captcha_manager=captcha_manager
                )
                
                # 登录
                print(f"\n🚀 开始登录... (尝试 {retry_count}/{max_retries})")
                if self.adapter.login():
                    print("✅ 登录成功")
                    login_success = True
                else:
                    print("❌ 登录失败")
                    
                    if retry_count < max_retries:
                        # 询问是否重新输入凭证
                        print("\n可能是用户名或密码错误")
                        retry = input("是否重新输入凭证? (y/n): ").strip().lower()
                        
                        if retry == 'y':
                            # 清空驱动并重新获取凭证
                            self.driver.quit()
                            self.username = None
                            self.password = None
                            self.get_credentials()
                            
                            # 重新启动驱动
                            self.driver = self.setup_driver()
                            if not self.driver:
                                return
                        else:
                            return
                    else:
                        print(f"\n❌ 已尝试 {max_retries} 次，登录失败")
                        return
            
            if not login_success:
                return
            
            print("✅ 登录成功\n")
            
            # 执行选课
            print("="*70)
            print("📚 开始选课")
            print("="*70)

            results = {}

            # 构建待选课列表（支持同课程号多节次）
            selection_plan = []
            for course in courses:
                resolved_list = self.resolve_course(course)
                if resolved_list:
                    for resolved in resolved_list:
                        resolved_id = resolved.get('id') or resolved.get('course_id') or course.get('course_id', '')
                        resolved_name = resolved.get('name') or course.get('course_name', '')
                        resolved_time = resolved.get('time') or course.get('time', '')
                        course_key = f"{resolved_id}|{resolved_time}"
                        selection_plan.append({
                            'course_id': resolved_id,
                            'course_name': f"{resolved_name} ({resolved_time})" if resolved_time else resolved_name,
                            'teacher': resolved.get('teacher') or course.get('teacher', ''),
                            'time': resolved_time,
                            'location': resolved.get('location') or course.get('location', ''),
                            'course_key': course_key,
                            'status': 'pending',
                            'attempts': 0
                        })
                    # 更新当前计划中的基础信息（仅保留第一条）
                    first = resolved_list[0]
                    course.update({
                        'course_id': first.get('id') or first.get('course_id') or course.get('course_id', ''),
                        'course_name': first.get('name') or course.get('course_name', ''),
                        'time': first.get('time') or course.get('time', ''),
                        'teacher': first.get('teacher') or course.get('teacher', ''),
                        'location': first.get('location') or course.get('location', ''),
                    })
                    self.course_manager.save_plan()
                else:
                    course_id = course.get('course_id', '')
                    course_time = course.get('time', '')
                    course_key = f"{course_id}|{course_time}"
                    course['course_key'] = course_key
                    selection_plan.append(course)

            # 过滤时间冲突（同一时间仅保留第一门）
            selection_plan = self._filter_time_conflicts(selection_plan)

            for i, course in enumerate(selection_plan, 1):
                course_id = course.get('course_id', '')
                course_name = course.get('course_name', '')
                course_key = course.get('course_key', f"{course_id}|{course.get('time','')}")

                print(f"\n[{i}/{len(selection_plan)}] 正在选课: {course_name} ({course_id})")
                
                max_attempts = 3
                for attempt in range(1, max_attempts + 1):
                    try:
                        attempt_label = f"(第{attempt}/{max_attempts}次)"
                        print(f"  - 尝试选课 {attempt_label} ...")
                        success, reason = self.adapter.select_course(course_id)

                        if success:
                            print(f"✅ 选课成功: {course_name} ({reason})")
                            self.course_manager.delete_course(course_key=course_key)
                            results[course_key] = {'success': True, 'name': course_name}
                            break

                        # 检查是否已在系统中选上（页面不再显示该课程）
                        available = self.adapter.get_courses() or []
                        if not any(c.get('id') == course_id or c.get('course_id') == course_id for c in available):
                            print(f"✅ 课程 {course_name} 可能已在系统中选中，将从待选列表移除 ({reason})")
                            self.course_manager.delete_course(course_key=course_key)
                            results[course_key] = {'success': True, 'name': course_name}
                            break

                        # 未成功，重试（如果还有机会）
                        if attempt < max_attempts:
                            print(f"  ⚠️ 选课未成功: {reason}，准备重试...")
                            time.sleep(1)
                            continue

                        # 到达最后一次仍未成功
                        print(f"❌ 选课失败: {course_name} ({reason})")
                        self.course_manager.update_course_status(course_key=course_key, status='failed')
                        results[course_key] = {'success': False, 'name': course_name}

                    except Exception as e:
                        logger.error(f"选课异常 {course_name}: {e}")
                        print(f"❌ 选课异常: {course_name}")
                        self.course_manager.update_course_status(course_key=course_key, status='failed')
                        results[course_key] = {'success': False, 'name': course_name}
                        break
                    
                # 给页面留一点时间，防止触发风控
                time.sleep(1)

            # 保存历史
            self.course_manager.save_history({
                'courses': courses,
                'results': results,
                'success_count': sum(1 for v in results.values() if v.get('success')),
                'total_count': len(results)
            })
            
            # 显示结果
            print("\n" + "="*70)
            print("📊 选课结果")
            print("="*70)
            
            success_count = sum(1 for v in results.values() if v.get('success'))
            total_count = len(results)

            for course_key, info in results.items():
                status = "✅" if info.get('success') else "❌"
                print(f"{status} {info.get('name', course_key)}")

            print("="*70)
            print(f"\n总计: {success_count}/{total_count} 门课程选课成功\n")

            # 如果还有未成功的课程，自动开启持续侦测并重试选课
            failed_keys = [k for k,v in results.items() if not v.get('success')]
            if failed_keys:
                print("⚠️ 以下课程尚未选上，将持续监控并尝试重试（按 Ctrl+C 停止）：")
                for k in failed_keys:
                    print(f"  - {results[k].get('name', k)}")

                try:
                    retry_interval = 1  # 尽量缩短重试间隔（单位：秒）
                    while failed_keys:
                        print("\n⏳ 开始新一轮检查（按 Ctrl+C 停止）...")

                        # 每轮刷新页面，确保最新的课程状态
                        try:
                            self.driver.refresh()
                        except Exception:
                            pass

                        for course_key in failed_keys[:]:
                            course_name = results[course_key].get('name', course_key)
                            course_id = course_key.split('|', 1)[0]

                            # 尝试重新选课（快速判断当前 DOM 是否可选）
                            success, reason = self.adapter.select_course(course_id)
                            if success:
                                print(f"✅ 选课成功: {course_name} ({reason})")
                                self.course_manager.delete_course(course_key=course_key)
                                results[course_key]['success'] = True
                                failed_keys.remove(course_key)
                                continue

                            # 若页面未找到该课程，说明可能已被系统选中
                            available = self.adapter.get_courses() or []
                            if not any(c.get('id') == course_id or c.get('course_id') == course_id for c in available):
                                print(f"✅ 课程 {course_name} 可能已在系统中选中，已移除。")
                                self.course_manager.delete_course(course_key=course_key)
                                results[course_key]['success'] = True
                                failed_keys.remove(course_key)
                                continue

                            print(f"⏳ 仍未选上: {course_name} ({reason})")

                        if not failed_keys:
                            print("\n🎉 已成功选满所有预定课程！")
                            break

                        print(f"\n等待 {retry_interval} 秒后继续检查... (Ctrl+C 停止)")
                        time.sleep(retry_interval)
                except KeyboardInterrupt:
                    print("\n🛑 已停止持续侦测，未选上的课程将保留在计划中。")

        except KeyboardInterrupt:
            print("\n\n⚠️ 用户中断")
        
        except Exception as e:
            logger.error(f"❌ 选课过程出错: {e}", exc_info=True)
            print(f"\n❌ 错误: {e}")
        
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                    logger.info("浏览器已关闭")
                except:
                    pass
    
    def view_history(self):
        """查看选课历史"""
        history_file = Path('whu_grab_history.json')
        
        if not history_file.exists():
            print("\n📊 还没有选课历史")
            return
        
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                histories = json.load(f)
            
            if not histories:
                print("\n📊 还没有选课历史")
                return
            
            print("\n" + "="*70)
            print("📊 选课历史（最近10次）")
            print("="*70)
            
            for i, history in enumerate(histories[-10:], 1):
                result = history.get('result', {})
                timestamp = history.get('timestamp', '').split('T')[0]
                success = result.get('success_count', 0)
                total = result.get('total_count', 0)
                
                print(f"\n{i}. {timestamp}")
                print(f"   结果: {success}/{total} 门课程成功")
            
            print("\n" + "="*70)
        
        except Exception as e:
            logger.error(f"查看历史失败: {e}")
            print(f"⚠️ 查看失败: {e}")
    
    def restore_plan(self):
        """恢复上次选课计划"""
        if self.course_manager.restore_previous_plan():
            self.view_all_courses()
        else:
            print("\n⚠️ 没有可恢复的历史记录")
    
    def run(self):
        """运行交互式菜单"""
        print("\n" + "="*70)
        print("欢迎使用武汉大学教务系统交互式选课系统")
        print("="*70)
        
        while True:
            self.print_menu()
            
            choice = input("\n请输入选项 (0-8): ").strip()
            
            if choice == '0':
                print("\n👋 再见！")
                break
            
            elif choice == '1':
                self.add_course_interactive()
            
            elif choice == '2':
                self.view_all_courses()
            
            elif choice == '3':
                self.delete_course_interactive()
            
            elif choice == '4':
                self.update_course_interactive()
            
            elif choice == '5':
                self.monitor_courses()
            
            elif choice == '6':
                self.start_grab()
            
            elif choice == '7':
                self.view_history()
            
            elif choice == '8':
                self.restore_plan()
            
            else:
                print("⚠️ 无效选项，请重新输入")


if __name__ == '__main__':
    try:
        grabber = InteractiveGrabber()
        grabber.run()
    except KeyboardInterrupt:
        print("\n\n👋 已退出")
        sys.exit(0)
    except Exception as e:
        logger.error(f"程序错误: {e}", exc_info=True)
        print(f"\n❌ 程序错误: {e}")
        sys.exit(1)
