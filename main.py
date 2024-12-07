import sys
import os
import requests
import shutil
import re
import json
import time
import threading
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QFileDialog, QProgressBar, QMessageBox, QListWidget, QTextEdit,
    QStackedWidget, QFormLayout, QComboBox, QFrame, QCheckBox, QSpinBox,
    QDoubleSpinBox, QSizePolicy, QGraphicsOpacityEffect, QScrollArea,
    QTabWidget, QGroupBox, QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QTimeEdit, QGraphicsDropShadowEffect, QSlider, QSpacerItem, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, QPoint, QSize, QTimer, QTime, QUrl
from PyQt5.QtGui import QIcon, QFont, QPixmap, QColor, QPalette, QBrush
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False

from playwright.sync_api import sync_playwright
import qdarkstyle  # Added QDarkStyle

SETTINGS_FILE = "settings.json"
HISTORY_FILE = "history.json"
CACHE_FILE = "cache.json"
LOG_EXPORT_FILE = "download_log.txt"

# ------------------------ Settings Manager ------------------------
class SettingsManager:
    default_settings = {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "timeout": 10,
        "retries": 3,
        "default_resource_types": {
            "css": True,
            "js": True,
            "images": True,
            "fonts": True,
            "videos": True,
            "svg": True,
            "documents": True
        },
        "max_depth": 2,
        "concurrency": 5,
        "proxy": None,
        "robots_txt": False,
        "rate_limit": 0.1,
        "exclusions": [],
        "ignore_https_errors": False,
        "max_file_size": 0,
        "download_structure": "keep",
        "theme": "Dark",
        "language": "English",
        "enable_logging": True,
        "log_level": "INFO",
        "default_save_location": "",
        "interface_scale": 1.0,
        "enable_notifications": True,
        "show_toolbar": True,
        "download_after_crawl": False,
        "include_subdomains": True,
        "follow_external_links": False,
        "custom_headers": [],
        "basic_auth_user": "",
        "basic_auth_pass": "",
        "schedule_download": False,
        "schedule_time": "00:00",
        "ignore_mime_types": []
    }

    settings = {}

    @classmethod
    def load_settings(cls):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    cls.settings = json.load(f)
                for k, v in cls.default_settings.items():
                    if k not in cls.settings:
                        cls.settings[k] = v
                print("Settings loaded successfully.")
            except (json.JSONDecodeError, IOError, ValueError) as e:
                print(f"Error loading settings: {e}")
                cls.settings = cls.default_settings.copy()
                cls.save_settings()
        else:
            cls.settings = cls.default_settings.copy()
            cls.save_settings()

    @classmethod
    def save_settings(cls):
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(cls.settings, f, indent=4)
            print("Settings saved successfully.")
        except IOError as e:
            print(f"Error saving settings: {e}")

    @classmethod
    def get_setting(cls, key):
        return cls.settings.get(key, cls.default_settings.get(key, ""))

    @classmethod
    def set_setting(cls, key, value):
        cls.settings[key] = value
        cls.save_settings()

    @classmethod
    def reset_to_defaults(cls):
        cls.settings = cls.default_settings.copy()
        cls.save_settings()

# ------------------------ History Manager ------------------------
class HistoryManager:
    history = []
    download_paths = {}

    @classmethod
    def load_history(cls):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f:
                    data = json.load(f)
                    cls.history = data.get('history', [])
                    cls.download_paths = data.get('download_paths', {})
                print("History loaded successfully.")
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading history: {e}")
                cls.history = []
                cls.download_paths = {}
                cls.save_history()
        else:
            cls.save_history()

    @classmethod
    def save_history(cls):
        data = {
            'history': cls.history,
            'download_paths': cls.download_paths
        }
        try:
            with open(HISTORY_FILE, 'w') as f:
                json.dump(data, f, indent=4)
            print("History saved successfully.")
        except IOError as e:
            print(f"Error saving history: {e}")

    @classmethod
    def add_history(cls, url, path):
        if url not in cls.history:
            cls.history.append(url)
            cls.download_paths[url] = path
            cls.save_history()
            print(f"Added to history: {url}")
        else:
            print(f"URL already in history: {url}")

    @classmethod
    def get_history(cls):
        return cls.history[::-1]

    @classmethod
    def get_download_path(cls, url):
        return cls.download_paths.get(url, "")

    @classmethod
    def clear_history(cls):
        cls.history = []
        cls.download_paths = {}
        cls.save_history()
        print("History cleared.")

