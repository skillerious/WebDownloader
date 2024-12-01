# main.py

import sys
import os
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import json
import shutil
import threading
from queue import Queue
import time
from urllib.robotparser import RobotFileParser
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, 
    QHBoxLayout, QFileDialog, QProgressBar, QMessageBox, QListWidget, QTextEdit,
    QStackedWidget, QFormLayout, QComboBox, QFrame, QCheckBox, QSpinBox, QDoubleSpinBox,
    QSizePolicy, QGraphicsOpacityEffect, QScrollArea, QTabWidget, QGroupBox, QGridLayout
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, QPoint, QSize
from PyQt5.QtGui import QIcon, QFont, QPixmap, QColor, QPalette, QBrush

# Constants
SETTINGS_FILE = "settings.json"
HISTORY_FILE = "history.json"

class WebDownloader:
    def __init__(self, base_urls, download_path, user_agent, resource_types, timeout, retries, max_depth=2, concurrency=5, proxy=None, progress_callback=None, status_callback=None, log_callback=None, robots_txt=True, rate_limit=0.1):
        """
        Initializes the WebDownloader.

        :param base_urls: List of URLs of the websites to download.
        :param download_path: The local directory path where files will be saved.
        :param user_agent: The User-Agent string to use for HTTP requests.
        :param resource_types: A list of resource types to download (e.g., ['css', 'js', 'images']).
        :param timeout: Timeout duration for HTTP requests.
        :param retries: Number of retry attempts for failed downloads.
        :param max_depth: Maximum recursion depth for downloading linked pages.
        :param concurrency: Number of concurrent threads for resource downloading.
        :param proxy: Proxy server settings.
        :param progress_callback: Function to call with progress updates.
        :param status_callback: Function to call with status messages.
        :param log_callback: Function to call with log messages.
        :param robots_txt: Whether to respect robots.txt.
        :param rate_limit: Delay between requests in seconds.
        """
        self.base_urls = base_urls
        self.download_path = download_path
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': user_agent})
        if proxy:
            self.session.proxies.update(proxy)
        self.resource_types = resource_types
        self.timeout = timeout
        self.retries = retries
        self.max_depth = max_depth
        self.concurrency = concurrency
        self.progress_callback = progress_callback
        self.status_callback = status_callback
        self.log_callback = log_callback
        self.visited_urls = set()
        self.counted_urls = set()  # Separate set for counting phase
        self.total_resources = 0
        self.downloaded_resources = 0
        self.lock = threading.Lock()  # To synchronize access to shared resources
        self.rate_limit = rate_limit
        self.robots_txt = robots_txt

        # Debugging Statement
        if self.log_callback:
            self.log_callback(f"🔧 WebDownloader initialized with robots_txt={self.robots_txt}")
        
        # Queue for resource downloading threads
        self.resource_queue = Queue()

    def download_websites(self):
        """
        Starts the website downloading process for all URLs.
        """
        try:
            if not os.path.exists(self.download_path):
                os.makedirs(self.download_path)

            for base_url in self.base_urls:
                self.status_callback(f"🕵️‍♂️ Starting resource counting for {base_url}")
                self._count_total_resources(base_url, current_depth=0)
            
            self.status_callback("📦 Resource counting completed.")
            self.status_callback("🔄 Starting download...")

            for base_url in self.base_urls:
                self._download_page(base_url, self.download_path, current_depth=0)

            # Start resource downloader threads
            num_threads = min(self.concurrency, self.total_resources) if self.total_resources > 0 else 1
            threads = []
            for _ in range(num_threads):
                t = threading.Thread(target=self._download_resources_worker)
                t.daemon = True
                t.start()
                threads.append(t)

            # Wait for all resources to be downloaded
            self.resource_queue.join()

            if self.progress_callback:
                self.progress_callback(100)
            if self.log_callback:
                self.log_callback("✅ Download completed successfully.")
            return True, "✅ Download completed successfully."
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"❌ An error occurred: {e}")
            return False, f"❌ An error occurred: {e}"

    def _can_fetch(self, url):
        """
        Checks if the URL can be fetched based on robots.txt.

        :param url: The URL to check.
        :return: Boolean indicating if the URL can be fetched.
        """
        if not self.robots_txt:
            return True  # Bypass robots.txt checks

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
            # If robots.txt cannot be fetched, assume allowed
            return True

    def _count_total_resources(self, url, current_depth):
        """
        Counts the total number of resources to download for progress tracking.

        :param url: The URL of the page to parse.
        :param current_depth: The current recursion depth.
        """
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
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' not in content_type:
                self.log_callback(f"⚠️ Skipping non-HTML content: {url}")
                return

            html_content = response.text
            soup = BeautifulSoup(html_content, 'html.parser')

            # Count resources
            resources = self._parse_resources(soup, url)
            self.total_resources += len(resources)
            self.log_callback(f"📝 Found {len(resources)} resources on {url}")

            # Find and count linked pages recursively
            linked_pages = self._find_linked_pages(soup, url)
            for link in linked_pages:
                full_link = urljoin(url, link)
                self._count_total_resources(full_link, current_depth + 1)

            # Rate limiting
            time.sleep(self.rate_limit)

        except requests.RequestException as e:
            self.log_callback(f"❌ Failed to access {url}: {e}")

    def _download_page(self, url, path, current_depth):
        """
        Downloads a single page and enqueues its resources.

        :param url: The URL of the page to download.
        :param path: The local directory path where files will be saved.
        :param current_depth: The current recursion depth.
        """
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
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' not in content_type:
                self.log_callback(f"⚠️ Skipping non-HTML content: {url}")
                return

            html_content = response.text
            soup = BeautifulSoup(html_content, 'html.parser')

            # Save HTML content
            relative_path = self._get_relative_path(url)
            local_path = os.path.join(path, relative_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            self.log_callback(f"✅ Saved page: {local_path}")

            # Enqueue resources for downloading
            resources = self._parse_resources(soup, url)
            for resource_url in resources:
                self.resource_queue.put((resource_url, path, url))  # Passing the page URL for rewriting links

            # Find and download linked pages recursively
            linked_pages = self._find_linked_pages(soup, url)
            for link in linked_pages:
                full_link = urljoin(url, link)
                self._download_page(full_link, path, current_depth + 1)

            # Rate limiting
            time.sleep(self.rate_limit)

        except requests.RequestException as e:
            self.log_callback(f"❌ Failed to download {url}: {e}")

    def _download_resources_worker(self):
        """
        Worker thread function to download resources from the queue.
        """
        while True:
            try:
                resource = self.resource_queue.get()
                if resource is None:
                    break  # Exit signal
                resource_url, path, page_url = resource
                self._download_resource(resource_url, path, page_url)
                self.resource_queue.task_done()
            except Exception as e:
                self.log_callback(f"❌ Error in resource downloader thread: {e}")
                self.resource_queue.task_done()

    def _download_resource(self, url, path, page_url):
        """
        Downloads a single resource and updates HTML to point to the local resource.

        :param url: The URL of the resource to download.
        :param path: The base download directory.
        :param page_url: The URL of the page where the resource is linked.
        """
        parsed_url = urlparse(url)
        if parsed_url.scheme not in ['http', 'https']:
            self.log_callback(f"⚠️ Skipping non-HTTP resource: {url}")
            return

        # Normalize the resource URL
        if not parsed_url.netloc:
            url = urljoin(self.base_urls[0], url)  # Assuming the first base URL

        # Check if resource can be fetched
        if not self._can_fetch(url):
            return

        try:
            response = self.session.get(url, timeout=self.timeout, stream=True)
            response.raise_for_status()
            relative_path = self._get_relative_path(url)
            local_path = os.path.join(path, relative_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'wb') as f:
                shutil.copyfileobj(response.raw, f)
            self.log_callback(f"✅ Downloaded resource: {local_path}")

            # Rewrite the HTML to point to the local resource
            self._rewrite_html(page_url, url, relative_path)

            with self.lock:
                self.downloaded_resources += 1
                self._update_progress()

            # Rate limiting
            time.sleep(self.rate_limit)

        except requests.RequestException as e:
            self.log_callback(f"❌ Failed to download resource {url}: {e}")

    def _rewrite_html(self, page_url, resource_url, local_relative_path):
        """
        Rewrites the HTML file to point resource URLs to local paths.

        :param page_url: The URL of the page containing the resource.
        :param resource_url: The original URL of the resource.
        :param local_relative_path: The local relative path where the resource is saved.
        """
        parsed_page_url = urlparse(page_url)
        relative_page_path = self._get_relative_path(page_url)
        local_page_path = os.path.join(self.download_path, relative_page_path)
        if not os.path.exists(local_page_path):
            return  # Page not downloaded yet

        try:
            with open(local_page_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            soup = BeautifulSoup(html_content, 'html.parser')

            # Determine the tag and attribute to modify based on resource type
            if any(resource_url.endswith(ext) for ext in ['.css']):
                tags = soup.find_all('link', href=lambda x: x and x.startswith(resource_url))
                for tag in tags:
                    tag['href'] = os.path.relpath(local_relative_path, os.path.dirname(local_page_path))
            elif any(resource_url.endswith(ext) for ext in ['.js']):
                tags = soup.find_all('script', src=lambda x: x and x.startswith(resource_url))
                for tag in tags:
                    tag['src'] = os.path.relpath(local_relative_path, os.path.dirname(local_page_path))
            elif any(resource_url.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.bmp', '.webp']):
                tags = soup.find_all('img', src=lambda x: x and x.startswith(resource_url))
                for tag in tags:
                    tag['src'] = os.path.relpath(local_relative_path, os.path.dirname(local_page_path))
            elif any(resource_url.endswith(ext) for ext in ['.woff', '.woff2', '.ttf', '.otf']):
                tags = soup.find_all('link', href=lambda x: x and x.startswith(resource_url))
                for tag in tags:
                    tag['href'] = os.path.relpath(local_relative_path, os.path.dirname(local_page_path))
            elif any(resource_url.endswith(ext) for ext in ['.mp4', '.webm', '.ogg']):
                tags = soup.find_all('video', src=lambda x: x and x.startswith(resource_url))
                for tag in tags:
                    tag['src'] = os.path.relpath(local_relative_path, os.path.dirname(local_page_path))
                # Also check <source> tags within <video>
                source_tags = soup.find_all('source', src=lambda x: x and x.startswith(resource_url))
                for tag in source_tags:
                    tag['src'] = os.path.relpath(local_relative_path, os.path.dirname(local_page_path))
            elif any(resource_url.endswith(ext) for ext in ['.pdf']):
                tags = soup.find_all('a', href=lambda x: x and x.startswith(resource_url))
                for tag in tags:
                    tag['href'] = os.path.relpath(local_relative_path, os.path.dirname(local_page_path))
            else:
                # Generic handling for other types
                tags = soup.find_all(['link', 'script', 'img', 'video', 'source', 'a'], href=lambda x: x and x.startswith(resource_url))
                for tag in tags:
                    if 'href' in tag.attrs:
                        tag['href'] = os.path.relpath(local_relative_path, os.path.dirname(local_page_path))
                    if 'src' in tag.attrs:
                        tag['src'] = os.path.relpath(local_relative_path, os.path.dirname(local_page_path))

            # Write back the modified HTML
            with open(local_page_path, 'w', encoding='utf-8') as f:
                f.write(str(soup))
            self.log_callback(f"🔄 Rewrote HTML links in {local_page_path}")
        except Exception as e:
            self.log_callback(f"❌ Failed to rewrite HTML for {page_url}: {e}")

    def _get_relative_path(self, url):
        """
        Converts a URL to a relative local file path.

        :param url: The URL to convert.
        :return: A relative file path.
        """
        parsed_url = urlparse(url)
        path = parsed_url.path
        if path.endswith('/'):
            path += 'index.html'
        elif not os.path.splitext(path)[1]:
            path += '.html'
        return path.lstrip('/')

    def _update_progress(self):
        """
        Updates the progress bar by calculating the current progress.
        """
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
        """
        Parses the HTML soup to find resource URLs based on resource types.

        :param soup: BeautifulSoup object of the HTML content.
        :param base_url: Base URL for resolving relative URLs.
        :return: A list of resource URLs.
        """
        resources = []

        # CSS files
        if 'css' in self.resource_types:
            for link in soup.find_all('link', rel='stylesheet'):
                href = link.get('href')
                if href:
                    full_url = urljoin(base_url, href)
                    resources.append(full_url)

        # JS files
        if 'js' in self.resource_types:
            for script in soup.find_all('script', src=True):
                src = script.get('src')
                if src:
                    full_url = urljoin(base_url, src)
                    resources.append(full_url)

        # Images
        if 'images' in self.resource_types:
            for img in soup.find_all('img', src=True):
                src = img.get('src')
                if src:
                    full_url = urljoin(base_url, src)
                    resources.append(full_url)

        # Fonts
        if 'fonts' in self.resource_types:
            for link in soup.find_all('link', rel=lambda x: x and 'font' in x.lower()):
                href = link.get('href')
                if href:
                    full_url = urljoin(base_url, href)
                    resources.append(full_url)

        # Videos
        if 'videos' in self.resource_types:
            for video in soup.find_all('video'):
                src = video.get('src')
                if src:
                    full_url = urljoin(base_url, src)
                    resources.append(full_url)
                for source in video.find_all('source', src=True):
                    source_src = source.get('src')
                    if source_src:
                        full_url = urljoin(base_url, source_src)
                        resources.append(full_url)

        # SVGs
        if 'svg' in self.resource_types:
            for img in soup.find_all('img', src=True):
                src = img.get('src')
                if src and src.endswith('.svg'):
                    full_url = urljoin(base_url, src)
                    resources.append(full_url)

        # Documents (e.g., PDFs)
        if 'documents' in self.resource_types:
            for a in soup.find_all('a', href=True):
                href = a.get('href')
                if href and href.endswith('.pdf'):
                    full_url = urljoin(base_url, href)
                    resources.append(full_url)

        return resources

    def _find_linked_pages(self, soup, base_url):
        """
        Finds all linked HTML pages within the same domain.

        :param soup: BeautifulSoup object of the HTML content.
        :param base_url: Base URL for resolving relative URLs.
        :return: A list of relative links to other HTML pages.
        """
        links = []
        for a in soup.find_all('a', href=True):
            href = a.get('href')
            if href.startswith('#'):
                continue  # Skip anchors
            full_url = urljoin(base_url, href)
            parsed_full_url = urlparse(full_url)
            parsed_base_url = urlparse(base_url)
            if parsed_full_url.netloc != parsed_base_url.netloc:
                continue  # Skip external links
            if any(href.endswith(ext) for ext in ['.html', '.htm', '/']):
                links.append(href)
        return links

class DownloaderThread(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished_download = pyqtSignal(bool, str)
    log = pyqtSignal(str)

    def __init__(self, urls, path, user_agent, resource_types, timeout, retries, max_depth=2, concurrency=5, proxy=None, robots_txt=True, rate_limit=0.1):
        super().__init__()
        self.urls = urls
        self.path = path
        self.user_agent = user_agent
        self.resource_types = resource_types
        self.timeout = timeout
        self.retries = retries
        self.max_depth = max_depth
        self.concurrency = concurrency
        self.proxy = proxy
        self.robots_txt = robots_txt
        self.rate_limit = rate_limit

    def run(self):
        downloader = WebDownloader(
            base_urls=self.urls,
            download_path=self.path,
            user_agent=self.user_agent,
            resource_types=self.resource_types,
            timeout=self.timeout,
            retries=self.retries,
            max_depth=self.max_depth,
            concurrency=self.concurrency,
            proxy=self.proxy,
            progress_callback=self.emit_progress,
            status_callback=self.emit_status,
            log_callback=self.emit_log,
            robots_txt=self.robots_txt,
            rate_limit=self.rate_limit
        )
        success, message = downloader.download_websites()
        self.finished_download.emit(success, message)

    def emit_progress(self, value):
        self.progress.emit(value)

    def emit_status(self, message):
        self.status.emit(message)

    def emit_log(self, message):
        self.log.emit(message)

class SidebarButton(QPushButton):
    def __init__(self, icon_path, text):
        super().__init__()
        self.setIcon(QIcon(icon_path))
        self.setText(text)
        self.setFixedHeight(50)
        self.setFont(QFont("Segoe UI", 12))
        self.setIconSize(QSize(24, 24))
        self.setStyleSheet("""
            QPushButton {
                background-color: #1e1e1e;
                color: #ffffff;
                text-align: left;
                padding-left: 20px;
                border: none;
            }
            QPushButton:hover {
                background-color: #333333;
            }
            QPushButton:pressed {
                background-color: #555555;
            }
        """)

    def set_active(self, active):
        if active:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #333333;
                    color: #1e90ff;
                    text-align: left;
                    padding-left: 20px;
                    border: none;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #1e1e1e;
                    color: #ffffff;
                    text-align: left;
                    padding-left: 20px;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #333333;
                }
                QPushButton:pressed {
                    background-color: #555555;
                }
            """)

class TitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()
        self.start = QPoint(0, 0)
        self.pressing = False

    def init_ui(self):
        self.setFixedHeight(40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # Allow horizontal expansion
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
                border-radius: 5px;
            }
            QPushButton:pressed {
                background-color: #2980b9;
                border-radius: 5px;
            }
        """)

        # Application Icon
        self.app_icon = QLabel()
        app_pixmap = QPixmap("icons/app_icon.png").scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.app_icon.setPixmap(app_pixmap)
        self.app_icon.setFixedSize(24, 24)
        self.app_icon.setToolTip("Web Downloader")

        # Title Label
        self.title = QLabel("Web Downloader")
        self.title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.title.setStyleSheet("background-color: transparent;")

        # Window Control Buttons with Icons
        self.btn_minimize = QPushButton()
        self.btn_minimize.setIcon(QIcon("icons/minimize.png"))  # Ensure you have this icon
        self.btn_minimize.setToolTip("Minimize")
        self.btn_minimize.clicked.connect(self.minimize_window)

        self.btn_maximize = QPushButton()
        self.btn_maximize.setIcon(QIcon("icons/maximize.png"))  # Ensure you have this icon
        self.btn_maximize.setToolTip("Maximize")
        self.btn_maximize.clicked.connect(self.maximize_restore_window)

        self.btn_close = QPushButton()
        self.btn_close.setIcon(QIcon("icons/close.png"))  # Ensure you have this icon
        self.btn_close.setToolTip("Close")
        self.btn_close.clicked.connect(self.close_window)

        # Layout
        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(10, 0, 10, 0)  # Horizontal margins
        h_layout.setSpacing(10)  # Spacing between widgets

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
            self.btn_maximize.setIcon(QIcon("icons/restore.png"))  # Ensure you have this icon
            self.btn_maximize.setToolTip("Restore")

    def close_window(self):
        choice = QMessageBox.question(self, 'Quit', 
            "Are you sure you want to quit?", QMessageBox.Yes | 
            QMessageBox.No, QMessageBox.No)

        if choice == QMessageBox.Yes:
            sys.exit()
        else:
            pass

    # Overriding mouse events for window dragging
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

class HomeWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        # Batch URL Input
        urls_label = QLabel("Website URLs (one per line):")
        urls_label.setFont(QFont("Segoe UI", 12))
        self.urls_input = QTextEdit()
        self.urls_input.setPlaceholderText("https://example.com\nhttps://anotherexample.com")
        self.urls_input.setFont(QFont("Segoe UI", 12))
        self.urls_input.setToolTip("Enter the URLs of the websites you want to download, one per line.")

        # Download Path
        path_label = QLabel("Download Path:")
        path_label.setFont(QFont("Segoe UI", 12))
        self.path_input = QLineEdit()
        self.path_input.setReadOnly(True)
        self.path_input.setFont(QFont("Segoe UI", 12))
        self.path_input.setToolTip("The folder where downloaded files will be saved.")
        self.browse_button = QPushButton("Browse")
        self.browse_button.setFont(QFont("Segoe UI", 12))
        self.browse_button.setFixedWidth(100)
        self.browse_button.clicked.connect(self.browse_folder)
        self.browse_button.setToolTip("Select the folder where downloaded files will be saved.")

        # Resource Types Selection
        resource_label = QLabel("Resource Types:")
        resource_label.setFont(QFont("Segoe UI", 12))
        self.css_checkbox = QCheckBox("CSS")
        self.css_checkbox.setChecked(True)
        self.js_checkbox = QCheckBox("JavaScript")
        self.js_checkbox.setChecked(True)
        self.images_checkbox = QCheckBox("Images")
        self.images_checkbox.setChecked(True)
        self.fonts_checkbox = QCheckBox("Fonts")
        self.fonts_checkbox.setChecked(False)
        self.videos_checkbox = QCheckBox("Videos")
        self.videos_checkbox.setChecked(False)
        self.svg_checkbox = QCheckBox("SVGs")
        self.svg_checkbox.setChecked(False)
        self.documents_checkbox = QCheckBox("Documents")
        self.documents_checkbox.setChecked(False)

        resource_layout = QGridLayout()
        resource_layout.addWidget(self.css_checkbox, 0, 0)
        resource_layout.addWidget(self.js_checkbox, 0, 1)
        resource_layout.addWidget(self.images_checkbox, 1, 0)
        resource_layout.addWidget(self.fonts_checkbox, 1, 1)
        resource_layout.addWidget(self.videos_checkbox, 2, 0)
        resource_layout.addWidget(self.svg_checkbox, 2, 1)
        resource_layout.addWidget(self.documents_checkbox, 3, 0)

        # Timeout Setting
        timeout_label = QLabel("Timeout (seconds):")
        timeout_label.setFont(QFont("Segoe UI", 12))
        self.timeout_spinbox = QSpinBox()
        self.timeout_spinbox.setRange(1, 120)
        self.timeout_spinbox.setValue(SettingsManager.get_setting('timeout'))
        self.timeout_spinbox.setFont(QFont("Segoe UI", 12))
        self.timeout_spinbox.setToolTip("Set the timeout duration for HTTP requests.")

        timeout_layout = QHBoxLayout()
        timeout_layout.addWidget(timeout_label)
        timeout_layout.addWidget(self.timeout_spinbox)

        # Retries Setting
        retries_label = QLabel("Retries:")
        retries_label.setFont(QFont("Segoe UI", 12))
        self.retries_spinbox = QSpinBox()
        self.retries_spinbox.setRange(0, 10)
        self.retries_spinbox.setValue(SettingsManager.get_setting('retries'))
        self.retries_spinbox.setFont(QFont("Segoe UI", 12))
        self.retries_spinbox.setToolTip("Specify the number of retry attempts for failed downloads.")

        retries_layout = QHBoxLayout()
        retries_layout.addWidget(retries_label)
        retries_layout.addWidget(self.retries_spinbox)

        # Max Depth Setting
        depth_label = QLabel("Max Depth:")
        depth_label.setFont(QFont("Segoe UI", 12))
        self.depth_spinbox = QSpinBox()
        self.depth_spinbox.setRange(1, 20)
        self.depth_spinbox.setValue(SettingsManager.get_setting('max_depth'))
        self.depth_spinbox.setFont(QFont("Segoe UI", 12))
        self.depth_spinbox.setToolTip("Set the maximum recursion depth for downloading linked pages.")

        depth_layout = QHBoxLayout()
        depth_layout.addWidget(depth_label)
        depth_layout.addWidget(self.depth_spinbox)

        # Concurrency Setting
        concurrency_label = QLabel("Concurrency:")
        concurrency_label.setFont(QFont("Segoe UI", 12))
        self.concurrency_spinbox = QSpinBox()
        self.concurrency_spinbox.setRange(1, 20)
        self.concurrency_spinbox.setValue(SettingsManager.get_setting('concurrency'))
        self.concurrency_spinbox.setFont(QFont("Segoe UI", 12))
        self.concurrency_spinbox.setToolTip("Set the number of concurrent threads for downloading resources.")

        concurrency_layout = QHBoxLayout()
        concurrency_layout.addWidget(concurrency_label)
        concurrency_layout.addWidget(self.concurrency_spinbox)

        # Proxy Settings
        proxy_label = QLabel("Proxy (optional):")
        proxy_label.setFont(QFont("Segoe UI", 12))
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("http://username:password@proxyserver:port")
        self.proxy_input.setFont(QFont("Segoe UI", 12))
        self.proxy_input.setToolTip("Enter proxy server details if required.")

        proxy_layout = QHBoxLayout()
        proxy_layout.addWidget(proxy_label)
        proxy_layout.addWidget(self.proxy_input)

        # Robots.txt Respect
        self.robots_checkbox = QCheckBox("Respect robots.txt")
        self.robots_checkbox.setChecked(SettingsManager.get_setting('robots_txt'))
        self.robots_checkbox.setFont(QFont("Segoe UI", 12))
        self.robots_checkbox.setToolTip("Enable to respect the website's robots.txt rules.")

        # Rate Limiting Setting
        rate_limit_label = QLabel("Rate Limit (seconds):")
        rate_limit_label.setFont(QFont("Segoe UI", 12))
        self.rate_limit_spinbox = QDoubleSpinBox()
        self.rate_limit_spinbox.setRange(0, 5)
        self.rate_limit_spinbox.setValue(SettingsManager.get_setting('rate_limit'))
        self.rate_limit_spinbox.setDecimals(2)  # Allows two decimal places
        self.rate_limit_spinbox.setFont(QFont("Segoe UI", 12))
        self.rate_limit_spinbox.setToolTip("Set the delay between HTTP requests to prevent server overload.")

        rate_limit_layout = QHBoxLayout()
        rate_limit_layout.addWidget(rate_limit_label)
        rate_limit_layout.addWidget(self.rate_limit_spinbox)

        # Download Button
        self.download_button = QPushButton("Download")
        self.download_button.setFont(QFont("Segoe UI", 12))
        self.download_button.setFixedHeight(40)
        self.download_button.setStyleSheet("""
            QPushButton {
                background-color: #1e90ff;
                color: white;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #63b8ff;
            }
            QPushButton:pressed {
                background-color: #4682b4;
            }
        """)
        self.download_button.clicked.connect(self.on_download)
        self.download_button.setToolTip("Start downloading the websites.")

        # Pause and Resume Buttons
        self.pause_button = QPushButton("Pause")
        self.pause_button.setFont(QFont("Segoe UI", 12))
        self.pause_button.setFixedHeight(40)
        self.pause_button.setStyleSheet("""
            QPushButton {
                background-color: #ffa500;
                color: white;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #ffb733;
            }
            QPushButton:pressed {
                background-color: #e69500;
            }
        """)
        self.pause_button.clicked.connect(self.pause_download)
        self.pause_button.setToolTip("Pause the ongoing downloads.")
        self.pause_button.setEnabled(False)

        self.resume_button = QPushButton("Resume")
        self.resume_button.setFont(QFont("Segoe UI", 12))
        self.resume_button.setFixedHeight(40)
        self.resume_button.setStyleSheet("""
            QPushButton {
                background-color: #32cd32;
                color: white;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45da45;
            }
            QPushButton:pressed {
                background-color: #28a428;
            }
        """)
        self.resume_button.clicked.connect(self.resume_download)
        self.resume_button.setToolTip("Resume the paused downloads.")
        self.resume_button.setEnabled(False)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.setFont(QFont("Segoe UI", 10))
        self.progress_bar.setFixedHeight(25)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 4px;
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
        self.progress_bar.hide()  # Initially hidden

        # Status Label
        self.status_label = QLabel("Enter URLs and select a download path.")
        self.status_label.setFont(QFont("Segoe UI", 10))
        self.status_label.setStyleSheet("color: #ffffff;")

        # Logs Card
        logs_label = QLabel("Download Logs:")
        logs_label.setFont(QFont("Segoe UI", 12))
        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        self.logs_text.setFont(QFont("Segoe UI", 10))
        self.logs_text.setStyleSheet("""
            QTextEdit {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 5px;
                color: #ffffff;
            }
        """)

        logs_layout = QVBoxLayout()
        logs_layout.addWidget(logs_label)
        logs_layout.addWidget(self.logs_text)
        logs_card = QWidget()
        logs_card.setLayout(logs_layout)
        logs_card.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                border: 1px solid #555555;
                border-radius: 8px;
            }
        """)

        # Layouts
        urls_layout = QVBoxLayout()
        urls_layout.addWidget(urls_label)
        urls_layout.addWidget(self.urls_input)

        path_layout = QHBoxLayout()
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.browse_button)

        resource_group = QGroupBox("Resource Types")
        resource_group.setFont(QFont("Segoe UI", 12))
        resource_group.setStyleSheet("""
            QGroupBox {
                color: #ffffff;
                font: 12px "Segoe UI", sans-serif;
            }
        """)
        resource_group.setLayout(resource_layout)

        settings_group = QGroupBox("Download Settings")
        settings_group.setFont(QFont("Segoe UI", 12))
        settings_group.setStyleSheet("""
            QGroupBox {
                color: #ffffff;
                font: 12px "Segoe UI", sans-serif;
            }
        """)
        settings_layout = QVBoxLayout()
        settings_layout.addLayout(timeout_layout)
        settings_layout.addLayout(retries_layout)
        settings_layout.addLayout(depth_layout)
        settings_layout.addLayout(concurrency_layout)
        settings_layout.addLayout(proxy_layout)
        settings_layout.addWidget(self.robots_checkbox)
        settings_layout.addLayout(rate_limit_layout)
        settings_group.setLayout(settings_layout)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.download_button)
        buttons_layout.addWidget(self.pause_button)
        buttons_layout.addWidget(self.resume_button)

        main_layout = QVBoxLayout()
        main_layout.addLayout(urls_layout)
        main_layout.addLayout(path_layout)
        main_layout.addWidget(resource_group)
        main_layout.addWidget(settings_group)
        main_layout.addSpacing(20)
        main_layout.addLayout(buttons_layout)
        main_layout.addWidget(self.progress_bar)
        main_layout.addSpacing(10)
        main_layout.addWidget(self.status_label)
        main_layout.addSpacing(20)
        main_layout.addWidget(logs_card)
        main_layout.addStretch()

        # Adding margins and alignment
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)

        self.setLayout(main_layout)

        # Download Control Flags
        self.is_paused = False
        self.pause_event = threading.Event()
        self.pause_event.set()  # Initially not paused

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if folder:
            self.path_input.setText(folder)
            HistoryManager.set_last_download_path(folder)

    def on_download(self):
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

        # Validate URLs
        invalid_urls = [url for url in urls if not self.is_valid_url(url)]
        if invalid_urls:
            QMessageBox.warning(self, "Input Error", f"These URLs are invalid:\n" + "\n".join(invalid_urls))
            return

        # Gather selected resource types
        resource_types = []
        if self.css_checkbox.isChecked():
            resource_types.append('css')
        if self.js_checkbox.isChecked():
            resource_types.append('js')
        if self.images_checkbox.isChecked():
            resource_types.append('images')
        if self.fonts_checkbox.isChecked():
            resource_types.append('fonts')
        if self.videos_checkbox.isChecked():
            resource_types.append('videos')
        if self.svg_checkbox.isChecked():
            resource_types.append('svg')
        if self.documents_checkbox.isChecked():
            resource_types.append('documents')

        # Get settings
        timeout = self.timeout_spinbox.value()
        retries = self.retries_spinbox.value()
        max_depth = self.depth_spinbox.value()
        concurrency = self.concurrency_spinbox.value()
        proxy_text = self.proxy_input.text().strip()
        proxy = {"http": proxy_text, "https": proxy_text} if proxy_text else None
        robots_txt = self.robots_checkbox.isChecked()
        rate_limit = self.rate_limit_spinbox.value()

        # Disable buttons during download
        self.download_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.resume_button.setEnabled(False)
        # self.clear_button_enabled(False)  # Placeholder if clear button is added

        self.progress_bar.show()
        self.progress_bar.setValue(0)
        self.logs_text.clear()

        # Initialize DownloaderThread
        self.thread = DownloaderThread(
            urls=urls,
            path=self.path_input.text().strip(),
            user_agent=SettingsManager.get_setting('user_agent'),
            resource_types=resource_types,
            timeout=timeout,
            retries=retries,
            max_depth=max_depth,
            concurrency=concurrency,
            proxy=proxy,
            robots_txt=robots_txt,
            rate_limit=rate_limit
        )
        self.thread.progress.connect(self.update_progress)
        self.thread.status.connect(self.update_status)
        self.thread.log.connect(self.update_logs)
        self.thread.finished_download.connect(self.download_finished)
        self.thread.start()

        self.update_status("⏳ Download started...")
        # Add to history
        for url in urls:
            HistoryManager.add_history(url)

    def pause_download(self):
        if hasattr(self, 'thread') and self.thread.isRunning():
            # Implementing proper pause functionality would require modifying the WebDownloader class
            # to periodically check for a pause_event. For now, we'll disable pause and enable resume.
            self.thread.terminate()  # Not recommended; proper implementation needed
            self.pause_button.setEnabled(False)
            self.resume_button.setEnabled(True)
            self.update_status("⏸️ Download paused.")
            self.log_callback("Download paused by user.")

    def resume_download(self):
        # Currently, terminating a thread does not allow resuming.
        # Implementing pause/resume would require a more sophisticated threading model.
        QMessageBox.information(self, "Info", "Resume functionality is not implemented yet.")
        self.pause_button.setEnabled(False)
        self.resume_button.setEnabled(False)

    def is_valid_url(self, url):
        parsed = urlparse(url)
        return all([parsed.scheme, parsed.netloc])

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_status(self, message):
        self.status_label.setText(message)

    def update_logs(self, message):
        self.logs_text.append(message)

    def download_finished(self, success, message):
        if success:
            QMessageBox.information(self, "Success", message)
        else:
            QMessageBox.critical(self, "Error", message)
        self.download_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.resume_button.setEnabled(False)
        self.progress_bar.hide()

    def clear_fields(self):
        self.urls_input.clear()
        self.path_input.clear()
        self.css_checkbox.setChecked(True)
        self.js_checkbox.setChecked(True)
        self.images_checkbox.setChecked(True)
        self.fonts_checkbox.setChecked(False)
        self.videos_checkbox.setChecked(False)
        self.svg_checkbox.setChecked(False)
        self.documents_checkbox.setChecked(False)
        self.timeout_spinbox.setValue(SettingsManager.get_setting('timeout'))
        self.retries_spinbox.setValue(SettingsManager.get_setting('retries'))
        self.depth_spinbox.setValue(SettingsManager.get_setting('max_depth'))
        self.concurrency_spinbox.setValue(SettingsManager.get_setting('concurrency'))
        self.proxy_input.clear()
        self.robots_checkbox.setChecked(SettingsManager.get_setting('robots_txt'))
        self.rate_limit_spinbox.setValue(SettingsManager.get_setting('rate_limit'))
        self.status_label.setText("🧹 Fields cleared.")
        self.progress_bar.hide()
        self.progress_bar.setValue(0)
        self.logs_text.clear()

    def clear_button_enabled(self, enabled):
        # Placeholder for enabling/disabling the clear button if needed
        pass

    def log_callback(self, message):
        """
        Emits log messages to the logs_text widget.
        """
        self.update_logs(message)

class HistoryWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        # Search Bar
        search_label = QLabel("Search History:")
        search_label.setFont(QFont("Segoe UI", 12))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by URL...")
        self.search_input.setFont(QFont("Segoe UI", 12))
        self.search_input.setToolTip("Enter text to filter the download history by URL.")
        self.search_input.textChanged.connect(self.filter_history)

        # History List
        self.history_list = QListWidget()
        self.load_history()
        self.history_list.setFont(QFont("Segoe UI", 12))
        self.history_list.setStyleSheet("""
            QListWidget {
                background-color: #3c3c3c;
                border: none;
                border-radius: 4px;
                padding: 5px;
                color: #ffffff;
            }
            QListWidget::item:selected {
                background-color: #1e90ff;
                color: #ffffff;
            }
        """)

        # Open Folder Button
        self.open_button = QPushButton("Open Folder")
        self.open_button.setFont(QFont("Segoe UI", 12))
        self.open_button.setFixedHeight(40)
        self.open_button.setStyleSheet("""
            QPushButton {
                background-color: #1e90ff;
                color: white;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #63b8ff;
            }
            QPushButton:pressed {
                background-color: #4682b4;
            }
        """)
        self.open_button.clicked.connect(self.open_selected)
        self.open_button.setToolTip("Open the folder where the selected website was downloaded.")

        # Clear History Button
        self.clear_button = QPushButton("Clear History")
        self.clear_button.setFont(QFont("Segoe UI", 12))
        self.clear_button.setFixedHeight(40)
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #ff4d4d;
                color: white;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #ff6666;
            }
            QPushButton:pressed {
                background-color: #e60000;
            }
        """)
        self.clear_button.clicked.connect(self.clear_history)
        self.clear_button.setToolTip("Remove all entries from the download history.")

        # Layouts
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
                        os.startfile(download_path)
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

    def init_ui(self):
        # User-Agent Setting
        user_agent_label = QLabel("User-Agent:")
        user_agent_label.setFont(QFont("Segoe UI", 12))

        self.user_agent_combobox = QComboBox()
        self.user_agent_combobox.setFont(QFont("Segoe UI", 12))
        self.user_agent_combobox.setToolTip("Select a predefined User-Agent or choose 'Custom' to enter your own.")

        # Predefined User-Agent Strings
        predefined_user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:104.0) Gecko/20100101 Firefox/104.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Mobile Safari/537.36",
            "Custom"  # Option to enter custom User-Agent
        ]

        self.user_agent_combobox.addItems(predefined_user_agents)
        self.user_agent_combobox.currentIndexChanged.connect(self.user_agent_selection_changed)

        self.custom_user_agent_input = QLineEdit()
        self.custom_user_agent_input.setFont(QFont("Segoe UI", 12))
        self.custom_user_agent_input.setPlaceholderText("Enter custom User-Agent string here...")
        self.custom_user_agent_input.setEnabled(False)
        self.custom_user_agent_input.setToolTip("Enter a custom User-Agent string.")

        # Load existing User-Agent from settings
        current_user_agent = SettingsManager.get_setting('user_agent')
        if current_user_agent in predefined_user_agents[:-1]:
            index = predefined_user_agents.index(current_user_agent)
            self.user_agent_combobox.setCurrentIndex(index)
            self.custom_user_agent_input.setEnabled(False)
        else:
            self.user_agent_combobox.setCurrentIndex(len(predefined_user_agents)-1)  # Select 'Custom'
            self.custom_user_agent_input.setEnabled(True)
            self.custom_user_agent_input.setText(current_user_agent)

        # Timeout Setting
        timeout_label = QLabel("Timeout (seconds):")
        timeout_label.setFont(QFont("Segoe UI", 12))
        self.timeout_spinbox = QSpinBox()
        self.timeout_spinbox.setRange(1, 120)
        self.timeout_spinbox.setValue(SettingsManager.get_setting('timeout'))
        self.timeout_spinbox.setFont(QFont("Segoe UI", 12))
        self.timeout_spinbox.setToolTip("Set the timeout duration for HTTP requests.")

        timeout_layout = QHBoxLayout()
        timeout_layout.addWidget(timeout_label)
        timeout_layout.addWidget(self.timeout_spinbox)

        # Retries Setting
        retries_label = QLabel("Retries:")
        retries_label.setFont(QFont("Segoe UI", 12))
        self.retries_spinbox = QSpinBox()
        self.retries_spinbox.setRange(0, 10)
        self.retries_spinbox.setValue(SettingsManager.get_setting('retries'))
        self.retries_spinbox.setFont(QFont("Segoe UI", 12))
        self.retries_spinbox.setToolTip("Specify the number of retry attempts for failed downloads.")

        retries_layout = QHBoxLayout()
        retries_layout.addWidget(retries_label)
        retries_layout.addWidget(self.retries_spinbox)

        # Max Depth Setting
        depth_label = QLabel("Max Depth:")
        depth_label.setFont(QFont("Segoe UI", 12))
        self.depth_spinbox = QSpinBox()
        self.depth_spinbox.setRange(1, 20)
        self.depth_spinbox.setValue(SettingsManager.get_setting('max_depth'))
        self.depth_spinbox.setFont(QFont("Segoe UI", 12))
        self.depth_spinbox.setToolTip("Set the maximum recursion depth for downloading linked pages.")

        depth_layout = QHBoxLayout()
        depth_layout.addWidget(depth_label)
        depth_layout.addWidget(self.depth_spinbox)

        # Concurrency Setting
        concurrency_label = QLabel("Concurrency:")
        concurrency_label.setFont(QFont("Segoe UI", 12))
        self.concurrency_spinbox = QSpinBox()
        self.concurrency_spinbox.setRange(1, 20)
        self.concurrency_spinbox.setValue(SettingsManager.get_setting('concurrency'))
        self.concurrency_spinbox.setFont(QFont("Segoe UI", 12))
        self.concurrency_spinbox.setToolTip("Set the number of concurrent threads for downloading resources.")

        concurrency_layout = QHBoxLayout()
        concurrency_layout.addWidget(concurrency_label)
        concurrency_layout.addWidget(self.concurrency_spinbox)

        # Proxy Settings
        proxy_label = QLabel("Proxy (optional):")
        proxy_label.setFont(QFont("Segoe UI", 12))
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("http://username:password@proxyserver:port")
        self.proxy_input.setFont(QFont("Segoe UI", 12))
        self.proxy_input.setToolTip("Enter proxy server details if required.")

        proxy_layout = QHBoxLayout()
        proxy_layout.addWidget(proxy_label)
        proxy_layout.addWidget(self.proxy_input)

        # Robots.txt Respect
        self.robots_checkbox = QCheckBox("Respect robots.txt")
        self.robots_checkbox.setChecked(SettingsManager.get_setting('robots_txt'))
        self.robots_checkbox.setFont(QFont("Segoe UI", 12))
        self.robots_checkbox.setToolTip("Enable to respect the website's robots.txt rules.")

        # Rate Limiting Setting
        rate_limit_label = QLabel("Rate Limit (seconds):")
        rate_limit_label.setFont(QFont("Segoe UI", 12))
        self.rate_limit_spinbox = QDoubleSpinBox()
        self.rate_limit_spinbox.setRange(0, 5)
        self.rate_limit_spinbox.setValue(SettingsManager.get_setting('rate_limit'))
        self.rate_limit_spinbox.setDecimals(2)  # Allows two decimal places
        self.rate_limit_spinbox.setFont(QFont("Segoe UI", 12))
        self.rate_limit_spinbox.setToolTip("Set the delay between HTTP requests to prevent server overload.")

        rate_limit_layout = QHBoxLayout()
        rate_limit_layout.addWidget(rate_limit_label)
        rate_limit_layout.addWidget(self.rate_limit_spinbox)

        # Default Resource Types Selection
        resource_default_label = QLabel("Default Resource Types to Download:")
        resource_default_label.setFont(QFont("Segoe UI", 12))
        self.css_default_checkbox = QCheckBox("CSS")
        self.css_default_checkbox.setChecked(SettingsManager.get_setting('default_resource_types').get('css', True))
        self.css_default_checkbox.setToolTip("Download CSS files by default.")
        self.js_default_checkbox = QCheckBox("JavaScript")
        self.js_default_checkbox.setChecked(SettingsManager.get_setting('default_resource_types').get('js', True))
        self.js_default_checkbox.setToolTip("Download JavaScript files by default.")
        self.images_default_checkbox = QCheckBox("Images")
        self.images_default_checkbox.setChecked(SettingsManager.get_setting('default_resource_types').get('images', True))
        self.images_default_checkbox.setToolTip("Download image files by default.")
        self.fonts_default_checkbox = QCheckBox("Fonts")
        self.fonts_default_checkbox.setChecked(SettingsManager.get_setting('default_resource_types').get('fonts', False))
        self.fonts_default_checkbox.setToolTip("Download font files by default.")
        self.videos_default_checkbox = QCheckBox("Videos")
        self.videos_default_checkbox.setChecked(SettingsManager.get_setting('default_resource_types').get('videos', False))
        self.videos_default_checkbox.setToolTip("Download video files by default.")
        self.svg_default_checkbox = QCheckBox("SVGs")
        self.svg_default_checkbox.setChecked(SettingsManager.get_setting('default_resource_types').get('svg', False))
        self.svg_default_checkbox.setToolTip("Download SVG files by default.")
        self.documents_default_checkbox = QCheckBox("Documents")
        self.documents_default_checkbox.setChecked(SettingsManager.get_setting('default_resource_types').get('documents', False))
        self.documents_default_checkbox.setToolTip("Download document files by default.")

        resource_default_layout = QGridLayout()
        resource_default_layout.addWidget(self.css_default_checkbox, 0, 0)
        resource_default_layout.addWidget(self.js_default_checkbox, 0, 1)
        resource_default_layout.addWidget(self.images_default_checkbox, 1, 0)
        resource_default_layout.addWidget(self.fonts_default_checkbox, 1, 1)
        resource_default_layout.addWidget(self.videos_default_checkbox, 2, 0)
        resource_default_layout.addWidget(self.svg_default_checkbox, 2, 1)
        resource_default_layout.addWidget(self.documents_default_checkbox, 3, 0)

        resource_default_group = QGroupBox("Default Resource Types")
        resource_default_group.setFont(QFont("Segoe UI", 12))
        resource_default_group.setStyleSheet("""
            QGroupBox {
                color: #ffffff;
                font: 12px "Segoe UI", sans-serif;
            }
        """)
        resource_default_group.setLayout(resource_default_layout)

        # Save Button
        self.save_button = QPushButton("Save Settings")
        self.save_button.setFont(QFont("Segoe UI", 12))
        self.save_button.setFixedHeight(40)
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #1e90ff;
                color: white;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #63b8ff;
            }
            QPushButton:pressed {
                background-color: #4682b4;
            }
        """)
        self.save_button.clicked.connect(self.save_settings)
        self.save_button.setToolTip("Save the current settings.")

        # Layout
        form_layout = QFormLayout()
        form_layout.addRow(user_agent_label, self.user_agent_combobox)
        form_layout.addRow("", self.custom_user_agent_input)
        form_layout.addRow(timeout_label, self.timeout_spinbox)
        form_layout.addRow(retries_label, self.retries_spinbox)
        form_layout.addRow(depth_label, self.depth_spinbox)
        form_layout.addRow(concurrency_label, self.concurrency_spinbox)
        form_layout.addRow(proxy_label, self.proxy_input)
        form_layout.addRow("", self.robots_checkbox)
        form_layout.addRow(rate_limit_label, self.rate_limit_spinbox)

        main_layout = QVBoxLayout()
        main_layout.addLayout(form_layout)
        main_layout.addWidget(resource_default_label)
        main_layout.addWidget(resource_default_group)
        main_layout.addSpacing(20)
        main_layout.addWidget(self.save_button)
        main_layout.addStretch()

        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)

        self.setLayout(main_layout)

    def user_agent_selection_changed(self, index):
        if self.user_agent_combobox.currentText() == "Custom":
            self.custom_user_agent_input.setEnabled(True)
        else:
            self.custom_user_agent_input.setEnabled(False)

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
        proxy = self.proxy_input.text().strip()
        proxy_dict = {"http": proxy, "https": proxy} if proxy else None
        robots_txt = self.robots_checkbox.isChecked()
        rate_limit = self.rate_limit_spinbox.value()

        # Gather default resource types
        default_resource_types = {
            'css': self.css_default_checkbox.isChecked(),
            'js': self.js_default_checkbox.isChecked(),
            'images': self.images_default_checkbox.isChecked(),
            'fonts': self.fonts_default_checkbox.isChecked(),
            'videos': self.videos_default_checkbox.isChecked(),
            'svg': self.svg_default_checkbox.isChecked(),
            'documents': self.documents_default_checkbox.isChecked()
        }

        # Update settings
        SettingsManager.set_setting('user_agent', user_agent)
        SettingsManager.set_setting('timeout', timeout)
        SettingsManager.set_setting('retries', retries)
        SettingsManager.set_setting('max_depth', max_depth)
        SettingsManager.set_setting('concurrency', concurrency)
        SettingsManager.set_setting('proxy', proxy_dict)
        SettingsManager.set_setting('robots_txt', robots_txt)
        SettingsManager.set_setting('rate_limit', rate_limit)
        SettingsManager.set_setting('default_resource_types', default_resource_types)

        QMessageBox.information(self, "Success", "✅ Settings saved successfully.")

class AboutWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        about_text = QTextEdit()
        about_text.setReadOnly(True)
        about_text.setHtml("""
            <h2>Web Downloader</h2>
            <p><strong>Version 2.0</strong></p>
            <p>Developed with Python and PyQt5.</p>
            <p>Developed by Robin Doak.</p>
            <p>This application allows you to download websites' HTML, CSS, JS, images, SVGs, videos, and documents into a single directory.</p>
            <p>Icons made by <a href="https://www.flaticon.com/authors/freepik" target="_blank">Freepik</a> from <a href="https://www.flaticon.com/" target="_blank">www.flaticon.com</a></p>
            <p>Special thanks to the open-source community for providing invaluable tools and libraries.</p>
        """)
        about_text.setFont(QFont("Segoe UI", 12))
        about_text.setStyleSheet("""
            QTextEdit {
                background-color: #3c3c3c;
                border: none;
                border-radius: 4px;
                padding: 10px;
                color: #ffffff;
            }
            a {
                color: #1e90ff;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
            }
        """)

        layout = QVBoxLayout()
        layout.addWidget(about_text)
        layout.addStretch()

        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        self.setLayout(layout)

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        # Set window flags to create a frameless window
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)  # Ensure opaque background

        # Main Layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)  # No margins
        main_layout.setSpacing(0)

        # Title Bar
        self.title_bar = TitleBar(self)
        main_layout.addWidget(self.title_bar)

        # Content Layout
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Sidebar
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(200)
        self.sidebar.setStyleSheet("background-color: #1e1e1e;")  # Darker sidebar

        self.sidebar_layout = QVBoxLayout()
        self.sidebar_layout.setContentsMargins(0, 0, 0, 0)  # No margins
        self.sidebar_layout.setSpacing(0)

        # Application Logo
        self.logo = QLabel()
        logo_pixmap = QPixmap("icons/app_icon.png").scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.logo.setPixmap(logo_pixmap)
        self.logo.setAlignment(Qt.AlignCenter)
        self.logo.setStyleSheet("padding: 20px;")
        self.sidebar_layout.addWidget(self.logo)

        # Sidebar Buttons
        self.btn_home = SidebarButton("icons/home.png", "Home")
        self.btn_history = SidebarButton("icons/history.png", "History")
        self.btn_settings = SidebarButton("icons/settings.png", "Settings")
        self.btn_about = SidebarButton("icons/about.png", "About")
        self.btn_quit = SidebarButton("icons/quit.png", "Quit")

        # Connect Buttons
        self.btn_home.clicked.connect(lambda: self.switch_page(0))
        self.btn_history.clicked.connect(lambda: self.switch_page(1))
        self.btn_settings.clicked.connect(lambda: self.switch_page(2))
        self.btn_about.clicked.connect(lambda: self.switch_page(3))
        self.btn_quit.clicked.connect(self.close_application)

        # Add buttons to sidebar
        self.sidebar_layout.addWidget(self.btn_home)
        self.sidebar_layout.addWidget(self.btn_history)
        self.sidebar_layout.addWidget(self.btn_settings)
        self.sidebar_layout.addWidget(self.btn_about)
        self.sidebar_layout.addStretch()
        self.sidebar_layout.addWidget(self.btn_quit)

        self.sidebar.setLayout(self.sidebar_layout)

        # Main Content Area
        self.stack = QStackedWidget()
        self.home = HomeWidget()
        self.history = HistoryWidget()
        self.settings = SettingsWidget()
        self.about = AboutWidget()

        self.stack.addWidget(self.home)
        self.stack.addWidget(self.history)
        self.stack.addWidget(self.settings)
        self.stack.addWidget(self.about)

        # Add sidebar and stack to content layout
        content_layout.addWidget(self.sidebar)
        content_layout.addWidget(self.stack)

        # Add content layout to main layout
        main_layout.addLayout(content_layout)

        self.setLayout(main_layout)

        # Set initial active button
        self.active_button = self.btn_home
        self.btn_home.set_active(True)

        self.setWindowTitle("Web Downloader")
        self.setWindowIcon(QIcon("icons/app_icon.png"))
        self.resize(1200, 800)  # Allows window resizing

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)
        self.highlight_button(index)
        self.fade_in()

    def highlight_button(self, index):
        buttons = [self.btn_home, self.btn_history, self.btn_settings, self.btn_about]
        for i, button in enumerate(buttons):
            if i == index:
                button.set_active(True)
                self.active_button = button
            else:
                button.set_active(False)

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
        else:
            pass

class SettingsManager:
    settings = {
        "user_agent": "WebDownloader/2.0",
        "timeout": 10,
        "retries": 3,
        "max_depth": 2,
        "concurrency": 5,
        "proxy": None,
        "robots_txt": True,
        "rate_limit": 0.1,
        "default_resource_types": {
            "css": True,
            "js": True,
            "images": True,
            "fonts": False,
            "videos": False,
            "svg": False,
            "documents": False
        }
    }

    @classmethod
    def load_settings(cls):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    cls.settings = json.load(f)
                # Ensure types
                cls.settings['timeout'] = int(cls.settings.get('timeout', 10))
                cls.settings['retries'] = int(cls.settings.get('retries', 3))
                cls.settings['max_depth'] = int(cls.settings.get('max_depth', 2))
                cls.settings['concurrency'] = int(cls.settings.get('concurrency', 5))
                cls.settings['user_agent'] = str(cls.settings.get('user_agent', "WebDownloader/2.0"))
                cls.settings['proxy'] = cls.settings.get('proxy', None)
                cls.settings['robots_txt'] = bool(cls.settings.get('robots_txt', True))
                cls.settings['rate_limit'] = float(cls.settings.get('rate_limit', 0.1))
                # Ensure resource types are booleans
                default_resources = cls.settings.get('default_resource_types', {})
                for key in ['css', 'js', 'images', 'fonts', 'videos', 'svg', 'documents']:
                    default_resources[key] = bool(default_resources.get(key, False))
                cls.settings['default_resource_types'] = default_resources
                print("Settings loaded successfully.")
            except (json.JSONDecodeError, IOError, ValueError) as e:
                print(f"Error loading settings: {e}")
                cls.settings = {
                    "user_agent": "WebDownloader/2.0",
                    "timeout": 10,
                    "retries": 3,
                    "max_depth": 2,
                    "concurrency": 5,
                    "proxy": None,
                    "robots_txt": True,
                    "rate_limit": 0.1,
                    "default_resource_types": {
                        "css": True,
                        "js": True,
                        "images": True,
                        "fonts": False,
                        "videos": False,
                        "svg": False,
                        "documents": False
                    }
                }
                cls.save_settings()
        else:
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
        return cls.settings.get(key, "")

    @classmethod
    def set_setting(cls, key, value):
        cls.settings[key] = value
        cls.save_settings()

class HistoryManager:
    history = []  # List of URLs
    download_paths = {}  # Mapping from URL to download path
    last_download_path = ""

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
    def add_history(cls, url):
        if url not in cls.history:
            cls.history.append(url)
            # Assuming the last download path is used
            if cls.last_download_path:
                cls.download_paths[url] = cls.last_download_path
            cls.save_history()
            print(f"Added to history: {url}")
        else:
            print(f"URL already in history: {url}")

    @classmethod
    def get_history(cls):
        return cls.history[::-1]  # Return in reverse chronological order

    @classmethod
    def get_download_path(cls, url):
        return cls.download_paths.get(url, "")

    @classmethod
    def set_last_download_path(cls, path):
        cls.last_download_path = path
        print(f"Set last download path to: {path}")

    @classmethod
    def clear_history(cls):
        cls.history = []
        cls.download_paths = {}
        cls.save_history()
        print("History cleared.")

class MainApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.load_resources()
        self.window = MainWindow()
        self.window.show()

    def load_resources(self):
        # Load settings and history
        SettingsManager.load_settings()
        HistoryManager.load_history()

    def run(self):
        sys.exit(self.app.exec_())

def apply_stylesheet(app):
    # Load stylesheet from file
    stylesheet_path = os.path.join(os.path.dirname(__file__), 'styles', 'style.qss')
    if os.path.exists(stylesheet_path):
        with open(stylesheet_path, 'r') as f:
            app.setStyleSheet(f.read())
    else:
        # Fallback to default styles if stylesheet file is missing
        app.setStyleSheet("""
        /* Default Dark Theme */
        QWidget {
            background-color: #2b2b2b;
            color: #ffffff;
            font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
            font-size: 14px;
        }
        """)

def main():
    # Ensure history is loaded before the application starts
    HistoryManager.load_history()
    # Ensure settings are loaded before the application starts
    SettingsManager.load_settings()
    app = QApplication(sys.argv)
    apply_stylesheet(app)
    main_app = MainApp()
    main_app.run()

if __name__ == "__main__":
    main()
