import asyncio
import aiohttp
import os
import json
import re
import shutil
from urllib.parse import urljoin, urlparse, urlunparse
from bs4 import BeautifulSoup
from PyQt5.QtCore import QThread, pyqtSignal
from managers import SettingsManager
import time

class DiskCache:
    def __init__(self, cache_dir="cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _safe_filename(self, url):
        # Replace illegal filename characters on Windows and other OS
        # Common invalid chars: < > : " / \ | ? *
        # We'll just replace them with '_'
        return re.sub(r'[<>:"/\\|?*]', '_', url)

    def _metadata_path(self, url):
        safe_url = self._safe_filename(url)
        return os.path.join(self.cache_dir, safe_url + ".json")

    def _data_path(self, url):
        safe_url = self._safe_filename(url)
        return os.path.join(self.cache_dir, safe_url + ".dat")

    def get_metadata(self, url):
        p = self._metadata_path(url)
        if os.path.exists(p):
            with open(p, 'r') as f:
                return json.load(f)
        return {}

    def save(self, url, content, headers):
        p_data = self._data_path(url)
        p_meta = self._metadata_path(url)
        with open(p_data, 'wb') as f:
            f.write(content)
        meta = {
            'ETag': headers.get('ETag'),
            'Last-Modified': headers.get('Last-Modified'),
            'Content-Type': headers.get('Content-Type'),
        }
        with open(p_meta, 'w') as f:
            json.dump(meta, f, indent=2)

    def load(self, url):
        p_data = self._data_path(url)
        if os.path.exists(p_data):
            with open(p_data, 'rb') as f:
                return f.read()
        return None


class AsyncWebDownloader:
    def __init__(self, base_urls, download_path, user_agent, resource_types, timeout, retries,
                 max_depth, concurrency, proxy, exclusions, robots_txt, rate_limit,
                 ignore_https_errors, max_file_size, download_structure, follow_external_links,
                 custom_headers, basic_auth_user, basic_auth_pass, ignore_mime_types,
                 stop_event,
                 log_callback, status_callback, progress_callback, page_callback, resource_callback):

        self.base_urls = base_urls
        self.download_path = download_path
        self.user_agent = user_agent
        self.resource_types = resource_types
        self.timeout = timeout
        self.retries = retries
        self.max_depth = max_depth
        self.concurrency = concurrency
        self.proxy = proxy
        self.exclusions = set(exclusions) if exclusions else set()
        self.robots_txt = robots_txt
        self.rate_limit = rate_limit
        self.ignore_https_errors = ignore_https_errors
        self.max_file_size = max_file_size * 1024 * 1024
        self.download_structure = download_structure
        self.follow_external_links = follow_external_links
        self.custom_headers = custom_headers
        self.basic_auth_user = basic_auth_user
        self.basic_auth_pass = basic_auth_pass
        self.ignore_mime_types = ignore_mime_types if ignore_mime_types else []
        self.stop_event = stop_event

        self.log_callback = log_callback
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.page_downloaded_callback = page_callback
        self.resource_downloaded_callback = resource_callback

        self.seen_pages = set()
        self.to_visit = asyncio.Queue()
        for url in self.base_urls:
            self.to_visit.put_nowait((url, 0))

        self.cache = DiskCache("cache")
        self.css_cache = {}

        self.seen_resources = set()
        self.failed = set()
        self.total_resources = 0
        self.downloaded_resources = 0
        self.resource_queue = asyncio.Queue()
        self.had_failures = False

    def emit_log(self, msg):
        if self.log_callback:
            self.log_callback(msg)

    def emit_status(self, msg):
        if self.status_callback:
            self.status_callback(msg)

    def emit_progress(self):
        if self.total_resources == 0:
            p = 100
        else:
            p = int((self.downloaded_resources / self.total_resources) * 100)
            if p > 100:
                p = 100
        if self.progress_callback:
            self.progress_callback(p)

    def emit_page_downloaded(self, url, status, path):
        if self.page_downloaded_callback:
            self.page_downloaded_callback(url, status, path)

    def emit_resource_downloaded(self, url, status, path):
        if self.resource_downloaded_callback:
            self.resource_downloaded_callback(url, status, path)

    def is_valid_resource_url(self, url):
        parsed = urlparse(url)
        if parsed.scheme not in ['http', 'https']:
            return False
        if not parsed.netloc:
            return False
        valid_extensions = ['.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.woff', '.woff2', '.ttf', '.eot', '.pdf', '.docx', '.xlsx', '.pptx', '.mp4', '.webm', '.ogg']
        return any(parsed.path.lower().endswith(ext) for ext in valid_extensions)

    def clean_url(self, url):
        parsed = urlparse(url)
        clean_parsed = parsed._replace(fragment='', query='')
        return urlunparse(clean_parsed)

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

    async def fetch(self, session, url, is_resource=False):
        if self.stop_event and self.stop_event.is_set():
            return None, ''
        meta = self.cache.get_metadata(url)
        headers = {}
        if meta.get('ETag'):
            headers['If-None-Match'] = meta['ETag']
        if meta.get('Last-Modified'):
            headers['If-Modified-Since'] = meta['Last-Modified']

        for h in self.custom_headers:
            if h.get('key') and h.get('value'):
                headers[h['key']] = h['value']

        auth = None
        if self.basic_auth_user and self.basic_auth_pass:
            auth = aiohttp.BasicAuth(self.basic_auth_user, self.basic_auth_pass)

        for attempt in range(self.retries):
            try:
                async with session.get(url, headers=headers, auth=auth, timeout=self.timeout) as resp:
                    if resp.status == 304:
                        cached_data = self.cache.load(url)
                        if cached_data:
                            return cached_data, meta.get('Content-Type', '')
                        else:
                            resp.raise_for_status()
                    resp.raise_for_status()
                    data = await resp.read()
                    if self.max_file_size > 0:
                        content_length = resp.headers.get('Content-Length')
                        if content_length and int(content_length) > self.max_file_size:
                            self.emit_log(f"❌ Resource too large, skipping: {url}")
                            return None, ''
                    self.cache.save(url, data, resp.headers)
                    return data, resp.headers.get('Content-Type','')
            except Exception as e:
                wait_time = 2 ** (attempt+1)
                self.emit_log(f"⚠️ Retry {attempt+1}/{self.retries} for {url} after {wait_time} seconds. Error: {e}")
                await asyncio.sleep(wait_time)

        self.failed.add(url)
        self.had_failures = True
        self.emit_log(f"❌ Failed to download resource {url}: Failed after {self.retries} attempts.")
        return None, ''

    def parse_css(self, base_url, css_content):
        if base_url in self.css_cache:
            return self.css_cache[base_url]

        resources = []
        text = css_content.decode('utf-8', 'ignore')
        import_statements = re.findall(r'@import\s+(?:url\()?["\']?(.*?)["\']?\)?;', text)
        for imp in import_statements:
            full_url = urljoin(base_url, imp)
            c = self.clean_url(full_url)
            if self.is_valid_resource_url(c):
                resources.append(c)

        url_references = re.findall(r'url\(["\']?(.*?)["\']?\)', text)
        for ref in url_references:
            if not ref.startswith('data:'):
                full_url = urljoin(base_url, ref)
                c = self.clean_url(full_url)
                if self.is_valid_resource_url(c):
                    resources.append(c)

        self.css_cache[base_url] = resources
        return resources

    def parse_html(self, content, base_url):
        soup = BeautifulSoup(content, 'html.parser')
        resources = set()
        linked_pages = []

        rt = self.resource_types
        if rt.get('css', False):
            for link in soup.find_all('link', rel='stylesheet'):
                href = link.get('href')
                if href:
                    full_url = urljoin(base_url, href)
                    c = self.clean_url(full_url)
                    if self.is_valid_resource_url(c):
                        resources.add(c)

        if rt.get('js', False):
            for script in soup.find_all('script', src=True):
                src = script.get('src')
                if src:
                    full_url = urljoin(base_url, src)
                    c = self.clean_url(full_url)
                    if self.is_valid_resource_url(c):
                        resources.add(c)

        if rt.get('images', False):
            for img in soup.find_all('img', src=True):
                src = img.get('src')
                if src:
                    full_url = urljoin(base_url, src)
                    c = self.clean_url(full_url)
                    if self.is_valid_resource_url(c):
                        resources.add(c)

        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith('#'):
                continue
            full_url = urljoin(base_url, href)
            if not self.follow_external_links:
                if urlparse(full_url).netloc != urlparse(base_url).netloc:
                    continue
            linked_pages.append(full_url)

        return resources, linked_pages

    async def worker_pages(self, session):
        while not self.to_visit.empty():
            if self.stop_event and self.stop_event.is_set():
                break
            url, depth = await self.to_visit.get()
            if depth > self.max_depth:
                self.to_visit.task_done()
                continue
            if url in self.seen_pages:
                self.to_visit.task_done()
                continue
            self.seen_pages.add(url)

            data, ctype = await self.fetch(session, url, is_resource=False)
            if not data:
                self.to_visit.task_done()
                continue

            relative_path = self._get_relative_path(url)
            local_path = os.path.join(self.download_path, relative_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'wb') as f:
                f.write(data)
            self.emit_log(f"✅ Saved page: {local_path}")
            self.emit_page_downloaded(url, "✅ Page Downloaded", local_path)

            resources, linked_pages = self.parse_html(data, url)
            for lp in linked_pages:
                await self.to_visit.put((lp, depth+1))
            for r in resources:
                if r not in self.seen_resources and r not in self.failed:
                    self.seen_resources.add(r)
                    self.total_resources += 1
                    await self.resource_queue.put(r)
            self.emit_progress()

            self.to_visit.task_done()
            await asyncio.sleep(self.rate_limit)

    async def worker_resources(self, session):
        while True:
            if self.stop_event and self.stop_event.is_set():
                break
            url = await self.resource_queue.get()
            if url in self.failed:
                self.resource_queue.task_done()
                continue
            data, ctype = await self.fetch(session, url, is_resource=True)
            if not data:
                self.resource_queue.task_done()
                continue

            if 'text/css' in ctype:
                css_res = self.parse_css(url, data)
                for c in css_res:
                    if c not in self.seen_resources and c not in self.failed:
                        self.seen_resources.add(c)
                        self.total_resources += 1
                        await self.resource_queue.put(c)

            relative_path = self._get_relative_path(url)
            local_path = os.path.join(self.download_path, relative_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            with open(local_path, 'wb') as f:
                f.write(data)

            self.emit_log(f"✅ Downloaded resource: {local_path}")
            self.emit_resource_downloaded(url, "✅ Resource Downloaded", local_path)
            self.downloaded_resources += 1
            self.emit_progress()

            self.resource_queue.task_done()
            await asyncio.sleep(self.rate_limit)

    async def run_crawler(self):
        connector = aiohttp.TCPConnector(ssl=not self.ignore_https_errors)
        async with aiohttp.ClientSession(connector=connector) as session:
            page_workers = max(1, self.concurrency // 2)
            resource_workers = max(1, self.concurrency - page_workers)

            tasks = []
            for _ in range(page_workers):
                tasks.append(asyncio.create_task(self.worker_pages(session)))
            for _ in range(resource_workers):
                tasks.append(asyncio.create_task(self.worker_resources(session)))

            await self.to_visit.join()
            await self.resource_queue.join()

            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        if self.had_failures:
            self.emit_log("⚠️ Download completed with some errors.")
            return False, "Download completed, but some resources failed."
        else:
            self.emit_log("✅ Download completed successfully.")
            return True, "✅ Download completed successfully."


class DownloaderThread(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished_download = pyqtSignal(bool, str)
    log = pyqtSignal(str)
    resource_downloaded = pyqtSignal(str, str, str)
    page_downloaded = pyqtSignal(str, str, str)

    def __init__(self, urls, path, user_agent, resource_types, timeout, retries,
                 max_depth=2, concurrency=5, proxy=None, exclusions=None,
                 robots_txt=True, rate_limit=0.1, ignore_https_errors=False,
                 max_file_size=0, download_structure="keep", follow_external_links=False,
                 custom_headers=None, basic_auth_user="", basic_auth_pass="", ignore_mime_types=None,
                 stop_event=None):
        super().__init__()
        self.urls = urls
        self.path = path

        # Set a realistic user-agent if not already set
        if not user_agent or "Mozilla" not in user_agent:
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"

        self.user_agent = user_agent
        self.resource_types = resource_types
        self.timeout = timeout
        self.retries = retries
        self.max_depth = max_depth
        self.concurrency = concurrency
        self.proxy = proxy
        self.exclusions = exclusions
        self.robots_txt = robots_txt
        self.rate_limit = rate_limit
        self.ignore_https_errors = ignore_https_errors
        self.max_file_size = max_file_size
        self.download_structure = download_structure
        self.follow_external_links = follow_external_links

        # Ensure custom_headers is a list
        if custom_headers is None:
            custom_headers = []

        # Add a referrer header if not present
        ref_present = any(h.get('key','').lower() == 'referer' for h in custom_headers)
        if not ref_present:
            custom_headers.append({"key": "Referer", "value": "https://preview.themeforest.net/"})

        # Add user-agent header if not present or override
        ua_present = any(h.get('key','').lower() == 'user-agent' for h in custom_headers)
        if not ua_present:
            custom_headers.append({"key": "User-Agent", "value": self.user_agent})

        self.custom_headers = custom_headers
        self.basic_auth_user = basic_auth_user
        self.basic_auth_pass = basic_auth_pass
        self.ignore_mime_types = ignore_mime_types
        self.stop_event = stop_event

    def run(self):
        async def run_downloader():
            downloader = AsyncWebDownloader(
                base_urls=self.urls,
                download_path=self.path,
                user_agent=self.user_agent,
                resource_types=self.resource_types,
                timeout=self.timeout,
                retries=self.retries,
                max_depth=self.max_depth,
                concurrency=self.concurrency,
                proxy=self.proxy,
                exclusions=self.exclusions,
                robots_txt=self.robots_txt,
                rate_limit=self.rate_limit,
                ignore_https_errors=self.ignore_https_errors,
                max_file_size=self.max_file_size,
                download_structure=self.download_structure,
                follow_external_links=self.follow_external_links,
                custom_headers=self.custom_headers,
                basic_auth_user=self.basic_auth_user,
                basic_auth_pass=self.basic_auth_pass,
                ignore_mime_types=self.ignore_mime_types,
                stop_event=self.stop_event,
                log_callback=self.on_log,
                status_callback=self.on_status,
                progress_callback=self.on_progress,
                page_callback=self.on_page_downloaded,
                resource_callback=self.on_resource_downloaded
            )
            return await downloader.run_crawler()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success, message = loop.run_until_complete(run_downloader())
        loop.close()
        self.finished_download.emit(success, message)

    def on_progress(self, p):
        self.progress.emit(p)

    def on_status(self, msg):
        self.status.emit(msg)

    def on_log(self, msg):
        self.log.emit(msg)

    def on_resource_downloaded(self, url, status, path):
        self.resource_downloaded.emit(url, status, path)

    def on_page_downloaded(self, url, status, path):
        self.page_downloaded.emit(url, status, path)

    def pause(self):
        self.on_log("⏸️ Pause not implemented in async version.")

    def resume(self):
        self.on_log("▶️ Resume not implemented in async version.")
