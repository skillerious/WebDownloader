import sys
import os
import requests
import shutil
import re
import json
import time
import threading
from urllib.parse import urljoin, urlparse, urlunparse, urldefrag
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from PyQt5.QtCore import QThread, pyqtSignal
from managers import SettingsManager
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False

from playwright.sync_api import sync_playwright

CACHE_FILE = "cache.json"

class WebDownloader:
    def __init__(self, base_urls, download_path, user_agent, resource_types, timeout, retries,
                 max_depth=2, concurrency=5, proxy=None, exclusions=None,
                 progress_callback=None, status_callback=None, log_callback=None,
                 resource_downloaded_callback=None, robots_txt=True, rate_limit=0.1,
                 ignore_https_errors=False, max_file_size=0, download_structure="keep",
                 follow_external_links=False, custom_headers=None, basic_auth_user="",
                 basic_auth_pass="", ignore_mime_types=None, stop_event=None,
                 # NEW parameters:
                 include_subdomains=True,
                 remove_query_strings=False,
                 max_pages=0,
                 max_resources=0,
                 max_images=0,
                 auth_token="",
                 token_refresh_endpoint=""):

        self.base_urls = base_urls
        self.download_path = download_path
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': user_agent})

        if proxy:
            if isinstance(proxy, dict):
                self.session.proxies.update(proxy)

        if basic_auth_user and basic_auth_pass:
            self.session.auth = (basic_auth_user, basic_auth_pass)

        if custom_headers:
            for hdr in custom_headers:
                if hdr.get("key") and hdr.get("value"):
                    self.session.headers[hdr["key"]] = hdr["value"]

        if auth_token:
            self.session.headers["Authorization"] = f"Bearer {auth_token}"

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
        self.failed_downloads = set()
        self.ignore_https_errors = ignore_https_errors
        self.max_file_size = max_file_size * 1024 * 1024
        self.download_structure = download_structure
        self.follow_external_links = follow_external_links
        self.ignore_mime_types = ignore_mime_types if ignore_mime_types else []
        self.stop_event = stop_event
        self.download_cache_file = CACHE_FILE

        # NEW:
        self.include_subdomains = include_subdomains
        self.remove_query_strings = remove_query_strings
        self.max_pages = max_pages
        self.max_resources = max_resources
        self.max_images = max_images
        self.auth_token = auth_token
        self.token_refresh_endpoint = token_refresh_endpoint

        self.pages_crawled = 0
        self.images_downloaded = 0

        self.load_cache()
        self.executor = ThreadPoolExecutor(max_workers=self.concurrency)
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.resource_queue = []

    def refresh_token_if_needed(self):
        # Placeholder if you need token refresh logic
        pass

    def should_stop_crawl(self):
        if self.stop_event and self.stop_event.is_set():
            return True
        if self.max_pages and self.pages_crawled >= self.max_pages:
            return True
        return False

    def should_stop_downloading_resources(self):
        if self.max_resources and self.downloaded_resources >= self.max_resources:
            return True
        if self.max_images and self.images_downloaded >= self.max_images:
            return True
        return False

    def load_cache(self):
        if os.path.exists(self.download_cache_file):
            try:
                with open(self.download_cache_file, 'r') as f:
                    data = json.load(f)
                    self.download_cache = set(data.get('downloaded', []))
                    self.failed_downloads = set(data.get('failed', []))
                if self.log_callback:
                    self.log_callback("✅ Download cache loaded.")
            except (json.JSONDecodeError, IOError) as e:
                if self.log_callback:
                    self.log_callback(f"❌ Failed to load download cache: {e}")
                self.download_cache = set()
                self.failed_downloads = set()
        else:
            self.download_cache = set()
            self.failed_downloads = set()

    def save_cache(self):
        data = {
            'downloaded': list(self.download_cache),
            'failed': list(self.failed_downloads)
        }
        try:
            with open(self.download_cache_file, 'w') as f:
                json.dump(data, f, indent=4)
            if self.log_callback:
                self.log_callback("✅ Download cache saved.")
        except IOError as e:
            if self.log_callback:
                self.log_callback(f"❌ Failed to save download cache: {e}")

    def pause(self):
        self.pause_event.clear()
        if self.log_callback:
            self.log_callback("⏸️ Download paused.")

    def resume(self):
        self.pause_event.set()
        if self.log_callback:
            self.log_callback("▶️ Download resumed.")

    def _can_fetch(self, url):
        if self.stop_event and self.stop_event.is_set():
            return False
        for exclusion in self.exclusions:
            if exclusion in url:
                if self.log_callback:
                    self.log_callback(f"🚫 Excluded by user settings: {url}")
                return False

        base_domain = urlparse(self.base_urls[0]).netloc
        target_domain = urlparse(url).netloc
        if not self.follow_external_links and target_domain != base_domain:
            return False
        if not self.include_subdomains:
            if target_domain != base_domain:
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
                if self.log_callback:
                    self.log_callback(f"🚫 Disallowed by robots.txt: {url}")
            else:
                if self.log_callback:
                    self.log_callback(f"✅ Allowed by robots.txt: {url}")
            return can_fetch
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"⚠️ Could not fetch robots.txt for {url}: {e}")
            return True

    def download_websites(self):
        try:
            if not os.path.exists(self.download_path):
                os.makedirs(self.download_path)

            # Count resources first
            for base_url in self.base_urls:
                if self.should_stop_crawl():
                    break
                if self.status_callback:
                    self.status_callback(f"🕵️‍♂️ Starting resource counting for {base_url}")
                self._count_total_resources(base_url, current_depth=0)

            if self.status_callback:
                self.status_callback("📦 Resource counting completed.")
                self.status_callback("🔄 Starting download...")

            # Download all pages
            for base_url in self.base_urls:
                if self.should_stop_crawl():
                    break
                self._download_page_with_playwright(base_url, self.download_path, current_depth=0)

            # Download resources
            unique_resources = set(self.resource_queue)
            for resource in unique_resources:
                if self.should_stop_downloading_resources() or self.should_stop_crawl():
                    break
                self.executor.submit(self._download_resource, *resource)

            self.executor.shutdown(wait=True)

            # Final rewriting after all downloads complete:
            self._final_rewrite_all_html()

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

    def _final_rewrite_all_html(self):
        if self.log_callback:
            self.log_callback("🔧 Running final HTML rewriting...")
        for root, dirs, files in os.walk(self.download_path):
            for file in files:
                if file.lower().endswith('.html'):
                    html_file_path = os.path.join(root, file)
                    try:
                        with open(html_file_path, 'r', encoding='utf-8') as f:
                            soup = BeautifulSoup(f.read(), 'html.parser')

                        self._rewrite_html_links(soup, html_file_path)

                        with open(html_file_path, 'w', encoding='utf-8') as f:
                            f.write(str(soup))
                        if self.log_callback:
                            self.log_callback(f"🔄 Final rewrite done for {html_file_path}")
                    except Exception as e:
                        if self.log_callback:
                            self.log_callback(f"❌ Error rewriting {html_file_path}: {e}")

    def _rewrite_html_links(self, soup, html_file_path):
        tags_attrs = [
            ('link', 'href'),
            ('script', 'src'),
            ('img', 'src'),
            ('video', 'src'),
            ('source', 'src'),
            ('a', 'href')
        ]

        for tag_name, attr in tags_attrs:
            for tag in soup.find_all(tag_name, {attr: True}):
                old_value = tag.get(attr)
                if not old_value:
                    continue
                parsed = urlparse(old_value)
                if parsed.scheme in ['http', 'https']:
                    local_path = self._get_relative_path(old_value)
                    local_abs = os.path.join(self.download_path, local_path)
                    if os.path.exists(local_abs):
                        rel_path = os.path.relpath(local_abs, os.path.dirname(html_file_path))
                        rel_path = rel_path.replace('\\', '/')
                        tag[attr] = rel_path

    def _count_total_resources(self, url, current_depth):
        if self.should_stop_crawl():
            return
        if current_depth > self.max_depth:
            return
        parsed_url = urlparse(url)
        if parsed_url.scheme not in ['http', 'https']:
            if self.log_callback:
                self.log_callback(f"⚠️ Skipping non-HTTP URL: {url}")
            return
        if url in self.counted_urls:
            if self.log_callback:
                self.log_callback(f"ℹ️ Already counted: {url}")
            return
        if not self._can_fetch(url):
            return
        self.counted_urls.add(url)
        try:
            if self.stop_event and self.stop_event.is_set():
                return
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
            if self.log_callback:
                self.log_callback(f"📝 Found {len(resources)} resources on {url}")

            linked_pages = self._find_linked_pages(soup, url)
            for link in linked_pages:
                if self.should_stop_crawl():
                    break
                full_link = urljoin(url, link)
                self._count_total_resources(full_link, current_depth + 1)

            time.sleep(self.rate_limit)

        except Exception as e:
            if self.log_callback:
                self.log_callback(f"❌ Failed to access {url}: {e}")

    def _download_page_with_playwright(self, url, path, current_depth):
        if self.should_stop_crawl():
            return
        if current_depth > self.max_depth:
            return
        parsed_url = urlparse(url)
        if parsed_url.scheme not in ['http', 'https']:
            if self.log_callback:
                self.log_callback(f"⚠️ Skipping non-HTTP URL: {url}")
            return
        if url in self.visited_urls:
            if self.log_callback:
                self.log_callback(f"ℹ️ Already downloaded: {url}")
            return
        if not self._can_fetch(url):
            return
        self.visited_urls.add(url)
        self.pages_crawled += 1
        try:
            if self.stop_event and self.stop_event.is_set():
                return
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(user_agent=self.session.headers['User-Agent'])
                page = context.new_page()
                page.goto(url, timeout=self.timeout * 1000)
                content = page.content()
                browser.close()

            relative_path = self._get_relative_path(url)
            local_path = os.path.join(path, relative_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(content)
            if self.log_callback:
                self.log_callback(f"✅ Saved page: {local_path}")

            soup = BeautifulSoup(content, 'html.parser')
            resources = self._parse_resources(soup, url)
            for resource_url in resources:
                if self.should_stop_downloading_resources():
                    break
                if resource_url not in self.download_cache:
                    self.resource_queue.append((resource_url, path, url))

            linked_pages = self._find_linked_pages(soup, url)
            for link in linked_pages:
                if self.should_stop_crawl():
                    break
                full_link = urljoin(url, link)
                self._download_page_with_playwright(full_link, path, current_depth + 1)

            time.sleep(self.rate_limit)

        except Exception as e:
            if self.log_callback:
                self.log_callback(f"❌ Failed to download {url} with Playwright: {e}")

    def _parse_css_resources(self, css_url):
        resources = []
        try:
            response = self.session.get(css_url, timeout=self.timeout)
            response.raise_for_status()
            css_content = response.text
            import_statements = re.findall(r'@import\s+(?:url\()?["\']?(.*?)["\']?\)?;', css_content)
            for imp in import_statements:
                full_url = urljoin(css_url, imp)
                if self.is_valid_resource_url(full_url):
                    resources.append(full_url)

            url_references = re.findall(r'url\(["\']?(.*?)["\']?\)', css_content)
            for ref in url_references:
                if not ref.startswith('data:'):
                    full_url = urljoin(css_url, ref)
                    if self.is_valid_resource_url(full_url):
                        resources.append(full_url)

        except requests.RequestException as e:
            if self.log_callback:
                self.log_callback(f"❌ Failed to parse CSS {css_url}: {e}")

        return resources

    def _find_linked_pages(self, soup, base_url):
        links = []
        base_parsed = urlparse(base_url)
        for a in soup.find_all('a', href=True):
            if self.should_stop_crawl():
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
        if parsed.scheme not in ['http', 'https']:
            return False
        if not parsed.netloc:
            return False
        valid_extensions = ['.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.woff', '.woff2', '.ttf', '.eot', '.pdf', '.docx', '.xlsx', '.pptx', '.mp4', '.webm', '.ogg']
        if not any(parsed.path.lower().endswith(ext) for ext in valid_extensions):
            return False
        return True

    def _download_resource(self, url, path, page_url):
        if self.stop_event and self.stop_event.is_set():
            return
        if self.should_stop_downloading_resources():
            return
        if url in self.download_cache:
            if self.log_callback:
                self.log_callback(f"ℹ️ Resource already downloaded: {url}")
            if self.resource_downloaded_callback:
                self.resource_downloaded_callback.emit(url, "ℹ️ Already Downloaded", self._get_relative_path(url))
            return
        if url in self.failed_downloads:
            if self.log_callback:
                self.log_callback(f"🚫 Resource previously failed: {url}")
            return
        if not self._can_fetch(url):
            return
        try:
            self.pause_event.wait()
            if self.stop_event and self.stop_event.is_set():
                return
            attempt = 0
            success = False
            response = None
            while attempt < self.retries:
                try:
                    head_resp = self.session.head(url, timeout=self.timeout)
                    if head_resp.status_code == 404:
                        if self.log_callback:
                            self.log_callback(f"🚫 Resource not found (404): {url}")
                        break
                    mime_type = head_resp.headers.get('Content-Type', '')
                    if any(m in mime_type for m in self.ignore_mime_types):
                        if self.log_callback:
                            self.log_callback(f"🚫 Skipping {url} due to ignored MIME type {mime_type}")
                        return
                    response = self.session.get(url, timeout=self.timeout, stream=True)
                    response.raise_for_status()
                    if self.max_file_size > 0:
                        content_length = response.headers.get('Content-Length')
                        if content_length and int(content_length) > self.max_file_size:
                            if self.log_callback:
                                self.log_callback(f"❌ Resource too large, skipping: {url}")
                            if self.resource_downloaded_callback:
                                self.resource_downloaded_callback.emit(url, "❌ Too Large", "")
                            return
                    success = True
                    break
                except requests.RequestException as e:
                    attempt += 1
                    wait_time = 2 ** attempt
                    if self.log_callback:
                        self.log_callback(f"⚠️ Retry {attempt}/{self.retries} for {url} after {wait_time} seconds.")
                    time.sleep(wait_time)

            if not success:
                raise requests.RequestException(f"Failed to download after {self.retries} attempts.")

            relative_path = self._get_relative_path(url)
            local_path = os.path.join(path, relative_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'wb') as f:
                shutil.copyfileobj(response.raw, f)
            if self.log_callback:
                self.log_callback(f"✅ Downloaded resource: {local_path}")

            if 'image/' in response.headers.get('Content-Type', ''):
                self.images_downloaded += 1

            self.download_cache.add(url)
            self.save_cache()

            if self.resource_downloaded_callback:
                self.resource_downloaded_callback.emit(url, "✅ Downloaded", local_path)

            with self.lock:
                self.downloaded_resources += 1
                self._update_progress()

            time.sleep(self.rate_limit)

        except requests.RequestException as e:
            if self.log_callback:
                self.log_callback(f"❌ Failed to download resource {url}: {e}")
            if self.resource_downloaded_callback:
                self.resource_downloaded_callback.emit(url, f"❌ Failed: {e}", "")
            self.failed_downloads.add(url)
            self.save_cache()

    def _get_relative_path(self, url):
        parsed_url = urlparse(url)
        path = parsed_url.path
        if path.endswith('/'):
            path += 'index.html'
        elif not os.path.splitext(path)[1]:
            path += '/index.html'

        if self.download_structure == "flatten":
            filename = os.path.basename(path)
            if not filename:
                filename = "index.html"
            return os.path.join(parsed_url.netloc, filename).replace('\\', '/')
        else:
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
        resources = set()
        if self.stop_event and self.stop_event.is_set():
            if self.log_callback:
                self.log_callback("⏹️ Stopping resource parsing as stop event is set.")
            return resources
        rt = self.resource_types
        if self.log_callback:
            self.log_callback(f"📄 Parsing resources for {base_url} with resource types: {rt}")

        # CSS
        if rt.get('css', False):
            for link in soup.find_all('link', rel='stylesheet'):
                href = link.get('href')
                if href:
                    full_url = urljoin(base_url, href)
                    clean_url = self.clean_url(full_url)
                    if self.is_valid_resource_url(clean_url):
                        resources.add(clean_url)
                        css_resources = self._parse_css_resources(clean_url)
                        resources.update(css_resources)

        # JS
        if rt.get('js', False):
            for script in soup.find_all('script', src=True):
                src = script.get('src')
                if src:
                    full_url = urljoin(base_url, src)
                    clean_url = self.clean_url(full_url)
                    if self.is_valid_resource_url(clean_url):
                        resources.add(clean_url)

        # Images
        if rt.get('images', False):
            for img in soup.find_all('img', src=True):
                src = img.get('src')
                if src:
                    full_url = urljoin(base_url, src)
                    clean_url = self.clean_url(full_url)
                    if self.is_valid_resource_url(clean_url):
                        resources.add(clean_url)

        # Fonts
        if rt.get('fonts', False):
            for link in soup.find_all('link', href=True):
                href = link.get('href')
                if href and any(href.lower().endswith(ext) for ext in ['.woff', '.woff2', '.ttf', '.eot']):
                    full_url = urljoin(base_url, href)
                    clean_url = self.clean_url(full_url)
                    if self.is_valid_resource_url(clean_url):
                        resources.add(clean_url)

        # Videos
        if rt.get('videos', False):
            for video in soup.find_all('video'):
                src = video.get('src')
                if src:
                    full_url = urljoin(base_url, src)
                    clean_url = self.clean_url(full_url)
                    if self.is_valid_resource_url(clean_url):
                        resources.add(clean_url)
                for source in video.find_all('source', src=True):
                    ssrc = source.get('src')
                    if ssrc:
                        full_url = urljoin(base_url, ssrc)
                        clean_url = self.clean_url(full_url)
                        if self.is_valid_resource_url(clean_url):
                            resources.add(clean_url)

        # SVG
        if rt.get('svg', False):
            for img in soup.find_all('img', src=True):
                src = img.get('src')
                if src and src.lower().endswith('.svg'):
                    full_url = urljoin(base_url, src)
                    clean_url = self.clean_url(full_url)
                    if self.is_valid_resource_url(clean_url):
                        resources.add(clean_url)

        # Documents
        if rt.get('documents', False):
            for a in soup.find_all('a', href=True):
                href = a.get('href')
                if href and any(href.lower().endswith(ext) for ext in ['.pdf', '.docx', '.xlsx', '.pptx']):
                    full_url = urljoin(base_url, href)
                    clean_url = self.clean_url(full_url)
                    if self.is_valid_resource_url(clean_url):
                        resources.add(clean_url)

        if self.log_callback:
            self.log_callback(f"🔍 Total unique resources found on {base_url}: {len(resources)}")
            for res in resources:
                self.log_callback(f"🔗 Resource detected: {res}")
        return resources

    def clean_url(self, url):
        parsed = urlparse(url)
        clean_parsed = parsed._replace(fragment='', query='')
        clean_url = urlunparse(clean_parsed)
        return clean_url


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
                 stop_event=None,
                 # NEW:
                 include_subdomains=True,
                 remove_query_strings=False,
                 max_pages=0,
                 max_resources=0,
                 max_images=0,
                 auth_token="",
                 token_refresh_endpoint=""
                 ):
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
            stop_event=stop_event,
            include_subdomains=include_subdomains,
            remove_query_strings=remove_query_strings,
            max_pages=max_pages,
            max_resources=max_resources,
            max_images=max_images,
            auth_token=auth_token,
            token_refresh_endpoint=token_refresh_endpoint
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
