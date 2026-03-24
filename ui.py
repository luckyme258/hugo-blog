import flet as ft
from datetime import datetime, timezone, timedelta
import os
import re
import glob
import yaml
from pathlib import Path

# 配置路径
SCRIPT_DIR = Path(__file__).parent.absolute()
CONTENT_DIR = SCRIPT_DIR / "content" / "posts"

class HugoEditor:
    def __init__(self, page: ft.Page):
        self.page = page
        self.current_file = None  # 当前编辑的文件路径
        
        # 确保目录存在
        CONTENT_DIR.mkdir(parents=True, exist_ok=True)
        
        self.setup_ui()
        self.load_article_list()
    
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
        except:
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
            lines.append(f"title: '{front_matter['title']}'")
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
        
        # 新建/保存/刷新按钮
        self.new_btn = ft.ElevatedButton("➕ 新建文章", icon=ft.Icons.ADD, on_click=self.new_article)
        self.save_btn = ft.ElevatedButton("💾 保存文章", icon=ft.Icons.SAVE, on_click=self.save_article)
        self.refresh_btn = ft.OutlinedButton("🔄 刷新列表", icon=ft.Icons.REFRESH, on_click=self.refresh_list)
        
        # 右侧布局
        right_column = ft.Column([
            ft.Text("📝 文章编辑", size=20, weight=ft.FontWeight.BOLD),
            self.title_input,
            ft.Row([self.categories_input, self.tags_input], spacing=20),
            ft.Row([self.draft_switch], alignment=ft.MainAxisAlignment.START),
            ft.Text("内容", weight=ft.FontWeight.BOLD),
            ft.Container(self.content_input, expand=True),
            ft.Row([self.new_btn, self.save_btn, self.refresh_btn], spacing=10),
            self.status_text
        ], spacing=15, expand=True)
        
        # 左右分屏
        self.page.add(
            ft.Row([
                ft.Container(
                    content=ft.Column([
                        ft.Text("📁 文章列表", size=20, weight=ft.FontWeight.BOLD),
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
        self.article_list.controls.clear()
        
        # 获取所有 .md 文件
        md_files = sorted(CONTENT_DIR.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True)
        
        if not md_files:
            self.article_list.controls.append(
                ft.Text("暂无文章，点击「新建文章」开始", color=ft.Colors.GREY, italic=True)
            )
            self.page.update()
            return
        
        for md_file in md_files:
            # 解析文件获取标题
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                front_matter, _ = self.parse_front_matter(content)
                title = front_matter.get('title', md_file.stem)
                
                # 获取文件修改时间
                mtime = datetime.fromtimestamp(md_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                
                # 创建列表项
                list_item = ft.Container(
                    content=ft.Column([
                        ft.Text(title, weight=ft.FontWeight.BOLD, size=14),
                        ft.Text(md_file.name, size=11, color=ft.Colors.GREY),
                        ft.Text(f"修改: {mtime}", size=10, color=ft.Colors.GREY)
                    ], spacing=2),
                    padding=10,
                    bgcolor=ft.Colors.WHITE,
                    border_radius=5,
                    on_click=lambda e, path=md_file: self.load_article(path),
                    ink=True
                )
                self.article_list.controls.append(list_item)
            except Exception as e:
                print(f"读取文件失败 {md_file}: {e}")
        
        self.page.update()
    
    def load_article(self, file_path):
        """加载文章到编辑器"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            front_matter, body = self.parse_front_matter(content)
            
            # 填充表单
            self.title_input.value = front_matter.get('title', '')
            
            # 处理 categories
            categories = front_matter.get('categories', ['未分类'])
            if isinstance(categories, list):
                self.categories_input.value = ', '.join(categories)
            else:
                self.categories_input.value = str(categories)
            
            # 处理 tags
            tags = front_matter.get('tags', ['Hugo'])
            if isinstance(tags, list):
                self.tags_input.value = ', '.join(tags)
            else:
                self.tags_input.value = str(tags)
            
            self.draft_switch.value = front_matter.get('draft', True)
            self.content_input.value = body
            
            self.current_file = file_path
            
            self.status_text.value = f"✅ 已加载: {file_path.name}"
            self.status_text.color = ft.Colors.GREEN
            
            self.page.update()
            
        except Exception as e:
            self.status_text.value = f"❌ 加载失败: {str(e)}"
            self.status_text.color = ft.Colors.RED
            self.page.update()
    
    def new_article(self, e):
        """新建文章"""
        self.title_input.value = ""
        self.categories_input.value = "未分类"
        self.tags_input.value = "Hugo"
        self.draft_switch.value = True
        self.content_input.value = ""
        self.current_file = None
        self.status_text.value = "📝 新建文章，保存后将自动生成文件"
        self.status_text.color = ft.Colors.BLUE
        self.page.update()
    
    def generate_filename(self):
        """生成文件名：日期-标题.md"""
        title = self.title_input.value.strip()
        if not title:
            title = "untitled"
        # 清理标题，只保留中文、英文、数字、空格、短横线
        clean_title = re.sub(r'[^\w\u4e00-\u9fff\s-]', '', title)
        clean_title = clean_title.replace(' ', '-')
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        return f"{date_prefix}-{clean_title}.md"
    
    def save_article(self, e):
        """保存文章"""
        if not self.title_input.value:
            self.status_text.value = "❌ 请填写文章标题"
            self.status_text.color = ft.Colors.RED
            self.page.update()
            return
        
        # 准备 Front Matter
        categories = [c.strip() for c in self.categories_input.value.split(',') if c.strip()]
        tags = [t.strip() for t in self.tags_input.value.split(',') if t.strip()]
        
        front_matter = {
            'title': self.title_input.value,
            'date': self.get_current_time_with_tz(),
            'draft': self.draft_switch.value,
            'categories': categories,
            'tags': tags
        }
        
        # 如果是编辑已有文件，保留原日期
        if self.current_file and self.current_file.exists():
            # 读取原文件的日期
            try:
                with open(self.current_file, 'r', encoding='utf-8') as f:
                    old_content = f.read()
                old_front_matter, _ = self.parse_front_matter(old_content)
                if 'date' in old_front_matter:
                    front_matter['date'] = old_front_matter['date']
            except:
                pass
            filename = self.current_file.name
            file_path = self.current_file
        else:
            # 新文件
            filename = self.generate_filename()
            file_path = CONTENT_DIR / filename
        
        # 生成完整内容
        full_content = self.format_front_matter(front_matter) + self.content_input.value
        
        # 保存文件
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(full_content)
            
            self.current_file = file_path
            
            self.status_text.value = f"✅ 已保存: {file_path.name}"
            self.status_text.color = ft.Colors.GREEN
            
            # 刷新文章列表
            self.load_article_list()
            
        except Exception as ex:
            self.status_text.value = f"❌ 保存失败: {str(ex)}"
            self.status_text.color = ft.Colors.RED
        
        self.page.update()
    
    def refresh_list(self, e):
        """刷新文章列表"""
        self.load_article_list()
        self.status_text.value = "🔄 列表已刷新"
        self.status_text.color = ft.Colors.BLUE
        self.page.update()

def main(page: ft.Page):
    HugoEditor(page)

if __name__ == "__main__":
    ft.app(target=main)
    ft.app(target=main)