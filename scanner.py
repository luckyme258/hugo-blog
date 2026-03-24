"""
scanner.py - 标签和分类扫描器
负责：扫描文章、管理缓存、提供数据查询
"""

import yaml
import threading
import time
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Callable
import json

class TagCategoryScanner:
    """标签和分类扫描器 - 独立的数据层组件"""
    
    def __init__(self, content_dir: Path, callback: Optional[Callable] = None):
        """
        初始化扫描器
        
        Args:
            content_dir: 文章目录路径
            callback: 扫描完成回调函数
        """
        self.content_dir = Path(content_dir)
        self.callback = callback
        
        # 扫描状态
        self.scanning = False
        self.pending_scan = False
        self.scan_timer = None
        self.last_scan_time = None
        
        # 配置参数
        self.scan_interval = 300      # 后台扫描间隔（秒）
        self.scan_delay = 3           # 防抖延迟（秒）
        
        # 缓存结构
        self.cache = {
            'data': {
                'tags': {},           # 标签 -> 使用次数
                'categories': {},     # 分类 -> 使用次数
                'top_tags': [],       # 热门标签列表（前10）
                'top_categories': []  # 热门分类列表（前10）
            },
            'article_states': {},     # 文件名 -> 修改时间
            'cache_time': None,
            'cache_version': 1
        }
        
        # 确保目录存在
        self.content_dir.mkdir(parents=True, exist_ok=True)
        
        # 定义缓存文件路径
        self.cache_file = self.content_dir / ".scanner_cache.json"
        self.tags_file = self.content_dir / "tags.md"
        
        # 加载现有缓存
        self._load_cache()
    
    def _load_cache(self):
        """加载缓存（优先从 JSON 文件，其次从 tags.md）"""
        # 优先使用 JSON 缓存文件（快速加载）
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    self.cache = cache_data
                    print(f"从 JSON 缓存加载: {len(self.cache['data']['tags'])} 个标签")
                    return
            except Exception as e:
                print(f"加载 JSON 缓存失败: {e}")
        
        # 后备：从 tags.md 加载
        if self.tags_file.exists():
            try:
                with open(self.tags_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        front_matter = yaml.safe_load(parts[1].strip())
                        if front_matter and 'cache_data' in front_matter:
                            cache_data = front_matter['cache_data']
                            self.cache['data']['tags'] = cache_data.get('tags', {})
                            self.cache['data']['categories'] = cache_data.get('categories', {})
                            self.cache['data']['top_tags'] = cache_data.get('top_tags', [])
                            self.cache['data']['top_categories'] = cache_data.get('top_categories', [])
                            self.cache['article_states'] = cache_data.get('article_states', {})
                            print(f"从 tags.md 加载: {len(self.cache['data']['tags'])} 个标签")
            except Exception as e:
                print(f"从 tags.md 加载失败: {e}")
    
    def _save_cache(self):
        """保存缓存到 JSON 和 tags.md"""
        try:
            # 更新缓存时间
            self.cache['cache_time'] = datetime.now().isoformat()
            
            # 1. 保存到 JSON 文件（快速加载用）
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
            
            # 2. 生成并保存 tags.md（人类可读）
            tags_md_content = self._generate_tags_md()
            with open(self.tags_file, 'w', encoding='utf-8') as f:
                f.write(tags_md_content)
            
            print(f"缓存已保存: {len(self.cache['data']['tags'])} 个标签")
        except Exception as e:
            print(f"保存缓存失败: {e}")
    
    def _generate_tags_md(self) -> str:
        """生成 tags.md 内容"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 准备 YAML Front Matter
        front_matter = {
            'title': "标签和分类索引",
            'date': datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            'draft': False,
            'version': 2,
            'statistics': {
                'total_articles': len(self.cache['article_states']),
                'last_scan': timestamp,
                'unique_tags': len(self.cache['data']['tags']),
                'unique_categories': len(self.cache['data']['categories'])
            },
            'cache_data': self.cache
        }
        
        yaml_str = yaml.dump(front_matter, allow_unicode=True, default_flow_style=False, sort_keys=False)
        
        # 生成 Markdown
        md = f"""---
{yaml_str}---

# 📊 标签和分类统计

> 最后更新: {timestamp}
> 文章总数: {len(self.cache['article_states'])}
> 标签总数: {len(self.cache['data']['tags'])}
> 分类总数: {len(self.cache['data']['categories'])}

---

## 🔥 热门标签 (Top 10)

"""
        for tag in self.cache['data']['top_tags'][:10]:
            count = self.cache['data']['tags'].get(tag, 0)
            md += f"- **{tag}** ({count} 篇文章)\n"
        
        if not self.cache['data']['top_tags']:
            md += "- *暂无标签*\n"
        
        md += f"""

## 📂 热门分类 (Top 10)

"""
        for cat in self.cache['data']['top_categories'][:10]:
            count = self.cache['data']['categories'].get(cat, 0)
            md += f"- **{cat}** ({count} 篇文章)\n"
        
        if not self.cache['data']['top_categories']:
            md += "- *暂无分类*\n"
        
        md += """

---

*此文件由 Hugo 文章管理器自动生成*
*请勿手动编辑，修改会被自动覆盖*
"""
        return md
    
    def _get_article_mtime(self, file_path: Path) -> float:
        """获取文件修改时间"""
        try:
            return file_path.stat().st_mtime
        except:
            return 0
    
    def _parse_article_tags_categories(self, file_path: Path) -> Tuple[set, set]:
        """解析文章的标签和分类"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析 Front Matter
            if not content.startswith('---'):
                return set(), set()
            
            parts = content.split('---', 2)
            if len(parts) < 3:
                return set(), set()
            
            front_matter = yaml.safe_load(parts[1].strip())
            if not front_matter:
                return set(), set()
            
            # 提取 tags
            tags = front_matter.get('tags', [])
            if isinstance(tags, str):
                tags = [tags]
            elif not isinstance(tags, list):
                tags = []
            tags = {t.strip() for t in tags if t and t.strip()}
            
            # 提取 categories
            categories = front_matter.get('categories', [])
            if isinstance(categories, str):
                categories = [categories]
            elif not isinstance(categories, list):
                categories = []
            categories = {c.strip() for c in categories if c and c.strip()}
            
            return tags, categories
        except Exception as e:
            print(f"解析失败 {file_path.name}: {e}")
            return set(), set()
    
    def _recalculate_top_items(self):
        """重新计算热门排行"""
        sorted_tags = sorted(self.cache['data']['tags'].items(), key=lambda x: x[1], reverse=True)
        self.cache['data']['top_tags'] = [tag for tag, _ in sorted_tags[:10]]
        
        sorted_cats = sorted(self.cache['data']['categories'].items(), key=lambda x: x[1], reverse=True)
        self.cache['data']['top_categories'] = [cat for cat, _ in sorted_cats[:10]]
    
    def full_scan(self):
        """全量扫描所有文章"""
        if self.scanning:
            self.pending_scan = True
            return
        
        self.scanning = True
        print("开始全量扫描...")
        
        try:
            # 重置缓存
            self.cache['data']['tags'] = {}
            self.cache['data']['categories'] = {}
            self.cache['article_states'] = {}
            
            # 获取所有文章
            md_files = [f for f in self.content_dir.glob("*.md") if f.name != "tags.md"]
            
            for md_file in md_files:
                tags, categories = self._parse_article_tags_categories(md_file)
                
                # 更新统计
                for tag in tags:
                    self.cache['data']['tags'][tag] = self.cache['data']['tags'].get(tag, 0) + 1
                for cat in categories:
                    self.cache['data']['categories'][cat] = self.cache['data']['categories'].get(cat, 0) + 1
                
                # 记录状态
                self.cache['article_states'][md_file.name] = self._get_article_mtime(md_file)
            
            # 重新计算热门
            self._recalculate_top_items()
            self.cache['cache_time'] = datetime.now()
            
            # 保存缓存
            self._save_cache()
            
            print(f"全量扫描完成: {len(self.cache['data']['tags'])} 标签, {len(self.cache['data']['categories'])} 分类")
            
            # 回调通知
            if self.callback:
                self.callback()
            
        except Exception as e:
            print(f"全量扫描失败: {e}")
        finally:
            self.scanning = False
            if self.pending_scan:
                self.pending_scan = False
                self.full_scan()
    
    def schedule_scan(self, delay: int = None):
        """防抖调度扫描"""
        if delay is None:
            delay = self.scan_delay
        
        if self.scan_timer:
            self.scan_timer.cancel()
        
        self.scan_timer = threading.Timer(delay, self.full_scan)
        self.scan_timer.daemon = True
        self.scan_timer.start()
        print(f"已调度扫描，延迟 {delay} 秒")
    
    def start_background_scan(self):
        """启动后台扫描服务"""
        def background_loop():
            time.sleep(5)  # 等待启动
            self.full_scan()
            
            while True:
                time.sleep(self.scan_interval)
                self.full_scan()
        
        thread = threading.Thread(target=background_loop, daemon=True)
        thread.start()
        print("后台扫描服务已启动")
    
    def force_scan(self):
        """强制立即扫描"""
        self.schedule_scan(0.5)
    
    # === 数据查询接口 ===
    def get_top_tags(self, limit: int = 10) -> List[str]:
        """获取热门标签"""
        return self.cache['data']['top_tags'][:limit]
    
    def get_top_categories(self, limit: int = 10) -> List[str]:
        """获取热门分类"""
        return self.cache['data']['top_categories'][:limit]
    
    def get_tag_count(self, tag: str) -> int:
        """获取标签使用次数"""
        return self.cache['data']['tags'].get(tag, 0)
    
    def get_category_count(self, cat: str) -> int:
        """获取分类使用次数"""
        return self.cache['data']['categories'].get(cat, 0)
    
    def get_all_tags(self) -> Dict[str, int]:
        """获取所有标签"""
        return self.cache['data']['tags'].copy()
    
    def get_all_categories(self) -> Dict[str, int]:
        """获取所有分类"""
        return self.cache['data']['categories'].copy()
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            'total_articles': len(self.cache['article_states']),
            'unique_tags': len(self.cache['data']['tags']),
            'unique_categories': len(self.cache['data']['categories']),
            'last_scan': self.cache['cache_time']
        }


if __name__ == "__main__":
    # 独立测试
    scanner = TagCategoryScanner(Path("./content/posts"))
    scanner.full_scan()
    print(f"热门标签: {scanner.get_top_tags()}")
    print(f"统计: {scanner.get_stats()}")