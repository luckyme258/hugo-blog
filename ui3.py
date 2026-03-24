"""
ui.py - Hugo 文章管理器 UI
"""

import flet as ft
from datetime import datetime, timezone, timedelta
import re
import yaml
from pathlib import Path
import threading
import time
import asyncio
from scanner import TagCategoryScanner

# 配置路径
SCRIPT_DIR = Path(__file__).parent.absolute()
CONTENT_DIR = SCRIPT_DIR / "content" / "posts"

# 获取主线程的事件循环（在 main 中设置）
main_loop = None


class HugoEditor:
    """Hugo 文章编辑器 UI"""

    def __init__(self, page: ft.Page):
        self.page = page
        self.current_file = None
        self.scanner = None

        # 确保目录存在
        CONTENT_DIR.mkdir(parents=True, exist_ok=True)

        self.setup_ui()
        self.load_article_list()

        # 初始化扫描器（传入回调）
        self.scanner = TagCategoryScanner(CONTENT_DIR, callback=self.on_scan_complete)
        self.scanner.start_background_scan()

        self.status_text.value = "🔄 正在初始化扫描器..."
        self.page.update()

    def on_scan_complete(self):
        """扫描完成回调（在扫描器线程中执行）"""
        global main_loop
        if main_loop:
            asyncio.run_coroutine_threadsafe(
                self._update_scan_status(),
                main_loop
            )

    async def _update_scan_status(self):
        """更新扫描状态到 UI"""
        stats = self.scanner.get_stats()
        self.status_text.value = f"✅ 扫描完成 - {stats['unique_tags']} 个标签, {stats['unique_categories']} 个分类"
        self.status_text.color = ft.Colors.GREEN
        await self.page.update_async()

        # 3秒后清除
        await asyncio.sleep(3)
        if self.status_text.value.startswith("✅ 扫描完成"):
            self.status_text.value = ""
            await self.page.update_async()

    async def _clear_status(self):
        """清除状态消息"""
        self.status_text.value = ""
        await self.page.update_async()

    def get_current_time_with_tz(self):
        """获取当前时间（带时区）"""
        tz = timezone(timedelta(hours=8))
        return datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%S+08:00")

    def parse_front_matter(self, content):
        """解析 Front Matter"""
        if not content.startswith('---'):
            return {}, content

        parts = content.split('---', 2)
        if len(parts) < 3:
            return {}, content

        try:
            front_matter = yaml.safe_load(parts[1].strip())
            return front_matter or {}, parts[2].strip()
        except:
            return {}, content

    def format_front_matter(self, front_matter):
        """格式化 Front Matter"""
        lines = ['---']

        if 'date' in front_matter:
            lines.append(f"date: '{front_matter['date']}'")
        if 'draft' in front_matter:
            lines.append(f"draft: {str(front_matter['draft']).lower()}")
        if 'title' in front_matter:
            title = front_matter['title'].replace("'", "\\'")
            lines.append(f"title: '{title}'")
        if 'categories' in front_matter and front_matter['categories']:
            lines.append(f"categories: {front_matter['categories']}")
        if 'tags' in front_matter and front_matter['tags']:
            lines.append(f"tags: {front_matter['tags']}")

        lines.append('---')
        lines.append('')
        return '\n'.join(lines)

    def setup_ui(self):
        """设置 UI"""
        self.page.title = "Hugo 文章管理器"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.window_width = 1300
        self.page.window_height = 800
        self.page.padding = 20

        # 左侧文章列表
        self.article_list = ft.ListView(expand=True, spacing=5, padding=10)

        # 输入控件
        self.title_input = ft.TextField(
            label="文章标题 *", hint_text="例如：思考", width=600, autofocus=True
        )

        self.categories_input = ft.TextField(
            label="分类", value="",
            hint_text="点击输入框选择热门分类，或直接输入（多个用逗号分隔）",
            width=600, on_focus=self.show_category_suggestions,
            on_blur=self.close_suggestions_panel
        )

        self.tags_input = ft.TextField(
            label="标签", value="",
            hint_text="点击输入框选择热门标签，或直接输入（多个用逗号分隔）",
            width=600, on_focus=self.show_tag_suggestions,
            on_blur=self.close_suggestions_panel
        )

        # 建议面板
        self.suggestions_container = ft.Container(
            visible=False,
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=5,
            padding=10,
            margin=ft.margin.only(top=5),
            shadow=ft.BoxShadow(spread_radius=1, blur_radius=5, color=ft.Colors.GREY_400)
        )

        self.draft_switch = ft.Switch(label="草稿模式", value=True)

        self.content_input = ft.TextField(
            label="文章内容", multiline=True, min_lines=20, max_lines=30,
            expand=True, hint_text="支持 Markdown 和 Hugo 短代码"
        )

        self.status_text = ft.Text("", color=ft.Colors.GREEN)

        # 按钮 - 使用 FilledButton 替代 ElevatedButton
        self.new_btn = ft.FilledButton("➕ 新建文章", icon=ft.Icons.ADD, on_click=self.new_article)
        self.save_btn = ft.FilledButton("💾 保存文章", icon=ft.Icons.SAVE, on_click=self.save_article)
        self.refresh_btn = ft.OutlinedButton("🔄 刷新列表", icon=ft.Icons.REFRESH, on_click=self.refresh_list)
        self.scan_btn = ft.OutlinedButton("🏷️ 重新扫描", icon=ft.Icons.TAG, on_click=self.force_scan)
        self.delete_btn = ft.FilledButton("🗑️ 删除文章", icon=ft.Icons.DELETE, on_click=self.delete_article,
                                          color=ft.Colors.RED, bgcolor=ft.Colors.RED_50)

        # 布局
        right_column = ft.Column([
            ft.Text("📝 文章编辑", size=20, weight=ft.FontWeight.BOLD),
            self.title_input,
            self.categories_input,
            self.tags_input,
            self.suggestions_container,
            ft.Row([self.draft_switch]),
            ft.Text("内容", weight=ft.FontWeight.BOLD),
            ft.Container(self.content_input, expand=True),
            ft.Row([self.new_btn, self.save_btn, self.refresh_btn, self.scan_btn, self.delete_btn], spacing=10),
            self.status_text
        ], spacing=15, expand=True)

        self.page.add(ft.Row([
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
        ], expand=True, spacing=20))

    def close_suggestions_panel(self, e):
        """关闭建议面板（延迟关闭）"""
        def delayed_close():
            time.sleep(0.3)
            if self.suggestions_container.visible:
                self.suggestions_container.visible = False
                self.page.update()

        threading.Thread(target=delayed_close, daemon=True).start()

    def show_category_suggestions(self, e):
        """显示分类建议面板"""
        top_cats = self.scanner.get_top_categories(10)
        if not top_cats:
            self.status_text.value = "💡 暂无热门分类"
            self.page.update()
            return

        # 创建建议按钮
        suggestion_buttons = []
        for cat in top_cats:
            count = self.scanner.get_category_count(cat)
            btn = ft.Container(
                content=ft.Text(f"📁 {cat} ({count})", size=12),
                padding=8,
                bgcolor=ft.Colors.GREY_50,
                border_radius=3,
                on_click=lambda e, v=cat: self.add_to_input('category', v),
                ink=True,
                margin=ft.margin.only(right=5, bottom=5)
            )
            suggestion_buttons.append(btn)

        # 使用 Row 配合 wrap=True 实现换行
        self.suggestions_container.content = ft.Column([
            ft.Text("🔥 热门分类 (点击选择):", size=12, weight=ft.FontWeight.BOLD),
            ft.Row(suggestion_buttons, wrap=True, spacing=5, run_spacing=5),
            ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
            ft.Text("💡 可直接输入新分类，多个用逗号分隔", size=10, color=ft.Colors.GREY)
        ], spacing=5)

        self.suggestions_container.visible = True
        self.page.update()

    def show_tag_suggestions(self, e):
        """显示标签建议面板"""
        top_tags = self.scanner.get_top_tags(10)
        if not top_tags:
            self.status_text.value = "💡 暂无热门标签"
            self.page.update()
            return

        # 创建建议按钮
        suggestion_buttons = []
        for tag in top_tags:
            count = self.scanner.get_tag_count(tag)
            btn = ft.Container(
                content=ft.Text(f"🏷️ {tag} ({count})", size=12),
                padding=8,
                bgcolor=ft.Colors.GREY_50,
                border_radius=3,
                on_click=lambda e, v=tag: self.add_to_input('tag', v),
                ink=True,
                margin=ft.margin.only(right=5, bottom=5)
            )
            suggestion_buttons.append(btn)

        # 使用 Row 配合 wrap=True 实现换行
        self.suggestions_container.content = ft.Column([
            ft.Text("🔥 热门标签 (点击选择):", size=12, weight=ft.FontWeight.BOLD),
            ft.Row(suggestion_buttons, wrap=True, spacing=5, run_spacing=5),
            ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
            ft.Text("💡 可直接输入新标签，多个用逗号分隔", size=10, color=ft.Colors.GREY)
        ], spacing=5)

        self.suggestions_container.visible = True
        self.page.update()

    def add_to_input(self, field_type: str, value: str):
        """添加分类或标签到输入框"""
        if field_type == 'category':
            current = self.categories_input.value.strip()
            if current:
                existing = [c.strip() for c in current.split(',')]
                if value in existing:
                    self.status_text.value = f"⚠️ 分类「{value}」已存在"
                    self.page.update()
                    return
                self.categories_input.value = f"{current}, {value}"
            else:
                self.categories_input.value = value
        else:
            current = self.tags_input.value.strip()
            if current:
                existing = [t.strip() for t in current.split(',')]
                if value in existing:
                    self.status_text.value = f"⚠️ 标签「{value}」已存在"
                    self.page.update()
                    return
                self.tags_input.value = f"{current}, {value}"
            else:
                self.tags_input.value = value

        self.status_text.value = f"✅ 已添加: {value}"
        self.status_text.color = ft.Colors.GREEN
        self.page.update()

        def clear():
            time.sleep(2)
            global main_loop
            if main_loop and self.status_text.value == f"✅ 已添加: {value}":
                asyncio.run_coroutine_threadsafe(self._clear_status(), main_loop)

        threading.Thread(target=clear, daemon=True).start()

    def load_article_list(self):
        """加载文章列表"""
        self.article_list.controls.clear()

        md_files = [f for f in CONTENT_DIR.glob("*.md") if f.name != "tags.md"]
        md_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        for md_file in md_files:
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                front_matter, _ = self.parse_front_matter(content)
                title = front_matter.get('title', md_file.stem)

                is_draft = front_matter.get('draft', False)
                draft_badge = "📝" if is_draft else "✅"

                # 获取修改时间
                mtime = datetime.fromtimestamp(md_file.stat().st_mtime)
                mtime_str = mtime.strftime("%Y-%m-%d %H:%M")

                item = ft.Container(
                    content=ft.Column([
                        ft.Text(f"{draft_badge} {title}", weight=ft.FontWeight.BOLD, size=14),
                        ft.Text(md_file.name, size=10, color=ft.Colors.GREY),
                        ft.Text(mtime_str, size=9, color=ft.Colors.GREY)
                    ], spacing=2),
                    padding=10,
                    bgcolor=ft.Colors.WHITE,
                    border_radius=5,
                    on_click=lambda e, p=md_file: self.load_article(p),
                    ink=True,
                    data=md_file
                )
                self.article_list.controls.append(item)
            except Exception as e:
                print(f"读取失败 {md_file.name}: {e}")

        self.page.update()

    def load_article(self, file_path):
        """加载文章到编辑器"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            front_matter, body = self.parse_front_matter(content)

            self.title_input.value = front_matter.get('title', '')

            cats = front_matter.get('categories', [])
            self.categories_input.value = ', '.join(cats) if cats else ''

            tags = front_matter.get('tags', [])
            self.tags_input.value = ', '.join(tags) if tags else ''

            self.draft_switch.value = front_matter.get('draft', True)
            self.content_input.value = body
            self.current_file = file_path

            # 高亮当前选中的文章
            self.highlight_current_article(file_path)

            self.status_text.value = f"✅ 已加载: {file_path.name}"
            self.status_text.color = ft.Colors.GREEN
            self.page.update()
        except Exception as e:
            self.status_text.value = f"❌ 加载失败: {e}"
            self.status_text.color = ft.Colors.RED
            self.page.update()

    def highlight_current_article(self, current_path):
        """高亮当前选中的文章"""
        for item in self.article_list.controls:
            if hasattr(item, 'data') and item.data == current_path:
                item.bgcolor = ft.Colors.BLUE_50
            else:
                item.bgcolor = ft.Colors.WHITE
        self.page.update()

    def new_article(self, e):
        """新建文章"""
        self.title_input.value = ""
        self.categories_input.value = ""
        self.tags_input.value = ""
        self.draft_switch.value = True
        self.content_input.value = ""
        self.current_file = None
        self.status_text.value = "📝 新建文章"
        self.status_text.color = ft.Colors.BLUE
        self.suggestions_container.visible = False

        # 移除高亮
        for item in self.article_list.controls:
            item.bgcolor = ft.Colors.WHITE

        self.page.update()

    def generate_filename(self, title):
        """生成文件名"""
        clean = re.sub(r'[^\w\u4e00-\u9fff\s-]', '', title)
        clean = clean.strip().replace(' ', '-') or "untitled"
        return f"{datetime.now().strftime('%Y-%m-%d')}-{clean}.md"

    def save_article(self, e):
        """保存文章"""
        if not self.title_input.value.strip():
            self.status_text.value = "❌ 请填写标题"
            self.status_text.color = ft.Colors.RED
            self.page.update()
            return

        # 处理分类和标签
        cats = [c.strip() for c in self.categories_input.value.split(',') if c.strip()]
        tags = [t.strip() for t in self.tags_input.value.split(',') if t.strip()]

        front_matter = {
            'title': self.title_input.value.strip(),
            'date': self.get_current_time_with_tz(),
            'draft': self.draft_switch.value,
            'categories': cats,
            'tags': tags
        }

        if self.current_file and self.current_file.exists() and self.current_file.name != "tags.md":
            file_path = self.current_file
            # 保留原日期
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    old = f.read()
                old_fm, _ = self.parse_front_matter(old)
                if 'date' in old_fm:
                    front_matter['date'] = old_fm['date']
            except:
                pass
        else:
            file_path = CONTENT_DIR / self.generate_filename(self.title_input.value)

        full_content = self.format_front_matter(front_matter) + self.content_input.value

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(full_content)

            self.current_file = file_path
            self.status_text.value = f"✅ 已保存: {file_path.name}"
            self.status_text.color = ft.Colors.GREEN
            self.load_article_list()
            self.highlight_current_article(file_path)

            # 触发扫描（防抖）
            self.scanner.schedule_scan()
        except Exception as ex:
            self.status_text.value = f"❌ 保存失败: {ex}"
            self.status_text.color = ft.Colors.RED

        self.page.update()

    def delete_article(self, e):
        """删除文章"""
        if not self.current_file:
            self.status_text.value = "❌ 请先选择文章"
            self.status_text.color = ft.Colors.RED
            self.page.update()
            return

        if self.current_file.name == "tags.md":
            self.status_text.value = "❌ 不能删除 tags.md"
            self.status_text.color = ft.Colors.RED
            self.page.update()
            return

        def confirm(e):
            try:
                filename = self.current_file.name
                self.current_file.unlink()
                self.status_text.value = f"🗑️ 已删除: {filename}"
                self.status_text.color = ft.Colors.ORANGE
                self.new_article(None)
                self.load_article_list()
                self.scanner.schedule_scan()
                dialog.open = False
                self.page.update()
            except Exception as ex:
                self.status_text.value = f"❌ 删除失败: {ex}"
                self.status_text.color = ft.Colors.RED
                self.page.update()

        def cancel(e):
            dialog.open = False
            self.page.update()

        title = self.title_input.value if self.title_input.value else self.current_file.stem

        dialog = ft.AlertDialog(
            title=ft.Text("⚠️ 确认删除"),
            content=ft.Column([
                ft.Text(f"确定要删除以下文章吗？", size=16, weight=ft.FontWeight.BOLD),
                ft.Text(f"标题: {title}", size=14),
                ft.Text(f"文件: {self.current_file.name}", size=12, color=ft.Colors.GREY),
                ft.Text("此操作不可撤销！", size=12, color=ft.Colors.RED, weight=ft.FontWeight.BOLD),
            ], spacing=10),
            actions=[
                ft.TextButton("取消", on_click=cancel),
                ft.FilledButton("确认删除", on_click=confirm, color=ft.Colors.RED)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def refresh_list(self, e):
        """刷新列表"""
        self.load_article_list()
        if self.current_file and self.current_file.exists():
            self.highlight_current_article(self.current_file)
        self.status_text.value = "🔄 列表已刷新"
        self.status_text.color = ft.Colors.BLUE
        self.page.update()

    def force_scan(self, e):
        """强制扫描"""
        self.status_text.value = "🔍 开始扫描..."
        self.status_text.color = ft.Colors.BLUE
        self.page.update()
        self.scanner.force_scan()


def main(page: ft.Page):
    global main_loop
    main_loop = asyncio.get_event_loop()
    HugoEditor(page)


if __name__ == "__main__":
    print("启动 Hugo 文章管理器...")
    ft.app(target=main)