# ------------------------ Web Downloader ------------------------
class WebDownloader:
    def __init__(self, base_urls, download_path, user_agent, resource_types, timeout, retries,
                 max_depth=2, concurrency=5, proxy=None, exclusions=None,
                 progress_callback=None, status_callback=None, log_callback=None,
                 resource_downloaded_callback=None, robots_txt=True, rate_limit=0.1,
                 ignore_https_errors=False, max_file_size=0, download_structure="keep",
                 follow_external_links=False, custom_headers=None, basic_auth_user="",
                 basic_auth_pass="", ignore_mime_types=None, stop_event=None):
        self.base_urls = base_urls
        self.download_path = download_path
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': user_agent})
        if proxy:
            self.session.proxies.update(proxy)
        self.session.verify = not ignore_https_errors

        if custom_headers:
            for hdr in custom_headers:
                if hdr.get("key") and hdr.get("value"):
                    self.session.headers[hdr["key"]] = hdr["value"]

        if basic_auth_user and basic_auth_pass:
            self.session.auth = (basic_auth_user, basic_auth_pass)

        self.resource_types = resource_types
        self.timeout = timeout
        self.retries = retries
        self.max_depth = max_depth
        self.concurrency = concurrency
        self.progress_callback = progress_callback
        self.status_callback = status_callback
        self.log_callback = log_callback
        self.resource_downloaded_callback = resource_downloaded_callback
        self.visited_urls = set()
        self.counted_urls = set()
        self.total_resources = 0
        self.downloaded_resources = 0
        self.lock = threading.Lock()
        self.rate_limit = rate_limit
        self.robots_txt = robots_txt
        self.exclusions = set(exclusions) if exclusions else set()
        self.download_cache = set()
        self.ignore_https_errors = ignore_https_errors
        self.max_file_size = max_file_size * 1024 * 1024
        self.download_structure = download_structure
        self.follow_external_links = follow_external_links
        self.ignore_mime_types = ignore_mime_types if ignore_mime_types else []
        self.stop_event = stop_event

        self.load_cache()
        self.executor = ThreadPoolExecutor(max_workers=self.concurrency)
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.resource_queue = []

    def load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f:
                    data = json.load(f)
                    self.download_cache = set(data.get('downloaded', []))
                self.log_callback("✅ Cache loaded.")
            except (json.JSONDecodeError, IOError) as e:
                self.log_callback(f"❌ Failed to load cache: {e}")
                self.download_cache = set()
        else:
            self.save_cache()

    def save_cache(self):
        data = {
            'downloaded': list(self.download_cache)
        }
        try:
            with open(CACHE_FILE, 'w') as f:
                json.dump(data, f, indent=4)
            self.log_callback("✅ Cache saved.")
        except IOError as e:
            self.log_callback(f"❌ Failed to save cache: {e}")

    def pause(self):
        self.pause_event.clear()
        self.log_callback("⏸️ Download paused.")

    def resume(self):
        self.pause_event.set()
        self.log_callback("▶️ Download resumed.")

    def _can_fetch(self, url):
        if self.stop_event and self.stop_event.is_set():
            return False
        for exclusion in self.exclusions:
            if exclusion in url:
                self.log_callback(f"🚫 Excluded by user settings: {url}")
                return False
        if not self.robots_txt:
            return True
        parsed_url = urlparse(url)
        robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
        rp = RobotFileParser()
        try:
            rp.set_url(robots_url)
            rp.read()
            can_fetch = rp.can_fetch(self.session.headers['User-Agent'], url)
            if not can_fetch:
                self.log_callback(f"🚫 Disallowed by robots.txt: {url}")
            else:
                self.log_callback(f"✅ Allowed by robots.txt: {url}")
            return can_fetch
        except Exception as e:
            self.log_callback(f"⚠️ Could not fetch robots.txt for {url}: {e}")
            return True

    def download_websites(self):
        try:
            if not os.path.exists(self.download_path):
                os.makedirs(self.download_path)

            for base_url in self.base_urls:
                if self.stop_event and self.stop_event.is_set():
                    break
                self.status_callback(f"🕵️‍♂️ Starting resource counting for {base_url}")
                self._count_total_resources(base_url, current_depth=0)

            self.status_callback("📦 Resource counting completed.")
            self.status_callback("🔄 Starting download...")

            for base_url in self.base_urls:
                if self.stop_event and self.stop_event.is_set():
                    break
                self._download_page_with_playwright(base_url, self.download_path, current_depth=0)

            for resource in self.resource_queue:
                if self.stop_event and self.stop_event.is_set():
                    break
                self.executor.submit(self._download_resource, *resource)

            self.executor.shutdown(wait=True)

            if self.stop_event and self.stop_event.is_set():
                if self.log_callback:
                    self.log_callback("🛑 Download stopped by user.")
                return False, "🛑 Download stopped by user."

            if self.progress_callback:
                self.progress_callback(100)
            if self.log_callback:
                self.log_callback("✅ Download completed successfully.")
            return True, "✅ Download completed successfully."
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"❌ An error occurred: {e}")
            return False, f"❌ An error occurred: {e}"

    def _count_total_resources(self, url, current_depth):
        if self.stop_event and self.stop_event.is_set():
            return
        if current_depth > self.max_depth:
            return
        parsed_url = urlparse(url)
        if parsed_url.scheme not in ['http', 'https']:
            self.log_callback(f"⚠️ Skipping non-HTTP URL: {url}")
            return
        if url in self.counted_urls:
            self.log_callback(f"ℹ️ Already counted: {url}")
            return
        if not self._can_fetch(url):
            return
        self.counted_urls.add(url)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(user_agent=self.session.headers['User-Agent'])
                page = context.new_page()
                page.goto(url, timeout=self.timeout * 1000)
                content = page.content()
                browser.close()

            soup = BeautifulSoup(content, 'html.parser')
            resources = self._parse_resources(soup, url)
            self.total_resources += len(resources)
            self.log_callback(f"📝 Found {len(resources)} resources on {url}")

            linked_pages = self._find_linked_pages(soup, url)
            for link in linked_pages:
                if self.stop_event and self.stop_event.is_set():
                    break
                full_link = urljoin(url, link)
                self._count_total_resources(full_link, current_depth + 1)

            time.sleep(self.rate_limit)

        except Exception as e:
            self.log_callback(f"❌ Failed to access {url}: {e}")

    def _download_page_with_playwright(self, url, path, current_depth):
        if self.stop_event and self.stop_event.is_set():
            return
        if current_depth > self.max_depth:
            return
        parsed_url = urlparse(url)
        if parsed_url.scheme not in ['http', 'https']:
            self.log_callback(f"⚠️ Skipping non-HTTP URL: {url}")
            return
        if url in self.visited_urls:
            self.log_callback(f"ℹ️ Already downloaded: {url}")
            return
        if not self._can_fetch(url):
            return
        self.visited_urls.add(url)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(user_agent=self.session.headers['User-Agent'])
                page = context.new_page()
                page.goto(url, timeout=self.timeout * 1000)
                content = page.content()
                browser.close()

            soup = BeautifulSoup(content, 'html.parser')
            relative_path = self._get_relative_path(url)
            local_path = os.path.join(path, relative_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.log_callback(f"✅ Saved page: {local_path}")

            resources = self._parse_resources(soup, url)
            for resource_url in resources:
                if resource_url not in self.download_cache:
                    self.resource_queue.append((resource_url, path, url))

            linked_pages = self._find_linked_pages(soup, url)
            for link in linked_pages:
                if self.stop_event and self.stop_event.is_set():
                    break
                full_link = urljoin(url, link)
                self._download_page_with_playwright(full_link, path, current_depth + 1)

            time.sleep(self.rate_limit)

        except Exception as e:
            self.log_callback(f"❌ Failed to download {url} with Playwright: {e}")

    def _parse_css_resources(self, css_url):
        resources = []
        try:
            response = self.session.get(css_url, timeout=self.timeout)
            response.raise_for_status()
            css_content = response.text
            # Find @import statements
            import_statements = re.findall(r'@import\s+(?:url\()?["\']?(.*?)["\']?\)?;', css_content)
            for imp in import_statements:
                full_url = urljoin(css_url, imp)
                if self.is_valid_resource_url(full_url):
                    resources.append(full_url)
            # Find additional url() references
            url_references = re.findall(r'url\(["\']?(.*?)["\']?\)', css_content)
            for ref in url_references:
                if not ref.startswith('data:'):
                    full_url = urljoin(css_url, ref)
                    if self.is_valid_resource_url(full_url):
                        resources.append(full_url)

        except requests.RequestException as e:
            self.log_callback(f"❌ Failed to parse CSS {css_url}: {e}")

        return resources


    def _find_linked_pages(self, soup, base_url):
        links = []
        base_parsed = urlparse(base_url)
        for a in soup.find_all('a', href=True):
            if self.stop_event and self.stop_event.is_set():
                break
            href = a.get('href')
            if href.startswith('#'):
                continue
            full_url = urljoin(base_url, href)
            parsed_full_url = urlparse(full_url)
            parsed_base_url = urlparse(base_url)

            if not self.follow_external_links:
                if parsed_full_url.netloc != parsed_base_url.netloc:
                    continue
            links.append(href)
        return links

    def is_valid_resource_url(self, url):
        parsed = urlparse(url)
        if '%23' in parsed.path:
            self.log_callback(f"🚫 Excluding resource URL with encoded fragment: {url}")
            return False
        if parsed.scheme not in ['http', 'https'] or not bool(parsed.netloc):
            return False
        return True

    def _download_resource(self, url, path, page_url):
        if self.stop_event and self.stop_event.is_set():
            return
        if url in self.download_cache:
            self.log_callback(f"ℹ️ Resource already downloaded: {url}")
            if self.resource_downloaded_callback:
                self.resource_downloaded_callback.emit(url, "ℹ️ Already Downloaded", self._get_relative_path(url))
            return
        if not self._can_fetch(url):
            return
        try:
            self.pause_event.wait()
            if self.stop_event and self.stop_event.is_set():
                return
            attempt = 0
            while attempt <= self.retries:
                try:
                    head_resp = self.session.head(url, timeout=self.timeout)
                    mime_type = head_resp.headers.get('Content-Type', '')
                    if any(m in mime_type for m in self.ignore_mime_types):
                        self.log_callback(f"🚫 Skipping {url} due to ignored MIME type {mime_type}")
                        return
                    response = self.session.get(url, timeout=self.timeout, stream=True)
                    response.raise_for_status()
                    if self.max_file_size > 0:
                        content_length = response.headers.get('Content-Length')
                        if content_length and int(content_length) > self.max_file_size:
                            self.log_callback(f"❌ Resource too large, skipping: {url}")
                            if self.resource_downloaded_callback:
                                self.resource_downloaded_callback.emit(url, "❌ Too Large", "")
                            return
                    break
                except requests.RequestException as e:
                    attempt += 1
                    if attempt > self.retries:
                        raise e
                    wait_time = 2 ** attempt
                    self.log_callback(f"⚠️ Retry {attempt}/{self.retries} for {url} after {wait_time} seconds.")
                    time.sleep(wait_time)

            relative_path = self._get_relative_path(url)
            local_path = os.path.join(path, relative_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'wb') as f:
                shutil.copyfileobj(response.raw, f)
            self.log_callback(f"✅ Downloaded resource: {local_path}")

            self._rewrite_html(page_url, url, relative_path)
            self.download_cache.add(url)
            self.save_cache()

            if self.resource_downloaded_callback:
                self.resource_downloaded_callback(url, "✅ Downloaded", local_path)


            with self.lock:
                self.downloaded_resources += 1
                self._update_progress()

            time.sleep(self.rate_limit)

        except requests.RequestException as e:
            self.log_callback(f"❌ Failed to download resource {url}: {e}")
            if self.resource_downloaded_callback:
                self.resource_downloaded_callback.emit(url, f"❌ Failed: {e}", "")

    def _rewrite_html(self, page_url, resource_url, local_relative_path):
        if self.stop_event and self.stop_event.is_set():
            return
        parsed_page_url = urlparse(page_url)
        relative_page_path = self._get_relative_path(page_url)
        local_page_path = os.path.join(self.download_path, relative_page_path)
        if not os.path.exists(local_page_path):
            return
        try:
            with open(local_page_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            soup = BeautifulSoup(html_content, 'html.parser')
            resource_type_map = {
                '.css': ('link', 'href'),
                '.js': ('script', 'src'),
                '.png': ('img', 'src'),
                '.jpg': ('img', 'src'),
                '.jpeg': ('img', 'src'),
                '.gif': ('img', 'src'),
                '.svg': ('img', 'src'),
                '.bmp': ('img', 'src'),
                '.webp': ('img', 'src'),
                '.woff': ('link', 'href'),
                '.woff2': ('link', 'href'),
                '.ttf': ('link', 'href'),
                '.otf': ('link', 'href'),
                '.mp4': ('video', 'src'),
                '.webm': ('video', 'src'),
                '.ogg': ('video', 'src'),
                '.pdf': ('a', 'href'),
                '.docx': ('a', 'href'),
                '.xlsx': ('a', 'href'),
                '.pptx': ('a', 'href'),
            }
            extension = os.path.splitext(resource_url)[1].lower()
            if extension in resource_type_map:
                tag_name, attr = resource_type_map[extension]
                tags = soup.find_all(tag_name, {attr: True})
                for tag in tags:
                    src = tag.get(attr)
                    if src:
                        parsed_src = urlparse(src)
                        clean_src = parsed_src._replace(fragment='').geturl()
                        if clean_src == resource_url:
                            new_path = os.path.relpath(local_relative_path, os.path.dirname(local_page_path))
                            new_path = new_path.replace('\\', '/')
                            tag[attr] = new_path
            else:
                tags = soup.find_all(['link', 'script', 'img', 'video', 'source', 'a'],
                                     href=lambda x: x and x.startswith(resource_url))
                for tag in tags:
                    if 'href' in tag.attrs:
                        new_path = os.path.relpath(local_relative_path, os.path.dirname(local_page_path))
                        new_path = new_path.replace('\\', '/')
                        tag['href'] = new_path
                    if 'src' in tag.attrs:
                        new_path = os.path.relpath(local_relative_path, os.path.dirname(local_page_path))
                        new_path = new_path.replace('\\', '/')
                        tag['src'] = new_path
            with open(local_page_path, 'w', encoding='utf-8') as f:
                f.write(str(soup))
            self.log_callback(f"🔄 Rewrote HTML links in {local_page_path}")
        except Exception as e:
            self.log_callback(f"❌ Failed to rewrite HTML for {page_url}: {e}")

    def _get_relative_path(self, url):
        parsed_url = urlparse(url)
        path = parsed_url.path
        if path.endswith('/'):
            path += 'index.html'
        elif not os.path.splitext(path)[1]:
            path += '/index.html'

        extension = os.path.splitext(path)[1].lower()
        if self.download_structure == "flatten":
            filename = os.path.basename(path)
            if not filename:
                filename = "index.html"
            # If it's a JS or CSS file, put it in a specific folder
            if extension == '.css':
                return os.path.join(parsed_url.netloc, 'css', filename).replace('\\', '/')
            elif extension == '.js':
                return os.path.join(parsed_url.netloc, 'js', filename).replace('\\', '/')
            else:
                return os.path.join(parsed_url.netloc, filename).replace('\\', '/')
        else:
            # keep original structure
            return os.path.join(parsed_url.netloc, path.lstrip('/')).replace('\\', '/')


    def _update_progress(self):
        if self.total_resources == 0:
            progress = 100
        else:
            progress = int((self.downloaded_resources / self.total_resources) * 100)
            if progress > 100:
                progress = 100
        if self.progress_callback:
            self.progress_callback(progress)
        if self.status_callback:
            self.status_callback(f"Downloaded {self.downloaded_resources} of {self.total_resources} resources.")

    def _parse_resources(self, soup, base_url):
        resources = []
        if self.stop_event and self.stop_event.is_set():
            return resources
        rt = self.resource_types

        # For CSS
        if 'css' in rt:
            for link in soup.find_all('link', rel='stylesheet'):
                href = link.get('href')
                if href:
                    full_url = urljoin(base_url, href)
                    if self.is_valid_resource_url(full_url):
                        resources.append(full_url)
                        # If the CSS references other resources like @import or URL(),
                        # they'll be handled in _parse_css_resources

        # For JS
        if 'js' in rt:
            for script in soup.find_all('script', src=True):
                src = script.get('src')
                if src:
                    full_url = urljoin(base_url, src)
                    if self.is_valid_resource_url(full_url):
                        resources.append(full_url)

        if 'images' in rt:
            for img in soup.find_all('img', src=True):
                src = img.get('src')
                if src:
                    full_url = urljoin(base_url, src)
                    parsed_url = urlparse(full_url)
                    clean_url = parsed_url._replace(fragment='').geturl()
                    if self.is_valid_resource_url(clean_url):
                        resources.append(clean_url)

        if 'fonts' in rt:
            for link in soup.find_all('link', rel=lambda x: x and 'font' in x.lower()):
                href = link.get('href')
                if href:
                    full_url = urljoin(base_url, href)
                    parsed_url = urlparse(full_url)
                    clean_url = parsed_url._replace(fragment='').geturl()
                    if self.is_valid_resource_url(clean_url):
                        resources.append(clean_url)

        if 'videos' in rt:
            for video in soup.find_all('video'):
                src = video.get('src')
                if src:
                    full_url = urljoin(base_url, src)
                    parsed_url = urlparse(full_url)
                    clean_url = parsed_url._replace(fragment='').geturl()
                    if self.is_valid_resource_url(clean_url):
                        resources.append(clean_url)
                for source in video.find_all('source', src=True):
                    source_src = source.get('src')
                    if source_src:
                        full_url = urljoin(base_url, source_src)
                        parsed_url = urlparse(full_url)
                        clean_url = parsed_url._replace(fragment='').geturl()
                        if self.is_valid_resource_url(clean_url):
                            resources.append(clean_url)

        if 'svg' in rt:
            for img in soup.find_all('img', src=True):
                src = img.get('src')
                if src and src.lower().endswith('.svg'):
                    full_url = urljoin(base_url, src)
                    parsed_url = urlparse(full_url)
                    clean_url = parsed_url._replace(fragment='').geturl()
                    if self.is_valid_resource_url(clean_url):
                        resources.append(clean_url)

        if 'documents' in rt:
            for a in soup.find_all('a', href=True):
                href = a.get('href')
                if href and any(href.lower().endswith(ext) for ext in ['.pdf', '.docx', '.xlsx', '.pptx']):
                    full_url = urljoin(base_url, href)
                    parsed_url = urlparse(full_url)
                    clean_url = parsed_url._replace(fragment='').geturl()
                    if self.is_valid_resource_url(clean_url):
                        resources.append(clean_url)

        self.log_callback(f"🔍 Total resources found on {base_url}: {len(resources)}")
        return resources


# ------------------------ Downloader Thread ------------------------
class DownloaderThread(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished_download = pyqtSignal(bool, str)
    log = pyqtSignal(str)
    resource_downloaded = pyqtSignal(str, str, str)

    def __init__(self, urls, path, user_agent, resource_types, timeout, retries,
                 max_depth=2, concurrency=5, proxy=None, exclusions=None,
                 robots_txt=True, rate_limit=0.1, ignore_https_errors=False,
                 max_file_size=0, download_structure="keep", follow_external_links=False,
                 custom_headers=None, basic_auth_user="", basic_auth_pass="", ignore_mime_types=None,
                 stop_event=None):
        super().__init__()
        self.downloader = WebDownloader(
            base_urls=urls,
            download_path=path,
            user_agent=user_agent,
            resource_types=resource_types,
            timeout=timeout,
            retries=retries,
            max_depth=max_depth,
            concurrency=concurrency,
            proxy=proxy,
            exclusions=exclusions,
            progress_callback=self.emit_progress,
            status_callback=self.emit_status,
            log_callback=self.emit_log,
            resource_downloaded_callback=self.emit_resource_downloaded,
            robots_txt=robots_txt,
            rate_limit=rate_limit,
            ignore_https_errors=ignore_https_errors,
            max_file_size=max_file_size,
            download_structure=download_structure,
            follow_external_links=follow_external_links,
            custom_headers=custom_headers,
            basic_auth_user=basic_auth_user,
            basic_auth_pass=basic_auth_pass,
            ignore_mime_types=ignore_mime_types,
            stop_event=stop_event
        )

    def run(self):
        success, message = self.downloader.download_websites()
        self.finished_download.emit(success, message)

    def emit_progress(self, value):
        self.progress.emit(value)

    def emit_status(self, message):
        self.status.emit(message)

    def emit_log(self, message):
        self.log.emit(message)

    def emit_resource_downloaded(self, url, status, path):
        self.resource_downloaded.emit(url, status, path)

    def pause(self):
        self.downloader.pause()

    def resume(self):
        self.downloader.resume()

# ------------------------ Sidebar Button ------------------------
class SidebarButton(QPushButton):
    def __init__(self, icon_path, text):
        super().__init__()
        self.setIcon(QIcon(icon_path))
        self.setText(text)
        self.setFixedHeight(50)
        self.setFont(QFont("Segoe UI", 12))
        self.setIconSize(QSize(24, 24))

        self.inactive_style = """
            QPushButton {
                background-color: #1e1e1e;
                color: #ffffff;
                text-align: left;
                padding-left: 20px;
                border: none;
                border-left: 3px solid transparent;
                border-radius: 0px;
            }
            QPushButton:hover {
                background-color: #2d2d2d;
                border-left: 3px solid #1e90ff;
            }
            QPushButton:pressed {
                background-color: #3c3c3c;
                border-left: 3px solid #1e90ff;
            }
        """

        self.active_style = """
            QPushButton {
                background-color: #2d2d2d;
                color: #1e90ff;
                text-align: left;
                padding-left: 20px;
                border: none;
                border-left: 3px solid #1e90ff;
                border-radius: 0px;
            }
            QPushButton:hover {
                background-color: #333333;
            }
            QPushButton:pressed {
                background-color: #3c3c3c;
            }
        """

        self.setStyleSheet(self.inactive_style)

    def set_active(self, active):
        if active:
            self.setStyleSheet(self.active_style)
        else:
            self.setStyleSheet(self.inactive_style)

# ------------------------ Title Bar ------------------------
class TitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()
        self.start = QPoint(0, 0)
        self.pressing = False

    def init_ui(self):
        self.setFixedHeight(40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet("""
            QWidget {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2c3e50, stop:1 #34495e);
            }
            QLabel {
                color: #ecf0f1;
                font: 14px "Segoe UI", sans-serif;
            }
            QPushButton {
                border: none;
                color: #ecf0f1;
                font-size: 12px;
                width: 30px;
                height: 30px;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #34495e;
            }
            QPushButton:pressed {
                background-color: #2980b9;
            }
        """)

        self.app_icon = QLabel()
        app_pixmap = QPixmap("icons/app_icon.png").scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.app_icon.setPixmap(app_pixmap)
        self.app_icon.setFixedSize(24, 24)
        self.app_icon.setToolTip("Web Downloader")

        self.title = QLabel("Web Downloader")
        self.title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.title.setStyleSheet("background-color: transparent;")

        self.btn_minimize = QPushButton()
        self.btn_minimize.setIcon(QIcon("icons/minimize.png"))
        self.btn_minimize.setToolTip("Minimize")
        self.btn_minimize.clicked.connect(self.minimize_window)

        self.btn_maximize = QPushButton()
        self.btn_maximize.setIcon(QIcon("icons/maximize.png"))
        self.btn_maximize.setToolTip("Maximize")
        self.btn_maximize.clicked.connect(self.maximize_restore_window)

        self.btn_close = QPushButton()
        self.btn_close.setIcon(QIcon("icons/close.png"))
        self.btn_close.setToolTip("Close")
        self.btn_close.clicked.connect(self.close_window)

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(10, 0, 10, 0)
        h_layout.setSpacing(10)

        h_layout.addWidget(self.app_icon, alignment=Qt.AlignLeft | Qt.AlignVCenter)
        h_layout.addWidget(self.title, alignment=Qt.AlignLeft | Qt.AlignVCenter)
        h_layout.addStretch()
        h_layout.addWidget(self.btn_minimize, alignment=Qt.AlignRight | Qt.AlignVCenter)
        h_layout.addWidget(self.btn_maximize, alignment=Qt.AlignRight | Qt.AlignVCenter)
        h_layout.addWidget(self.btn_close, alignment=Qt.AlignRight | Qt.AlignVCenter)

        self.setLayout(h_layout)

    def minimize_window(self):
        self.parent.showMinimized()

    def maximize_restore_window(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
            self.btn_maximize.setIcon(QIcon("icons/maximize.png"))
            self.btn_maximize.setToolTip("Maximize")
        else:
            self.parent.showMaximized()
            self.btn_maximize.setIcon(QIcon("icons/restore.png"))
            self.btn_maximize.setToolTip("Restore")

    def close_window(self):
        choice = QMessageBox.question(self, 'Quit',
                                      "Are you sure you want to quit?", QMessageBox.Yes |
                                      QMessageBox.No, QMessageBox.No)

        if choice == QMessageBox.Yes:
            sys.exit()
        else:
            pass

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start = event.globalPos()
            self.pressing = True

    def mouseMoveEvent(self, event):
        if self.pressing:
            self.parent.move(self.parent.pos() + event.globalPos() - self.start)
            self.start = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.pressing = False

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.maximize_restore_window()

# ------------------------ Home Widget ------------------------
class HomeWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.downloader_thread = None
        self.stop_event = threading.Event()
        self.schedule_timer = None
        self.preview_button = None
        self.open_folder_button = None

    def init_ui(self):
        urls_label = QLabel("Website URLs (one per line):")
        urls_label.setFont(QFont("Segoe UI", 12))
        self.urls_input = QTextEdit()
        self.urls_input.setPlaceholderText("https://example.com\nhttps://anotherexample.com")
        self.urls_input.setFont(QFont("Segoe UI", 12))

        path_label = QLabel("Download Path:")
        path_label.setFont(QFont("Segoe UI", 12))
        self.path_input = QLineEdit()
        self.path_input.setReadOnly(True)
        self.path_input.setFont(QFont("Segoe UI", 12))
        self.browse_button = QPushButton("Browse")
        self.browse_button.setFont(QFont("Segoe UI", 12))
        self.browse_button.setFixedWidth(100)
        self.browse_button.clicked.connect(self.browse_folder)

        self.download_button = QPushButton("Download")
        self.download_button.setFont(QFont("Segoe UI", 12))
        self.download_button.setFixedHeight(40)
        self.download_button.setStyleSheet("""
            QPushButton {
                background-color: #1e90ff;
                color: white;
                border-radius: 0px;
            }
            QPushButton:hover {
                background-color: #63b8ff;
            }
            QPushButton:pressed {
                background-color: #4682b4;
            }
        """)
        self.download_button.clicked.connect(self.on_download)

        self.pause_button = QPushButton("Pause")
        self.pause_button.setFont(QFont("Segoe UI", 12))
        self.pause_button.setFixedHeight(40)
        self.pause_button.setStyleSheet("""
            QPushButton {
                background-color: #ffa500;
                color: white;
                border-radius: 0px;
            }
            QPushButton:hover {
                background-color: #ffb733;
            }
            QPushButton:pressed {
                background-color: #e69500;
            }
        """)
        self.pause_button.clicked.connect(self.pause_download)
        self.pause_button.setEnabled(False)

        self.resume_button = QPushButton("Resume")
        self.resume_button.setFont(QFont("Segoe UI", 12))
        self.resume_button.setFixedHeight(40)
        self.resume_button.setStyleSheet("""
            QPushButton {
                background-color: #32cd32;
                color: white;
                border-radius: 0px;
            }
            QPushButton:hover {
                background-color: #45da45;
            }
            QPushButton:pressed {
                background-color: #28a428;
            }
        """)
        self.resume_button.clicked.connect(self.resume_download)
        self.resume_button.setEnabled(False)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setFont(QFont("Segoe UI", 12))
        self.stop_button.setFixedHeight(40)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #ff4d4d;
                color: white;
                border-radius: 0px;
            }
            QPushButton:hover {
                background-color: #ff6666;
            }
            QPushButton:pressed {
                background-color: #e60000;
            }
        """)
        self.stop_button.clicked.connect(self.stop_download)
        self.stop_button.setEnabled(False)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.download_button)
        buttons_layout.addWidget(self.pause_button)
        buttons_layout.addWidget(self.resume_button)
        buttons_layout.addWidget(self.stop_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.setFont(QFont("Segoe UI", 10))
        self.progress_bar.setFixedHeight(25)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 0px;
                text-align: center;
                background-color: #3c3c3c;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #1e90ff;
                width: 20px;
            }
            QProgressBar::chunk:hover {
                background-color: #63b8ff;
            }
        """)
        self.progress_bar.hide()

        self.status_label = QLabel("Enter URLs and select a download path.")
        self.status_label.setFont(QFont("Segoe UI", 10))
        self.status_label.setStyleSheet("color: #ffffff;")

        logs_label = QLabel("Download Logs:")
        logs_label.setFont(QFont("Segoe UI", 12))

        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        self.logs_text.setFont(QFont("Segoe UI", 10))
        self.logs_text.setStyleSheet("""
            QTextEdit {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 0px;
                padding: 5px;
                color: #ffffff;
            }
        """)

        self.clear_logs_button = QPushButton("Clear Logs")
        self.clear_logs_button.setFont(QFont("Segoe UI", 10))
        self.clear_logs_button.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: white;
                border-radius: 0px;
            }
            QPushButton:hover {
                background-color: #777777;
            }
            QPushButton:pressed {
                background-color: #333333;
            }
        """)
        self.clear_logs_button.clicked.connect(self.clear_logs)

        logs_control_layout = QHBoxLayout()
        logs_control_layout.addWidget(logs_label)
        logs_control_layout.addStretch()
        logs_control_layout.addWidget(self.clear_logs_button)

        logs_layout = QVBoxLayout()
        logs_layout.addLayout(logs_control_layout)
        logs_layout.addWidget(self.logs_text)
        logs_card = QWidget()
        logs_card.setLayout(logs_layout)
        logs_card.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                border: 1px solid #555555;
                border-radius: 0px;
            }
        """)

        self.resource_table = QTableWidget()
        self.resource_table.setColumnCount(3)
        self.resource_table.setHorizontalHeaderLabels(['Resource URL', 'Status', 'Path'])
        self.resource_table.horizontalHeader().setStretchLastSection(True)
        self.resource_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.resource_table.setFont(QFont("Segoe UI", 10))
        self.resource_table.setStyleSheet("""
            QTableWidget {
                background-color: #3c3c3c;
                border: none;
                color: #ffffff;
                gridline-color: #555555;
            }
            QHeaderView::section {
                background-color: #2b2b2b;
                color: #ffffff;
                font-size: 12px;
            }
        """)
        self.resource_table.setSortingEnabled(True)
        self.resource_table.hide()

        self.resource_search_input = QLineEdit()
        self.resource_search_input.setPlaceholderText("Filter resources...")
        self.resource_search_input.setFont(QFont("Segoe UI", 12))
        self.resource_search_input.textChanged.connect(self.filter_resource_table)

        resource_search_layout = QHBoxLayout()
        resource_search_layout.addWidget(QLabel("Filter Resources:"))
        resource_search_layout.addWidget(self.resource_search_input)

        urls_layout = QVBoxLayout()
        urls_layout.addWidget(urls_label)
        urls_layout.addWidget(self.urls_input)

        path_layout = QHBoxLayout()
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.browse_button)

        main_layout = QVBoxLayout()
        main_layout.addLayout(urls_layout)
        main_layout.addLayout(path_layout)
        main_layout.addSpacing(20)
        main_layout.addLayout(buttons_layout)
        main_layout.addWidget(self.progress_bar)
        main_layout.addLayout(resource_search_layout)
        main_layout.addWidget(self.resource_table)
        main_layout.addSpacing(10)
        main_layout.addWidget(self.status_label)
        main_layout.addSpacing(20)
        main_layout.addWidget(logs_card)
        main_layout.addStretch()

        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)

        self.setLayout(main_layout)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if folder:
            self.path_input.setText(folder)
            HistoryManager.add_history("Last Download Path", folder)

    def on_download(self):
        if self.downloader_thread and self.downloader_thread.isRunning():
            QMessageBox.warning(self, "Download in Progress", "A download is already in progress.")
            return

        urls_text = self.urls_input.toPlainText().strip()
        if not urls_text:
            QMessageBox.warning(self, "Input Error", "Please enter at least one URL.")
            return
        urls = [url.strip() for url in urls_text.splitlines() if url.strip()]
        if not urls:
            QMessageBox.warning(self, "Input Error", "Please enter valid URLs.")
            return
        if not self.path_input.text().strip():
            QMessageBox.warning(self, "Input Error", "Please select a download path.")
            return

        from datetime import datetime

        if SettingsManager.get_setting('schedule_download'):
            schedule_time_str = SettingsManager.get_setting('schedule_time')
            schedule_time = QTime.fromString(schedule_time_str, "HH:mm")
            current_time = QTime.currentTime()
            if schedule_time > current_time:
                msecs_until = current_time.msecsTo(schedule_time)
                self.schedule_timer = QTimer(self)
                self.schedule_timer.setSingleShot(True)
                self.schedule_timer.timeout.connect(lambda: self.start_download(urls))
                self.schedule_timer.start(msecs_until)
                self.status_label.setText(f"⏳ Download scheduled at {schedule_time_str}...")
                return
            # else start immediately if time is past

        self.start_download(urls)

    def start_download(self, urls):
        resource_types = []
        settings_rt = SettingsManager.get_setting('default_resource_types')
        for rtype in ['css', 'js', 'images', 'fonts', 'videos', 'svg', 'documents']:
            if settings_rt.get(rtype, False):
                resource_types.append(rtype)

        if not resource_types:
            QMessageBox.warning(self, "Input Error", "Please select at least one resource type in settings.")
            return

        exclusions = SettingsManager.get_setting('exclusions')
        timeout = SettingsManager.get_setting('timeout')
        retries = SettingsManager.get_setting('retries')
        max_depth = SettingsManager.get_setting('max_depth')
        concurrency = SettingsManager.get_setting('concurrency')
        proxy = SettingsManager.get_setting('proxy')
        robots_txt = SettingsManager.get_setting('robots_txt')
        rate_limit = SettingsManager.get_setting('rate_limit')
        user_agent = SettingsManager.get_setting('user_agent')
        ignore_https_errors = SettingsManager.get_setting('ignore_https_errors')
        max_file_size = SettingsManager.get_setting('max_file_size')
        download_structure = SettingsManager.get_setting('download_structure')
        follow_external_links = SettingsManager.get_setting('follow_external_links')
        custom_headers = SettingsManager.get_setting('custom_headers')
        basic_auth_user = SettingsManager.get_setting('basic_auth_user')
        basic_auth_pass = SettingsManager.get_setting('basic_auth_pass')
        ignore_mime_types = SettingsManager.get_setting('ignore_mime_types')

        self.download_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.resume_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.stop_event.clear()

        self.progress_bar.show()
        self.progress_bar.setValue(0)
        self.logs_text.clear()
        self.resource_table.setRowCount(0)
        self.resource_table.show()
        self.status_label.setText("⏳ Download started...")

        self.downloader_thread = DownloaderThread(
            urls=urls,
            path=self.path_input.text().strip(),
            user_agent=user_agent,
            resource_types=resource_types,
            timeout=timeout,
            retries=retries,
            max_depth=max_depth,
            concurrency=concurrency,
            proxy=proxy,
            exclusions=exclusions,
            robots_txt=robots_txt,
            rate_limit=rate_limit,
            ignore_https_errors=ignore_https_errors,
            max_file_size=max_file_size,
            download_structure=download_structure,
            follow_external_links=follow_external_links,
            custom_headers=custom_headers,
            basic_auth_user=basic_auth_user,
            basic_auth_pass=basic_auth_pass,
            ignore_mime_types=ignore_mime_types,
            stop_event=self.stop_event
        )
        self.downloader_thread.progress.connect(self.update_progress)
        self.downloader_thread.status.connect(self.update_status)
        self.downloader_thread.log.connect(self.update_logs)
        self.downloader_thread.resource_downloaded.connect(self.update_resource_table)
        self.downloader_thread.finished_download.connect(self.download_finished)
        self.downloader_thread.start()

        for url in urls:
            HistoryManager.add_history(url, self.path_input.text().strip())

    def pause_download(self):
        if self.downloader_thread and self.downloader_thread.isRunning():
            self.downloader_thread.pause()
            self.pause_button.setEnabled(False)
            self.resume_button.setEnabled(True)
            self.update_status("⏸️ Download paused.")

    def resume_download(self):
        if self.downloader_thread and self.downloader_thread.isRunning():
            self.downloader_thread.resume()
            self.pause_button.setEnabled(True)
            self.resume_button.setEnabled(False)
            self.update_status("▶️ Download resumed.")

    def stop_download(self):
        if self.downloader_thread and self.downloader_thread.isRunning():
            self.stop_event.set()
            self.update_status("🛑 Stopping download...")

    def clear_logs(self):
        self.logs_text.clear()

    def is_valid_url(self, url):
        parsed = urlparse(url)
        return all([parsed.scheme, parsed.netloc])

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_status(self, message):
        self.status_label.setText(message)

    def update_logs(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.logs_text.append(f"[{timestamp}] {message}")
        self.logs_text.verticalScrollBar().setValue(self.logs_text.verticalScrollBar().maximum())

    def update_resource_table(self, url, status, path):
        print("update_resource_table called")
        for row in range(self.resource_table.rowCount()):
            item = self.resource_table.item(row, 0)
            if item and item.text() == url:
                self.resource_table.setItem(row, 1, QTableWidgetItem(status))
                self.resource_table.setItem(row, 2, QTableWidgetItem(path))
                self.color_status_cell(row, status)
                return
        row_position = self.resource_table.rowCount()
        self.resource_table.insertRow(row_position)
        self.resource_table.setItem(row_position, 0, QTableWidgetItem(url))
        self.resource_table.setItem(row_position, 1, QTableWidgetItem(status))
        self.resource_table.setItem(row_position, 2, QTableWidgetItem(path))
        self.color_status_cell(row_position, status)

    def color_status_cell(self, row, status):
        status_item = self.resource_table.item(row, 1)
        if "✅" in status:
            status_item.setForeground(QBrush(QColor("green")))
        elif "❌" in status:
            status_item.setForeground(QBrush(QColor("red")))
        elif "⚠️" in status:
            status_item.setForeground(QBrush(QColor("orange")))
        else:
            status_item.setForeground(QBrush(QColor("white")))

    def filter_resource_table(self, text):
        for row in range(self.resource_table.rowCount()):
            item = self.resource_table.item(row, 0)
            if text.lower() in item.text().lower():
                self.resource_table.setRowHidden(row, False)
            else:
                self.resource_table.setRowHidden(row, True)

    def download_finished(self, success, message):
        if success:
            QMessageBox.information(self, "Success", message)
        else:
            QMessageBox.critical(self, "Error", message)
        self.download_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.resume_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.progress_bar.hide()
        self.status_label.setText("Download finished.")

        # If PyQtWebEngine is available, add a preview button if last downloaded page exists
        if WEBENGINE_AVAILABLE:
            if self.resource_table.rowCount() > 0:
                last_path = self.resource_table.item(self.resource_table.rowCount()-1, 2)
                if last_path and os.path.exists(os.path.dirname(last_path.text())):
                    if not self.preview_button:
                        self.preview_button = QPushButton("Preview Last Downloaded Page")
                        self.preview_button.setFont(QFont("Segoe UI", 12))
                        self.preview_button.setStyleSheet("""
                            QPushButton {
                                background-color: #1e90ff;
                                color: white;
                                border-radius: 0px;
                            }
                            QPushButton:hover {
                                background-color: #63b8ff;
                            }
                            QPushButton:pressed {
                                background-color: #4682b4;
                            }
                        """)
                        self.preview_button.clicked.connect(lambda: self.preview_page(last_path.text()))
                        self.layout().addWidget(self.preview_button)

        # Add "Open Download Folder" button to quickly open the last download path
        if self.resource_table.rowCount() > 0:
            last_row = self.resource_table.rowCount() - 1
            path_item = self.resource_table.item(last_row, 2)
            if path_item and os.path.exists(os.path.dirname(path_item.text())):
                if not self.open_folder_button:
                    self.open_folder_button = QPushButton("Open Download Folder")
                    self.open_folder_button.setFont(QFont("Segoe UI", 12))
                    self.open_folder_button.setStyleSheet("""
                        QPushButton {
                            background-color: #1e90ff;
                            color: white;
                            border-radius: 0px;
                        }
                        QPushButton:hover {
                            background-color: #63b8ff;
                        }
                        QPushButton:pressed {
                            background-color: #4682b4;
                        }
                    """)
                    self.open_folder_button.clicked.connect(lambda: self.open_folder(path_item.text()))
                    self.layout().addWidget(self.open_folder_button)

    def preview_page(self, path):
        if not WEBENGINE_AVAILABLE:
            QMessageBox.information(self, "Preview Unavailable", "PyQtWebEngine is not installed.")
            return

        if not os.path.exists(path):
            QMessageBox.information(self, "File Not Found", "The requested file does not exist.")
            return

        preview_window = QWebEngineView()
        preview_window.setWindowTitle("Preview")
        preview_window.load(QUrl.fromLocalFile(os.path.abspath(path)))
        preview_window.setMinimumSize(800,600)
        preview_window.show()

    def open_folder(self, file_path):
        folder = os.path.dirname(file_path)
        if sys.platform.startswith('darwin'):
            os.system(f'open "{folder}"')
        elif os.name == 'nt':
            os.startfile(folder)  # type: ignore
        elif os.name == 'posix':
            os.system(f'xdg-open "{folder}"')

# ------------------------ History Widget ------------------------
class HistoryWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        search_label = QLabel("Search History:")
        search_label.setFont(QFont("Segoe UI", 12))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by URL...")
        self.search_input.setFont(QFont("Segoe UI", 12))
        self.search_input.textChanged.connect(self.filter_history)

        self.history_list = QListWidget()
        self.load_history()
        self.history_list.setFont(QFont("Segoe UI", 12))
        self.history_list.setStyleSheet("""
            QListWidget {
                background-color: #3c3c3c;
                border: none;
                border-radius: 0px;
                padding: 5px;
                color: #ffffff;
            }
            QListWidget::item:selected {
                background-color: #1e90ff;
                color: #ffffff;
            }
        """)

        self.open_button = QPushButton("Open Folder")
        self.open_button.setFont(QFont("Segoe UI", 12))
        self.open_button.setFixedHeight(40)
        self.open_button.setStyleSheet("""
            QPushButton {
                background-color: #1e90ff;
                color: white;
                border-radius: 0px;
            }
            QPushButton:hover {
                background-color: #63b8ff;
            }
            QPushButton:pressed {
                background-color: #4682b4;
            }
        """)
        self.open_button.clicked.connect(self.open_selected)

        self.clear_button = QPushButton("Clear History")
        self.clear_button.setFont(QFont("Segoe UI", 12))
        self.clear_button.setFixedHeight(40)
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #ff4d4d;
                color: white;
                border-radius: 0px;
            }
            QPushButton:hover {
                background-color: #ff6666;
            }
            QPushButton:pressed {
                background-color: #e60000;
            }
        """)
        self.clear_button.clicked.connect(self.clear_history)

        search_layout = QHBoxLayout()
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.open_button)
        buttons_layout.addWidget(self.clear_button)

        main_layout = QVBoxLayout()
        main_layout.addLayout(search_layout)
        main_layout.addWidget(self.history_list)
        main_layout.addSpacing(20)
        main_layout.addLayout(buttons_layout)
        main_layout.addStretch()

        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)

        self.setLayout(main_layout)

    def load_history(self):
        history = HistoryManager.get_history()
        self.history_list.clear()
        for entry in history:
            self.history_list.addItem(entry)

    def filter_history(self, text):
        for i in range(self.history_list.count()):
            item = self.history_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def open_selected(self):
        selected = self.history_list.currentItem()
        if selected:
            url = selected.text()
            download_path = HistoryManager.get_download_path(url)
            if download_path and os.path.exists(download_path):
                try:
                    if sys.platform.startswith('darwin'):
                        os.system(f'open "{download_path}"')
                    elif os.name == 'nt':
                        os.startfile(download_path)  # type: ignore
                    elif os.name == 'posix':
                        os.system(f'xdg-open "{download_path}"')
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to open folder: {e}")
            else:
                QMessageBox.warning(self, "Error", "Download path does not exist.")

    def clear_history(self):
        confirm = QMessageBox.question(
            self, "Clear History",
            "Are you sure you want to clear the download history?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            HistoryManager.clear_history()
            self.load_history()
            QMessageBox.information(self, "Success", "✅ Download history cleared.")

class SettingsWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_current_settings()

    def init_ui(self):
        self.tabs = QTabWidget()
        self.tabs.setFont(QFont("Segoe UI", 12))
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border-top: 2px solid #C2C7CB;
                background-color: #2b2b2b;
            }
            QTabBar::tab {
                background: #1e1e1e;
                color: #ffffff;
                padding: 10px;
                border: 1px solid #444444;
                border-bottom: none;
                min-width: 120px;
                font: 14px "Segoe UI";
            }
            QTabBar::tab:selected {
                background: #333333;
                color: #1e90ff;
            }
        """)

        self.general_tab = QWidget()
        self.appearance_tab = QWidget()
        self.downloads_tab = QWidget()
        self.network_tab = QWidget()
        self.logging_tab = QWidget()
        self.exclusions_tab = QWidget()
        self.advanced_tab = QWidget()

        self.init_general_tab()
        self.init_appearance_tab()
        self.init_downloads_tab()
        self.init_network_tab()
        self.init_logging_tab()
        self.init_exclusions_tab()
        self.init_advanced_tab()

        self.tabs.addTab(self.general_tab, QIcon("icons/general.png"), "General")
        self.tabs.addTab(self.appearance_tab, QIcon("icons/appearance.png"), "Appearance")
        self.tabs.addTab(self.downloads_tab, QIcon("icons/downloads.png"), "Downloads")
        self.tabs.addTab(self.network_tab, QIcon("icons/network.png"), "Network")
        self.tabs.addTab(self.logging_tab, QIcon("icons/logging.png"), "Logging")
        self.tabs.addTab(self.exclusions_tab, QIcon("icons/exclusions.png"), "Exclusions")
        self.tabs.addTab(self.advanced_tab, QIcon("icons/advanced.png"), "Advanced")

        self.save_button = QPushButton("Save Settings")
        self.save_button.setFont(QFont("Segoe UI", 12))
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #32cd32;
                color: white;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #45da45;
            }
            QPushButton:pressed {
                background-color: #28a428;
            }
        """)
        self.save_button.clicked.connect(self.save_settings)

        self.reset_button = QPushButton("Reset to Default")
        self.reset_button.setFont(QFont("Segoe UI", 12))
        self.reset_button.setStyleSheet("""
            QPushButton {
                background-color: #ff4d4d;
                color: white;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #ff6666;
            }
            QPushButton:pressed {
                background-color: #e60000;
            }
        """)
        self.reset_button.clicked.connect(self.reset_to_default)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.reset_button)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tabs)
        main_layout.addLayout(button_layout)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)

        self.setLayout(main_layout)
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
                font-family: "Segoe UI";
            }
            QLabel {
                font-size: 14px;
                color: #ffffff;
            }
            QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox, QTimeEdit {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px;
                color: #ffffff;
                font-size: 14px;
            }
            QGroupBox {
                border: 1px solid #555555;
                border-radius: 4px;
                margin-top: 20px;
                font: 14px "Segoe UI";
                color: #ffffff;
            }
            QGroupBox:title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 10px;
            }
        """)

    def init_general_tab(self):
        layout = QFormLayout()
        self.user_agent_combobox = QComboBox()
        predefined_user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:104.0) Gecko/20100101 Firefox/104.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Mobile Safari/537.36",
            "Custom"
        ]
        self.user_agent_combobox.addItems(predefined_user_agents)
        self.user_agent_combobox.currentIndexChanged.connect(self.user_agent_selection_changed)

        self.custom_user_agent_input = QLineEdit()
        self.custom_user_agent_input.setPlaceholderText("Enter custom User-Agent...")
        self.custom_user_agent_input.setEnabled(False)

        ua_layout = QVBoxLayout()
        ua_layout.addWidget(self.user_agent_combobox)
        ua_layout.addWidget(self.custom_user_agent_input)
        ua_widget = QWidget()
        ua_widget.setLayout(ua_layout)

        layout.addRow(QLabel("User-Agent:"), ua_widget)
        self.general_tab.setLayout(layout)

    def init_appearance_tab(self):
        layout = QFormLayout()
        self.theme_combobox = QComboBox()
        self.theme_combobox.addItems(["Dark", "Light"])

        self.language_combobox = QComboBox()
        self.language_combobox.addItems(["English", "Spanish", "French", "German"])

        self.interface_scale_spinbox = QDoubleSpinBox()
        self.interface_scale_spinbox.setRange(0.5, 2.0)
        self.interface_scale_spinbox.setSingleStep(0.1)

        self.show_toolbar_checkbox = QCheckBox("Show Toolbar")
        self.enable_notifications_checkbox = QCheckBox("Enable Notifications")

        layout.addRow(QLabel("Theme:"), self.theme_combobox)
        layout.addRow(QLabel("Language:"), self.language_combobox)
        layout.addRow(QLabel("Interface Scale:"), self.interface_scale_spinbox)
        layout.addRow("", self.show_toolbar_checkbox)
        layout.addRow("", self.enable_notifications_checkbox)
        self.appearance_tab.setLayout(layout)

    def init_downloads_tab(self):
        main_layout = QVBoxLayout()
        form = QFormLayout()

        self.timeout_spinbox = QSpinBox()
        self.timeout_spinbox.setRange(1, 120)

        self.retries_spinbox = QSpinBox()
        self.retries_spinbox.setRange(0, 10)

        self.depth_spinbox = QSpinBox()
        self.depth_spinbox.setRange(1, 20)

        self.concurrency_spinbox = QSpinBox()
        self.concurrency_spinbox.setRange(1, 20)

        self.max_file_size_spinbox = QSpinBox()
        self.max_file_size_spinbox.setRange(0, 1024)

        self.download_structure_combobox = QComboBox()
        self.download_structure_combobox.addItems(["keep", "flatten"])

        self.download_after_crawl_checkbox = QCheckBox("Download After Crawl")

        form.addRow(QLabel("Timeout (s):"), self.timeout_spinbox)
        form.addRow(QLabel("Retries:"), self.retries_spinbox)
        form.addRow(QLabel("Max Depth:"), self.depth_spinbox)
        form.addRow(QLabel("Concurrency:"), self.concurrency_spinbox)
        form.addRow(QLabel("Max File Size (MB):"), self.max_file_size_spinbox)
        form.addRow(QLabel("Download Structure:"), self.download_structure_combobox)
        form.addRow("", self.download_after_crawl_checkbox)

        resource_group = QGroupBox("Resource Types")

        self.html_checkbox = QCheckBox("HTML")
        self.css_checkbox = QCheckBox("CSS")
        self.js_checkbox = QCheckBox("JavaScript")
        self.images_checkbox = QCheckBox("Images")
        self.fonts_checkbox = QCheckBox("Fonts")
        self.videos_checkbox = QCheckBox("Videos")
        self.svg_checkbox = QCheckBox("SVG")
        self.documents_checkbox = QCheckBox("Documents")

        resource_layout = QGridLayout()
        resource_layout.addWidget(self.html_checkbox, 0, 0)
        resource_layout.addWidget(self.css_checkbox, 0, 1)
        resource_layout.addWidget(self.js_checkbox, 1, 0)
        resource_layout.addWidget(self.images_checkbox, 1, 1)
        resource_layout.addWidget(self.fonts_checkbox, 2, 0)
        resource_layout.addWidget(self.videos_checkbox, 2, 1)
        resource_layout.addWidget(self.svg_checkbox, 3, 0)
        resource_layout.addWidget(self.documents_checkbox, 3, 1)
        resource_group.setLayout(resource_layout)

        main_layout.addLayout(form)
        main_layout.addWidget(resource_group)
        self.downloads_tab.setLayout(main_layout)

    def init_network_tab(self):
        form = QFormLayout()

        self.proxy_address_input = QLineEdit()
        self.proxy_address_input.setPlaceholderText("http://proxy:port")

        self.proxy_auth_checkbox = QCheckBox("Use Proxy Authentication")
        self.proxy_auth_checkbox.stateChanged.connect(self.toggle_proxy_auth_fields)

        self.proxy_username_input = QLineEdit()
        self.proxy_username_input.setPlaceholderText("Username")
        self.proxy_username_input.setVisible(False)

        self.proxy_password_input = QLineEdit()
        self.proxy_password_input.setPlaceholderText("Password")
        self.proxy_password_input.setEchoMode(QLineEdit.Password)
        self.proxy_password_input.setVisible(False)

        self.robots_checkbox = QCheckBox("Respect robots.txt")
        self.ignore_https_checkbox = QCheckBox("Ignore HTTPS Errors")

        self.rate_limit_spinbox = QDoubleSpinBox()
        self.rate_limit_spinbox.setRange(0, 5)
        self.rate_limit_spinbox.setDecimals(2)

        self.include_subdomains_checkbox = QCheckBox("Include Subdomains")

        form.addRow(QLabel("Proxy:"), self.proxy_address_input)
        form.addRow("", self.proxy_auth_checkbox)
        form.addRow(QLabel("Proxy Username:"), self.proxy_username_input)
        form.addRow(QLabel("Proxy Password:"), self.proxy_password_input)
        form.addRow("", self.robots_checkbox)
        form.addRow("", self.ignore_https_checkbox)
        form.addRow(QLabel("Rate Limit (s):"), self.rate_limit_spinbox)
        form.addRow("", self.include_subdomains_checkbox)
        self.network_tab.setLayout(form)

    def init_logging_tab(self):
        form = QFormLayout()

        self.enable_logging_checkbox = QCheckBox("Enable Logging")

        self.log_level_combobox = QComboBox()
        self.log_level_combobox.addItems(["INFO", "DEBUG", "ERROR"])

        self.default_save_location_input = QLineEdit()
        self.default_save_location_input.setPlaceholderText("Choose a folder...")
        self.default_save_location_browse = QPushButton("Browse")
        self.default_save_location_browse.setFixedWidth(80)
        self.default_save_location_browse.clicked.connect(self.browse_default_save_location)

        save_loc_layout = QHBoxLayout()
        save_loc_layout.addWidget(self.default_save_location_input)
        save_loc_layout.addWidget(self.default_save_location_browse)
        save_loc_widget = QWidget()
        save_loc_widget.setLayout(save_loc_layout)

        export_log_button = QPushButton("Export Logs")
        export_log_button.setFont(QFont("Segoe UI", 12))
        export_log_button.clicked.connect(self.export_logs)

        form.addRow("", self.enable_logging_checkbox)
        form.addRow(QLabel("Log Level:"), self.log_level_combobox)
        form.addRow(QLabel("Default Save Location:"), save_loc_widget)
        form.addRow("", export_log_button)
        self.logging_tab.setLayout(form)

    def init_exclusions_tab(self):
        layout = QVBoxLayout()
        exclusions_label = QLabel("Enter paths or file extensions to exclude, one per line (e.g., /admin, .zip):")

        self.exclusions_input = QTextEdit()
        self.exclusions_input.setFont(QFont("Segoe UI", 12))
        self.exclusions_input.setPlaceholderText("/admin\n.zip")

        layout.addWidget(exclusions_label)
        layout.addWidget(self.exclusions_input)
        self.exclusions_tab.setLayout(layout)

    def init_advanced_tab(self):
        form = QFormLayout()

        self.follow_external_links_checkbox = QCheckBox("Follow External Links")
        self.schedule_download_checkbox = QCheckBox("Schedule Download")
        self.schedule_time_edit = QTimeEdit()
        self.schedule_time_edit.setDisplayFormat("HH:mm")

        self.headers_table = QTableWidget()
        self.headers_table.setColumnCount(2)
        self.headers_table.setHorizontalHeaderLabels(["Header Key", "Header Value"])
        self.headers_table.horizontalHeader().setStretchLastSection(True)

        add_header_button = QPushButton("Add Header")
        remove_header_button = QPushButton("Remove Selected Header")
        add_header_button.setFont(QFont("Segoe UI", 10))
        remove_header_button.setFont(QFont("Segoe UI", 10))
        add_header_button.clicked.connect(self.add_header_row)
        remove_header_button.clicked.connect(self.remove_header_row)

        headers_button_layout = QHBoxLayout()
        headers_button_layout.addWidget(add_header_button)
        headers_button_layout.addWidget(remove_header_button)
        hb_widget = QWidget()
        hb_widget.setLayout(headers_button_layout)

        self.basic_auth_user_input = QLineEdit()
        self.basic_auth_user_input.setPlaceholderText("User")

        self.basic_auth_pass_input = QLineEdit()
        self.basic_auth_pass_input.setPlaceholderText("Password")
        self.basic_auth_pass_input.setEchoMode(QLineEdit.Password)

        self.ignore_mime_types_input = QTextEdit()
        self.ignore_mime_types_input.setPlaceholderText("application/octet-stream\nimage/x-icon")

        form.addRow("", self.follow_external_links_checkbox)
        form.addRow("Schedule Download:", self.schedule_download_checkbox)
        form.addRow("Schedule Time:", self.schedule_time_edit)
        form.addRow(QLabel("Custom Headers:"), self.headers_table)
        form.addRow("", hb_widget)
        form.addRow("Basic Auth User:", self.basic_auth_user_input)
        form.addRow("Basic Auth Password:", self.basic_auth_pass_input)
        form.addRow("Ignore MIME Types:", self.ignore_mime_types_input)
        self.advanced_tab.setLayout(form)


    def user_agent_selection_changed(self, index):
        if self.user_agent_combobox.currentText() == "Custom":
            self.custom_user_agent_input.setEnabled(True)
        else:
            self.custom_user_agent_input.setEnabled(False)

    def toggle_proxy_auth_fields(self, state):
        if state == Qt.Checked:
            self.proxy_username_input.setVisible(True)
            self.proxy_password_input.setVisible(True)
        else:
            self.proxy_username_input.setVisible(False)
            self.proxy_password_input.setVisible(False)

    def browse_default_save_location(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Default Save Folder")
        if folder:
            self.default_save_location_input.setText(folder)

    def export_logs(self):
        with open("download_log.txt", 'w') as f:
            f.write("This is a sample exported log.\n")
        QMessageBox.information(self, "Logs Exported", "Logs have been exported to download_log.txt.")

    def add_header_row(self):
        row = self.headers_table.rowCount()
        self.headers_table.insertRow(row)
        self.headers_table.setItem(row, 0, QTableWidgetItem(""))
        self.headers_table.setItem(row, 1, QTableWidgetItem(""))

    def remove_header_row(self):
        selected = self.headers_table.selectedItems()
        if selected:
            row = selected[0].row()
            self.headers_table.removeRow(row)

    def load_current_settings(self):
        # Load settings
        user_agent = SettingsManager.get_setting('user_agent')
        predefined_user_agents = [self.user_agent_combobox.itemText(i) for i in range(self.user_agent_combobox.count())]
        if user_agent in predefined_user_agents[:-1]:
            # Matches a predefined user agent
            self.user_agent_combobox.setCurrentIndex(predefined_user_agents.index(user_agent))
            self.custom_user_agent_input.setEnabled(False)
        else:
            # Use custom user agent
            self.user_agent_combobox.setCurrentIndex(len(predefined_user_agents)-1)
            self.custom_user_agent_input.setEnabled(True)
            self.custom_user_agent_input.setText(user_agent)

        self.theme_combobox.setCurrentText(SettingsManager.get_setting('theme'))
        self.language_combobox.setCurrentText(SettingsManager.get_setting('language'))

        self.timeout_spinbox.setValue(SettingsManager.get_setting('timeout'))
        self.retries_spinbox.setValue(SettingsManager.get_setting('retries'))
        self.depth_spinbox.setValue(SettingsManager.get_setting('max_depth'))
        self.concurrency_spinbox.setValue(SettingsManager.get_setting('concurrency'))
        self.rate_limit_spinbox.setValue(SettingsManager.get_setting('rate_limit'))
        self.max_file_size_spinbox.setValue(SettingsManager.get_setting('max_file_size'))
        self.download_structure_combobox.setCurrentText(SettingsManager.get_setting('download_structure'))

        proxy = SettingsManager.get_setting('proxy')
        if proxy and isinstance(proxy, dict):
            http_proxy = proxy.get('http', '')
            if '://' in http_proxy:
                parsed = urlparse(http_proxy)
                host_port = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
                self.proxy_address_input.setText(host_port)
                if parsed.username and parsed.password:
                    self.proxy_auth_checkbox.setChecked(True)
                    self.proxy_username_input.setText(parsed.username)
                    self.proxy_password_input.setText(parsed.password)
                else:
                    self.proxy_auth_checkbox.setChecked(False)
                    self.proxy_username_input.clear()
                    self.proxy_password_input.clear()
            else:
                self.proxy_address_input.setText(http_proxy)
                self.proxy_auth_checkbox.setChecked(False)
                self.proxy_username_input.clear()
                self.proxy_password_input.clear()
        else:
            self.proxy_address_input.clear()
            self.proxy_auth_checkbox.setChecked(False)
            self.proxy_username_input.clear()
            self.proxy_password_input.clear()

        self.robots_checkbox.setChecked(SettingsManager.get_setting('robots_txt'))
        self.ignore_https_checkbox.setChecked(SettingsManager.get_setting('ignore_https_errors'))
        self.enable_logging_checkbox.setChecked(SettingsManager.get_setting('enable_logging'))
        self.log_level_combobox.setCurrentText(SettingsManager.get_setting('log_level'))
        self.default_save_location_input.setText(SettingsManager.get_setting('default_save_location'))

        exclusions = SettingsManager.get_setting('exclusions')
        self.exclusions_input.setText("\n".join(exclusions))

        self.interface_scale_spinbox.setValue(SettingsManager.get_setting('interface_scale'))
        self.enable_notifications_checkbox.setChecked(SettingsManager.get_setting('enable_notifications'))
        self.show_toolbar_checkbox.setChecked(SettingsManager.get_setting('show_toolbar'))
        self.download_after_crawl_checkbox.setChecked(SettingsManager.get_setting('download_after_crawl'))
        self.include_subdomains_checkbox.setChecked(SettingsManager.get_setting('include_subdomains'))

        self.follow_external_links_checkbox.setChecked(SettingsManager.get_setting('follow_external_links'))
        self.schedule_download_checkbox.setChecked(SettingsManager.get_setting('schedule_download'))
        schedule_time_str = SettingsManager.get_setting('schedule_time')
        self.schedule_time_edit.setTime(QTime.fromString(schedule_time_str, "HH:mm"))
        custom_headers = SettingsManager.get_setting('custom_headers')
        self.headers_table.setRowCount(0)
        for header in custom_headers:
            row = self.headers_table.rowCount()
            self.headers_table.insertRow(row)
            self.headers_table.setItem(row, 0, QTableWidgetItem(header.get("key", "")))
            self.headers_table.setItem(row, 1, QTableWidgetItem(header.get("value", "")))

        self.basic_auth_user_input.setText(SettingsManager.get_setting('basic_auth_user'))
        self.basic_auth_pass_input.setText(SettingsManager.get_setting('basic_auth_pass'))

        ignore_mime_types = SettingsManager.get_setting('ignore_mime_types')
        self.ignore_mime_types_input.setText("\n".join(ignore_mime_types))

        # Load default resource types
        default_resources = SettingsManager.get_setting('default_resource_types')
        self.html_checkbox.setChecked(default_resources.get('html', True))
        self.css_checkbox.setChecked(default_resources.get('css', True))
        self.js_checkbox.setChecked(default_resources.get('js', True))
        self.images_checkbox.setChecked(default_resources.get('images', True))
        self.fonts_checkbox.setChecked(default_resources.get('fonts', False))
        self.videos_checkbox.setChecked(default_resources.get('videos', False))
        self.svg_checkbox.setChecked(default_resources.get('svg', False))
        self.documents_checkbox.setChecked(default_resources.get('documents', False))

    def save_settings(self):
        if self.user_agent_combobox.currentText() == "Custom":
            user_agent = self.custom_user_agent_input.text().strip()
            if not user_agent:
                QMessageBox.warning(self, "Input Error", "Custom User-Agent cannot be empty.")
                return
        else:
            user_agent = self.user_agent_combobox.currentText()

        timeout = self.timeout_spinbox.value()
        retries = self.retries_spinbox.value()
        max_depth = self.depth_spinbox.value()
        concurrency = self.concurrency_spinbox.value()

        proxy_address = self.proxy_address_input.text().strip()
        if self.proxy_auth_checkbox.isChecked():
            proxy_username = self.proxy_username_input.text().strip()
            proxy_password = self.proxy_password_input.text().strip()
            if proxy_username and proxy_password:
                proxy = {
                    "http": f"http://{proxy_username}:{proxy_password}@{proxy_address}",
                    "https": f"http://{proxy_username}:{proxy_password}@{proxy_address}"
                }
            else:
                QMessageBox.warning(self, "Input Error", "Please enter both proxy username and password.")
                return
        else:
            if proxy_address:
                proxy = {
                    "http": proxy_address,
                    "https": proxy_address
                }
            else:
                proxy = None

        robots_txt = self.robots_checkbox.isChecked()
        rate_limit = self.rate_limit_spinbox.value()
        ignore_https = self.ignore_https_checkbox.isChecked()
        max_file_size = self.max_file_size_spinbox.value()
        download_structure = self.download_structure_combobox.currentText()

        exclusions_text = self.exclusions_input.toPlainText().strip()
        exclusions = [line.strip() for line in exclusions_text.splitlines() if line.strip()]

        theme = self.theme_combobox.currentText()
        language = self.language_combobox.currentText()
        enable_logging = self.enable_logging_checkbox.isChecked()
        log_level = self.log_level_combobox.currentText()
        default_save_location = self.default_save_location_input.text().strip()

        interface_scale = self.interface_scale_spinbox.value()
        enable_notifications = self.enable_notifications_checkbox.isChecked()
        show_toolbar = self.show_toolbar_checkbox.isChecked()
        download_after_crawl = self.download_after_crawl_checkbox.isChecked()
        include_subdomains = self.include_subdomains_checkbox.isChecked()

        follow_external_links = self.follow_external_links_checkbox.isChecked()
        schedule_download = self.schedule_download_checkbox.isChecked()
        schedule_time_str = self.schedule_time_edit.time().toString("HH:mm")

        custom_headers = []
        for row in range(self.headers_table.rowCount()):
            key_item = self.headers_table.item(row, 0)
            value_item = self.headers_table.item(row, 1)
            if key_item and value_item:
                k = key_item.text().strip()
                v = value_item.text().strip()
                if k and v:
                    custom_headers.append({"key": k, "value": v})

        basic_auth_user = self.basic_auth_user_input.text().strip()
        basic_auth_pass = self.basic_auth_pass_input.text().strip()

        ignore_mime_types_text = self.ignore_mime_types_input.toPlainText().strip()
        ignore_mime_types = [line.strip() for line in ignore_mime_types_text.splitlines() if line.strip()]

        # New default resource types based on checkboxes
        new_default_resources = {
            'html': self.html_checkbox.isChecked(),
            'css': self.css_checkbox.isChecked(),
            'js': self.js_checkbox.isChecked(),
            'images': self.images_checkbox.isChecked(),
            'fonts': self.fonts_checkbox.isChecked(),
            'videos': self.videos_checkbox.isChecked(),
            'svg': self.svg_checkbox.isChecked(),
            'documents': self.documents_checkbox.isChecked()
        }

        SettingsManager.set_setting('user_agent', user_agent)
        SettingsManager.set_setting('timeout', timeout)
        SettingsManager.set_setting('retries', retries)
        SettingsManager.set_setting('max_depth', max_depth)
        SettingsManager.set_setting('concurrency', concurrency)
        SettingsManager.set_setting('proxy', proxy)
        SettingsManager.set_setting('robots_txt', robots_txt)
        SettingsManager.set_setting('rate_limit', rate_limit)
        SettingsManager.set_setting('exclusions', exclusions)
        SettingsManager.set_setting('ignore_https_errors', ignore_https)
        SettingsManager.set_setting('max_file_size', max_file_size)
        SettingsManager.set_setting('download_structure', download_structure)
        SettingsManager.set_setting('theme', theme)
        SettingsManager.set_setting('language', language)
        SettingsManager.set_setting('enable_logging', enable_logging)
        SettingsManager.set_setting('log_level', log_level)
        SettingsManager.set_setting('default_save_location', default_save_location)
        SettingsManager.set_setting('interface_scale', interface_scale)
        SettingsManager.set_setting('enable_notifications', enable_notifications)
        SettingsManager.set_setting('show_toolbar', show_toolbar)
        SettingsManager.set_setting('download_after_crawl', download_after_crawl)
        SettingsManager.set_setting('include_subdomains', include_subdomains)
        SettingsManager.set_setting('follow_external_links', follow_external_links)
        SettingsManager.set_setting('schedule_download', schedule_download)
        SettingsManager.set_setting('schedule_time', schedule_time_str)
        SettingsManager.set_setting('custom_headers', custom_headers)
        SettingsManager.set_setting('basic_auth_user', basic_auth_user)
        SettingsManager.set_setting('basic_auth_pass', basic_auth_pass)
        SettingsManager.set_setting('ignore_mime_types', ignore_mime_types)
        SettingsManager.set_setting('default_resource_types', new_default_resources)

        QMessageBox.information(self, "Success", "✅ Settings saved successfully.")

    def reset_to_default(self):
        confirm = QMessageBox.question(self, "Reset to Default",
                                       "Are you sure you want to reset all settings to default?",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm == QMessageBox.Yes:
            SettingsManager.reset_to_defaults()
            self.load_current_settings()
            QMessageBox.information(self, "Success", "✅ Settings have been reset to default.")


    # ------------------------ About Widget ------------------------
class AboutWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(20)

        # Title area
        title_layout = QHBoxLayout()
        title_layout.setSpacing(10)

        icon_label = QLabel()
        icon_pixmap = QPixmap("icons/app_icon.png").scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        icon_label.setPixmap(icon_pixmap)

        title_label = QLabel("About Web Downloader")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #ffffff;
            }
        """)

        title_layout.addWidget(icon_label, 0, Qt.AlignCenter)
        title_layout.addWidget(title_label, 0, Qt.AlignCenter | Qt.AlignVCenter)
        title_layout.addStretch()

        # Divider line
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)
        divider.setStyleSheet("border: 1px solid #555555;")

        # About content label
        about_label = QLabel()
        about_label.setWordWrap(True)
        about_label.setAlignment(Qt.AlignTop)
        about_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                background-color: #3c3c3c;
                font-family: "Segoe UI";
                font-size: 14px;
            }
            a {
                color: #1e90ff;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
            }
        """)
        about_label.setText("""
            <h2 style="margin-bottom:5px;">Version 3.1</h2>
            <p><b>Developed with Python and PyQt5.</b></p>
            <p>This application allows you to download entire websites for offline use, handling HTML pages, images, CSS, JS, fonts, and more. It provides an intuitive interface, customizable settings, and detailed logs to help you manage and monitor your downloads efficiently.</p>
            <p><strong>Developer:</strong> Robin Doak</p>
            <p><i>Icons by</i> <a href="https://www.flaticon.com/authors/freepik" target="_blank">Freepik</a> 
            <i>from</i> <a href="https://www.flaticon.com/" target="_blank">Flaticon</a></p>
            <p>Special thanks to the open-source community for providing invaluable tools and libraries. Your contributions and innovations inspire continuous improvement.</p>
        """)

        # Frame for the about content
        card_frame = QFrame()
        card_frame.setStyleSheet("""
            QFrame {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 8px;
            }
        """)
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(10)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background-color: #3c3c3c;")
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.addWidget(about_label)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)
        scroll.setWidget(scroll_widget)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #3c3c3c;
            }
            QScrollBar:vertical {
                background: #3c3c3c;
                width: 8px;
                margin: 2px;
            }
            QScrollBar::handle:vertical {
                background: #555555;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #777777;
            }
        """)

        card_layout.addWidget(scroll)
        card_frame.setLayout(card_layout)

        main_layout.addLayout(title_layout)
        main_layout.addWidget(divider)
        main_layout.addWidget(card_frame)
        main_layout.addStretch()

        self.setLayout(main_layout)
        # Ensure a solid background
        self.setStyleSheet("background-color: #2b2b2b;")



# ------------------------ Main Window ------------------------
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.title_bar = TitleBar(self)
        main_layout.addWidget(self.title_bar)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(200)
        self.sidebar.setStyleSheet("background-color: #1e1e1e;")

        self.sidebar_layout = QVBoxLayout()
        self.sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar_layout.setSpacing(0)

        self.logo = QLabel()
        logo_pixmap = QPixmap("icons/app_icon.png").scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.logo.setPixmap(logo_pixmap)
        self.logo.setAlignment(Qt.AlignCenter)
        self.logo.setStyleSheet("padding: 20px;")
        self.sidebar_layout.addWidget(self.logo)

        self.btn_home = SidebarButton("icons/home.png", "Home")
        self.btn_history = SidebarButton("icons/history.png", "History")
        self.btn_settings = SidebarButton("icons/settings.png", "Settings")
        self.btn_about = SidebarButton("icons/about.png", "About")
        self.btn_quit = SidebarButton("icons/quit.png", "Quit")

        self.btn_home.clicked.connect(lambda: self.switch_page(0))
        self.btn_history.clicked.connect(lambda: self.switch_page(1))
        self.btn_settings.clicked.connect(lambda: self.switch_page(2))
        self.btn_about.clicked.connect(lambda: self.switch_page(3))
        self.btn_quit.clicked.connect(self.close_application)

        self.sidebar_layout.addWidget(self.btn_home)
        self.sidebar_layout.addWidget(self.btn_history)
        self.sidebar_layout.addWidget(self.btn_settings)
        self.sidebar_layout.addWidget(self.btn_about)
        self.sidebar_layout.addStretch()
        self.sidebar_layout.addWidget(self.btn_quit)

        self.sidebar.setLayout(self.sidebar_layout)

        self.stack = QStackedWidget()
        self.home = HomeWidget()
        self.history = HistoryWidget()
        self.settings = SettingsWidget()
        self.about = AboutWidget()

        self.stack.addWidget(self.home)
        self.stack.addWidget(self.history)
        self.stack.addWidget(self.settings)
        self.stack.addWidget(self.about)

        content_layout.addWidget(self.sidebar)
        content_layout.addWidget(self.stack)

        main_layout.addLayout(content_layout)

        self.effect = QGraphicsOpacityEffect()
        self.stack.setGraphicsEffect(self.effect)
        self.animation = QPropertyAnimation(self.effect, b"opacity")
        self.animation.setDuration(500)
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation.start()

        self.setLayout(main_layout)

        self.active_button = self.btn_home
        self.btn_home.set_active(True)

        self.setWindowTitle("Web Downloader")
        self.setWindowIcon(QIcon("icons/app_icon.png"))
        self.resize(1200, 800)

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)
        self.highlight_button(index)
        self.fade_in()

    def highlight_button(self, index):
        buttons = [self.btn_home, self.btn_history, self.btn_settings, self.btn_about]
        for i, button in enumerate(buttons):
            button.set_active(i == index)

    def fade_in(self):
        self.effect = QGraphicsOpacityEffect()
        self.stack.setGraphicsEffect(self.effect)
        self.animation = QPropertyAnimation(self.effect, b"opacity")
        self.animation.setDuration(500)
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation.start()

    def close_application(self):
        choice = QMessageBox.question(self, 'Quit',
                                      "Are you sure you want to quit?", QMessageBox.Yes |
                                      QMessageBox.No, QMessageBox.No)
        if choice == QMessageBox.Yes:
            sys.exit()

# ------------------------ Main Application ------------------------
class MainApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        SettingsManager.load_settings()
        HistoryManager.load_history()
        # Apply QDarkStyle theme
        self.app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt5'))

        self.window = MainWindow()
        self.window.show()

    def run(self):
        sys.exit(self.app.exec_())

def main():
    main_app = MainApp()
    main_app.run()

if __name__ == "__main__":
    main()