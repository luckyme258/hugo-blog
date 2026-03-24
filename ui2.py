import flet as ft
from datetime import datetime, timezone, timedelta
import os
import re
import yaml
from pathlib import Path
import threading
import time
from collections import defaultdict
import asyncio

# 配置路径 - 脚本所在目录
SCRIPT_DIR = Path(__file__).parent.absolute()
CONTENT_DIR = SCRIPT_DIR / "content" / "posts"
TAGS_FILE = CONTENT_DIR / "tags.md"

class TagCategoryScanner:
    """标签和分类扫描器，在后台线程中运行"""
    
    def __init__(self, editor):
        self.editor = editor
        self.scanning = False
        self.last_scan_time = None
        self.scan_interval = 60  # 扫描间隔（秒）
        
    def start_background_scan(self):
        """启动后台扫描线程"""
        def scan_loop():
            while True:
                try:
                    # 等待一段时间后执行扫描
                    time.sleep(5)  # 启动后等待5秒
                    self.scan_tags_and_categories()
                    
                    # 每隔 scan_interval 秒扫描一次
                    time.sleep(self.scan_interval)
                except Exception as e:
                    print(f"后台扫描错误: {e}")
                    time.sleep(10)  # 出错后等待10秒再重试
        
        # 启动后台线程
        scan_thread = threading.Thread(target=scan_loop, daemon=True)
        scan_thread.start()
        print("后台扫描线程已启动")
    
    def scan_tags_and_categories(self):
        """扫描所有文章的 tags 和 categories"""
        if self.scanning:
            print("扫描进行中，跳过本次扫描")
            return
        
        self.scanning = True
        print(f"开始扫描 tags 和 categories...")
        
        try:
            # 收集所有 tags 和 categories
            all_tags = set()
            all_categories = set()
            tag_count = defaultdict(int)
            category_count = defaultdict(int)
            
            # 获取所有 .md 文件（排除 tags.md 本身）
            md_files = [f for f in CONTENT_DIR.glob("*.md") if f.name != "tags.md"]
            
            for md_file in md_files:
                try:
                    with open(md_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    front_matter, _ = self.editor.parse_front_matter(content)
                    
                    # 提取 tags
                    tags = front_matter.get('tags', [])
                    if isinstance(tags, str):
                        tags = [tags]
                    elif not isinstance(tags, list):
                        tags = []
                    
                    for tag in tags:
                        if tag and tag.strip():
                            clean_tag = tag.strip()
                            all_tags.add(clean_tag)
                            tag_count[clean_tag] += 1
                    
                    # 提取 categories
                    categories = front_matter.get('categories', [])
                    if isinstance(categories, str):
                        categories = [categories]
                    elif not isinstance(categories, list):
                        categories = []
                    
                    for category in categories:
                        if category and category.strip():
                            clean_category = category.strip()
                            all_categories.add(clean_category)
                            category_count[clean_category] += 1
                            
                except Exception as e:
                    print(f"处理文件 {md_file.name} 时出错: {e}")
            
            # 生成 tags.md 内容
            tags_md_content = self.generate_tags_md(all_tags, all_categories, tag_count, category_count)
            
            # 写入文件
            with open(TAGS_FILE, 'w', encoding='utf-8') as f:
                f.write(tags_md_content)
            
            self.last_scan_time = datetime.now()
            print(f"扫描完成，找到 {len(all_tags)} 个标签，{len(all_categories)} 个分类")
            print(f"已写入文件: {TAGS_FILE}")
            
            # 更新 UI 状态（通过回调）
            if self.editor.page:
                self.editor.page.run_coroutine_threadsafe(
                    self.update_ui_status(len(all_tags), len(all_categories))
                )
                
        except Exception as e:
            print(f"扫描失败: {e}")
        finally:
            self.scanning = False
    
    def generate_tags_md(self, all_tags, all_categories, tag_count, category_count):
        """生成 tags.md 文件内容"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        content = f"""# 文章标签和分类索引

> 最后更新: {timestamp}
> 总计: {len(all_tags)} 个标签, {len(all_categories)} 个分类

---

## 📁 分类列表

"""
        
        # 添加分类列表（按使用次数排序）
        sorted_categories = sorted(category_count.items(), key=lambda x: x[1], reverse=True)
        for category, count in sorted_categories:
            content += f"- **{category}** ({count} 篇文章)\n"
        
        if not sorted_categories:
            content += "- *暂无分类*\n"
        
        content += f"""

## 🏷️ 标签列表

"""
        
        # 添加标签列表（按使用次数排序）
        sorted_tags = sorted(tag_count.items(), key=lambda x: x[1], reverse=True)
        for tag, count in sorted_tags:
            content += f"- **{tag}** ({count} 篇文章)\n"
        
        if not sorted_tags:
            content += "- *暂无标签*\n"
        
        content += f"""

---

## 📊 统计信息

- **文章总数**: {len([f for f in CONTENT_DIR.glob("*.md") if f.name != "tags.md"])}
- **标签总数**: {len(all_tags)}
- **分类总数**: {len(all_categories)}
- **最热门标签**: {self.get_most_popular(tag_count)}
- **最热门分类**: {self.get_most_popular(category_count)}

---

*此文件由 Hugo 文章管理器自动生成，请勿手动编辑*
"""
        
        return content
    
    def get_most_popular(self, count_dict):
        """获取最热门的项目"""
        if not count_dict:
            return "暂无"
        most_popular = max(count_dict.items(), key=lambda x: x[1])
        return f"{most_popular[0]} ({most_popular[1]} 篇)"
    
    def update_ui_status(self, tag_count, category_count):
        """更新 UI 状态"""
        if self.editor.status_text:
            self.editor.status_text.value = f"✅ 后台扫描完成 - 找到 {tag_count} 个标签, {category_count} 个分类"
            self.editor.status_text.color = ft.Colors.GREEN
            self.editor.page.update()
            
            # 3秒后恢复状态
            def reset_status():
                time.sleep(3)
                if self.editor.status_text.value == f"✅ 后台扫描完成 - 找到 {tag_count} 个标签, {category_count} 个分类":
                    self.editor.page.run_coroutine_threadsafe(
                        self.clear_status()
                    )
            
            reset_thread = threading.Thread(target=reset_status, daemon=True)
            reset_thread.start()
    
    def clear_status(self):
        """清除状态消息"""
        if self.editor.status_text:
            self.editor.status_text.value = ""
            self.editor.page.update()
    
    def force_scan(self):
        """强制立即扫描"""
        def scan():
            time.sleep(0.5)  # 稍微延迟，避免阻塞 UI
            self.scan_tags_and_categories()
        
        scan_thread = threading.Thread(target=scan, daemon=True)
        scan_thread.start()
        if self.editor.status_text:
            self.editor.status_text.value = "🔄 开始扫描标签和分类..."
            self.editor.status_text.color = ft.Colors.BLUE
            self.editor.page.update()


class HugoEditor:
    def __init__(self, page: ft.Page):
        self.page = page
        self.current_file = None  # 当前编辑的文件路径
        self.current_filename = None  # 当前编辑的文件名
        
        # 确保目录存在
        print(f"脚本目录: {SCRIPT_DIR}")
        print(f"文章目录: {CONTENT_DIR}")
        
        # 如果 content/posts 不存在，创建它
        if not CONTENT_DIR.exists():
            print(f"创建目录: {CONTENT_DIR}")
            CONTENT_DIR.mkdir(parents=True, exist_ok=True)
        
        self.setup_ui()
        self.load_article_list()
        
        # 初始化扫描器并启动后台扫描
        self.scanner = TagCategoryScanner(self)
        self.scanner.start_background_scan()
        
        # 首次扫描（延迟执行，避免影响 UI 启动）
        self.page.add(ft.Text("正在启动扫描器...", size=12, color=ft.Colors.GREY))
        self.page.update()
        self.scanner.force_scan()
    
    def get_current_time_with_tz(self):
        """获取当前时间，带 +08:00 时区"""
        tz = timezone(timedelta(hours=8))
        current_time = datetime.now(tz)
        return current_time.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    
    def parse_front_matter(self, content):
        """解析 Front Matter，返回 (front_matter_dict, body)"""
        if not content.startswith('---'):
            return {}, content
        
        # 找到第二个 ---
        parts = content.split('---', 2)
        if len(parts) < 3:
            return {}, content
        
        front_matter_str = parts[1].strip()
        body = parts[2].strip()
        
        try:
            front_matter = yaml.safe_load(front_matter_str)
            if front_matter is None:
                front_matter = {}
            return front_matter, body
        except Exception as e:
            print(f"解析 Front Matter 失败: {e}")
            return {}, content
    
    def format_front_matter(self, front_matter):
        """将字典格式化为 YAML Front Matter 字符串"""
        lines = ['---']
        
        # 按固定顺序输出
        if 'date' in front_matter:
            lines.append(f"date: '{front_matter['date']}'")
        if 'draft' in front_matter:
            lines.append(f"draft: {str(front_matter['draft']).lower()}")
        if 'title' in front_matter:
            # 处理标题中的引号
            title = front_matter['title'].replace("'", "\\'")
            lines.append(f"title: '{title}'")
        if 'categories' in front_matter and front_matter['categories']:
            # 处理 categories（可能是列表或字符串）
            cats = front_matter['categories']
            if isinstance(cats, list):
                lines.append(f"categories: {cats}")
            else:
                lines.append(f"categories: ['{cats}']")
        if 'tags' in front_matter and front_matter['tags']:
            tags = front_matter['tags']
            if isinstance(tags, list):
                lines.append(f"tags: {tags}")
            else:
                lines.append(f"tags: ['{tags}']")
        
        lines.append('---')
        lines.append('')
        return '\n'.join(lines)
    
    def setup_ui(self):
        """设置界面"""
        self.page.title = "Hugo 文章管理器"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.window_width = 1300
        self.page.window_height = 800
        self.page.padding = 20
        
        # 左侧：文章列表
        self.article_list = ft.ListView(
            expand=True,
            spacing=5,
            padding=10,
            height=600
        )
        
        # 右侧编辑区
        self.title_input = ft.TextField(
            label="文章标题 *",
            hint_text="例如：思考",
            width=600,
            autofocus=True
        )
        
        self.categories_input = ft.TextField(
            label="分类",
            hint_text="多个分类用英文逗号分隔，例如：教程, 博客搭建",
            width=600,
            value="未分类"
        )
        
        self.tags_input = ft.TextField(
            label="标签",
            hint_text="多个标签用英文逗号分隔，例如：Hugo, Lightbi, 入门",
            width=600,
            value="Hugo"
        )
        
        self.draft_switch = ft.Switch(
            label="草稿模式",
            value=True,
            tooltip="开启后文章不会发布，方便预览"
        )
        
        self.content_input = ft.TextField(
            label="文章内容 (支持 Markdown 和 Hugo 短代码)",
            multiline=True,
            min_lines=20,
            max_lines=30,
            expand=True,
            hint_text="""例如：
欢迎来到我的博客！

这是用 Lightbi 主题搭建的第一篇文章。主题看起来简洁现代，我很喜欢。

{{< bilibili "BV1634y1t7xR" >}}"""
        )
        
        self.status_text = ft.Text("", color=ft.Colors.GREEN)
        
        # 按钮
        self.new_btn = ft.ElevatedButton("➕ 新建文章", icon=ft.Icons.ADD, on_click=self.new_article)
        self.save_btn = ft.ElevatedButton("💾 保存文章", icon=ft.Icons.SAVE, on_click=self.save_article)
        self.refresh_btn = ft.OutlinedButton("🔄 刷新列表", icon=ft.Icons.REFRESH, on_click=self.refresh_list)
        self.scan_btn = ft.OutlinedButton("🏷️ 立即扫描标签", icon=ft.Icons.TAG, on_click=self.force_scan)
        self.delete_btn = ft.ElevatedButton("🗑️ 删除文章", icon=ft.Icons.DELETE, on_click=self.delete_article, color=ft.Colors.RED, bgcolor=ft.Colors.RED_50)
        
        # 右侧布局
        right_column = ft.Column([
            ft.Text("📝 文章编辑", size=20, weight=ft.FontWeight.BOLD),
            self.title_input,
            ft.Row([self.categories_input, self.tags_input], spacing=20),
            ft.Row([self.draft_switch], alignment=ft.MainAxisAlignment.START),
            ft.Text("内容", weight=ft.FontWeight.BOLD),
            ft.Container(self.content_input, expand=True),
            ft.Row([self.new_btn, self.save_btn, self.refresh_btn, self.scan_btn, self.delete_btn], spacing=10),
            self.status_text
        ], spacing=15, expand=True)
        
        # 左右分屏
        self.page.add(
            ft.Row([
                ft.Container(
                    content=ft.Column([
                        ft.Text("📁 文章列表", size=20, weight=ft.FontWeight.BOLD),
                        ft.Text(f"路径: {CONTENT_DIR}", size=10, color=ft.Colors.GREY),
                        ft.Divider(),
                        self.article_list
                    ], spacing=10),
                    width=350,
                    border=ft.border.all(1, ft.Colors.GREY_300),
                    border_radius=10,
                    padding=10
                ),
                ft.Container(
                    content=right_column,
                    expand=True,
                    border=ft.border.all(1, ft.Colors.GREY_300),
                    border_radius=10,
                    padding=20
                )
            ], expand=True, spacing=20)
        )
    
    def load_article_list(self):
        """加载文章列表"""
        print(f"开始加载文章列表，目录: {CONTENT_DIR}")
        self.article_list.controls.clear()
        
        # 检查目录是否存在
        if not CONTENT_DIR.exists():
            print(f"目录不存在: {CONTENT_DIR}")
            self.article_list.controls.append(
                ft.Text(f"目录不存在: {CONTENT_DIR}", color=ft.Colors.RED, italic=True)
            )
            self.page.update()
            return
        
        # 获取所有 .md 文件（排除 tags.md）
        md_files = [f for f in CONTENT_DIR.glob("*.md") if f.name != "tags.md"]
        print(f"找到 {len(md_files)} 个 Markdown 文件（排除 tags.md）")
        
        if not md_files:
            self.article_list.controls.append(
                ft.Text("📭 暂无文章，点击「新建文章」开始", color=ft.Colors.GREY, italic=True)
            )
            self.page.update()
            return
        
        # 按修改时间倒序排列
        md_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        for md_file in md_files:
            try:
                print(f"读取文件: {md_file.name}")
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                front_matter, _ = self.parse_front_matter(content)
                title = front_matter.get('title', md_file.stem)
                
                # 获取文件信息
                mtime = datetime.fromtimestamp(md_file.stat().st_mtime)
                mtime_str = mtime.strftime("%Y-%m-%d %H:%M")
                
                # 获取文件大小
                size = md_file.stat().st_size
                size_str = f"{size} 字节" if size < 1024 else f"{size/1024:.1f} KB"
                
                # 判断是否草稿
                is_draft = front_matter.get('draft', False)
                draft_badge = "📝" if is_draft else "✅"
                
                # 创建列表项
                list_item = ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Text(f"{draft_badge} {title}", weight=ft.FontWeight.BOLD, size=14, expand=True),
                            ft.Text(size_str, size=10, color=ft.Colors.GREY)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Text(md_file.name, size=10, color=ft.Colors.GREY),
                        ft.Text(f"修改: {mtime_str}", size=10, color=ft.Colors.GREY)
                    ], spacing=2),
                    padding=10,
                    bgcolor=ft.Colors.WHITE,
                    border_radius=5,
                    on_click=lambda e, path=md_file: self.load_article(path),
                    ink=True,
                    data=md_file
                )
                self.article_list.controls.append(list_item)
                
            except Exception as e:
                print(f"读取文件失败 {md_file.name}: {e}")
                self.article_list.controls.append(
                    ft.Text(f"❌ 读取失败: {md_file.name}", color=ft.Colors.RED, size=12)
                )
        
        print(f"列表加载完成，共 {len(self.article_list.controls)} 项")
        self.page.update()
    
    def load_article(self, file_path):
        """加载文章到编辑器"""
        try:
            print(f"加载文章: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            front_matter, body = self.parse_front_matter(content)
            
            # 填充表单
            self.title_input.value = front_matter.get('title', '')
            
            # 处理 categories
            categories = front_matter.get('categories', ['未分类'])
            if isinstance(categories, list):
                self.categories_input.value = ', '.join(categories) if categories else '未分类'
            else:
                self.categories_input.value = str(categories) if categories else '未分类'
            
            # 处理 tags
            tags = front_matter.get('tags', ['Hugo'])
            if isinstance(tags, list):
                self.tags_input.value = ', '.join(tags) if tags else 'Hugo'
            else:
                self.tags_input.value = str(tags) if tags else 'Hugo'
            
            self.draft_switch.value = front_matter.get('draft', True)
            self.content_input.value = body
            
            self.current_file = file_path
            self.current_filename = file_path.name
            
            # 高亮当前选中的文章
            self.highlight_current_article(file_path)
            
            self.status_text.value = f"✅ 已加载: {file_path.name}"
            self.status_text.color = ft.Colors.GREEN
            
            self.page.update()
            
        except Exception as e:
            print(f"加载失败: {e}")
            self.status_text.value = f"❌ 加载失败: {str(e)}"
            self.status_text.color = ft.Colors.RED
            self.page.update()
    
    def highlight_current_article(self, current_path):
        """高亮当前选中的文章"""
        for item in self.article_list.controls:
            if hasattr(item, 'data') and item.data == current_path:
                item.bgcolor = ft.Colors.BLUE_50
            else:
                item.bgcolor = ft.Colors.WHITE
    
    def new_article(self, e):
        """新建文章"""
        self.title_input.value = ""
        self.categories_input.value = "未分类"
        self.tags_input.value = "Hugo"
        self.draft_switch.value = True
        self.content_input.value = ""
        self.current_file = None
        self.current_filename = None
        self.status_text.value = "📝 新建文章，保存后将自动生成文件"
        self.status_text.color = ft.Colors.BLUE
        
        # 移除高亮
        for item in self.article_list.controls:
            item.bgcolor = ft.Colors.WHITE
        
        self.page.update()
    
    def generate_filename(self, title):
        """生成文件名：日期-标题.md"""
        if not title or title.strip() == "":
            title = "untitled"
        
        # 清理标题，只保留中文、英文、数字、空格、短横线
        clean_title = re.sub(r'[^\w\u4e00-\u9fff\s-]', '', title)
        clean_title = clean_title.strip().replace(' ', '-')
        
        # 如果清理后为空，使用默认名
        if not clean_title:
            clean_title = "untitled"
        
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        filename = f"{date_prefix}-{clean_title}.md"
        
        # 检查文件名是否已存在，如果存在则添加数字后缀
        counter = 1
        original_filename = filename
        while (CONTENT_DIR / filename).exists():
            name_parts = original_filename.rsplit('.', 1)
            filename = f"{name_parts[0]}-{counter}.{name_parts[1]}"
            counter += 1
        
        return filename
    
    def save_article(self, e):
        """保存文章"""
        print("开始保存文章...")
        
        if not self.title_input.value or self.title_input.value.strip() == "":
            self.status_text.value = "❌ 请填写文章标题"
            self.status_text.color = ft.Colors.RED
            self.page.update()
            return
        
        # 确保目录存在
        CONTENT_DIR.mkdir(parents=True, exist_ok=True)
        print(f"保存目录: {CONTENT_DIR}")
        
        # 准备 Front Matter
        categories = [c.strip() for c in self.categories_input.value.split(',') if c.strip()]
        tags = [t.strip() for t in self.tags_input.value.split(',') if t.strip()]
        
        front_matter = {
            'title': self.title_input.value.strip(),
            'date': self.get_current_time_with_tz(),
            'draft': self.draft_switch.value,
            'categories': categories if categories else ['未分类'],
            'tags': tags if tags else ['Hugo']
        }
        
        # 确定文件路径
        if self.current_file and self.current_file.exists() and self.current_file.name != "tags.md":
            # 编辑已有文件
            file_path = self.current_file
            
            # 保留原文件的日期
            try:
                with open(self.current_file, 'r', encoding='utf-8') as f:
                    old_content = f.read()
                old_front_matter, _ = self.parse_front_matter(old_content)
                if 'date' in old_front_matter:
                    front_matter['date'] = old_front_matter['date']
                    print(f"保留原日期: {front_matter['date']}")
            except Exception as e:
                print(f"读取原文件日期失败: {e}")
            
            print(f"更新已有文件: {file_path.name}")
        else:
            # 新建文件
            filename = self.generate_filename(self.title_input.value)
            file_path = CONTENT_DIR / filename
            print(f"创建新文件: {filename}")
        
        # 生成完整内容
        full_content = self.format_front_matter(front_matter) + self.content_input.value
        
        # 保存文件
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(full_content)
            
            self.current_file = file_path
            self.current_filename = file_path.name
            
            self.status_text.value = f"✅ 已保存: {file_path.name}"
            self.status_text.color = ft.Colors.GREEN
            
            print(f"保存成功: {file_path}")
            
            # 刷新文章列表
            self.load_article_list()
            
            # 自动选中刚保存的文章
            self.highlight_current_article(file_path)
            
            # 保存后触发一次扫描
            self.scanner.force_scan()
            
        except Exception as ex:
            print(f"保存失败: {ex}")
            self.status_text.value = f"❌ 保存失败: {str(ex)}"
            self.status_text.color = ft.Colors.RED
        
        self.page.update()
    
    def delete_article(self, e):
        """删除当前文章"""
        # 检查是否有选中的文章
        if not self.current_file or not self.current_file.exists():
            self.status_text.value = "❌ 没有选中的文章，请先在左侧点击选择要删除的文章"
            self.status_text.color = ft.Colors.RED
            self.page.update()
            return
        
        # 不允许删除 tags.md
        if self.current_file.name == "tags.md":
            self.status_text.value = "❌ 不能删除 tags.md 文件"
            self.status_text.color = ft.Colors.RED
            self.page.update()
            return
        
        # 创建确认删除的对话框
        def confirm_delete(e):
            try:
                file_path = self.current_file
                filename = file_path.name
                
                # 删除文件
                file_path.unlink()
                print(f"已删除文件: {file_path}")
                
                # 显示成功消息
                self.status_text.value = f"🗑️ 已删除文章: {filename}"
                self.status_text.color = ft.Colors.ORANGE
                
                # 清空编辑器
                self.new_article(None)
                
                # 刷新列表
                self.load_article_list()
                
                # 删除后触发扫描
                self.scanner.force_scan()
                
                # 关闭对话框
                dialog.open = False
                self.page.update()
                
            except Exception as ex:
                print(f"删除失败: {ex}")
                self.status_text.value = f"❌ 删除失败: {str(ex)}"
                self.status_text.color = ft.Colors.RED
                self.page.update()
        
        def cancel_delete(e):
            dialog.open = False
            self.page.update()
        
        # 获取文章标题用于显示
        title = self.title_input.value if self.title_input.value else self.current_file.stem
        
        # 创建对话框
        dialog = ft.AlertDialog(
            title=ft.Text("⚠️ 确认删除"),
            content=ft.Column([
                ft.Text(f"确定要删除以下文章吗？", size=16, weight=ft.FontWeight.BOLD),
                ft.Text(f"标题: {title}", size=14),
                ft.Text(f"文件: {self.current_file.name}", size=12, color=ft.Colors.GREY),
                ft.Text("此操作不可撤销！", size=12, color=ft.Colors.RED, weight=ft.FontWeight.BOLD),
            ], spacing=10),
            actions=[
                ft.TextButton("取消", on_click=cancel_delete),
                ft.ElevatedButton("确认删除", on_click=confirm_delete, color=ft.Colors.RED, bgcolor=ft.Colors.RED_50),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()
    
    def refresh_list(self, e):
        """刷新文章列表"""
        self.load_article_list()
        
        # 如果当前有选中的文章，重新高亮
        if self.current_file and self.current_file.exists():
            self.highlight_current_article(self.current_file)
        
        self.status_text.value = "🔄 列表已刷新"
        self.status_text.color = ft.Colors.BLUE
        self.page.update()
    
    def force_scan(self, e=None):
        """强制立即扫描"""
        self.scanner.force_scan()

def main(page: ft.Page):
    HugoEditor(page)

if __name__ == "__main__":
    print("启动 Hugo 文章管理器...")
    print(f"当前工作目录: {Path.cwd()}")
    print(f"脚本所在目录: {Path(__file__).parent}")
    ft.app(target=main)