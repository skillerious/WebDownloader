import os
import re
import time
import requests
import threading
from urllib.parse import urljoin, urlparse, urldefrag, urlunparse
from bs4 import BeautifulSoup

# Optional JavaScript support with Playwright
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

class ImageRipper:
    def __init__(self, 
                 url, 
                 download_path, 
                 log_callback=None, 
                 progress_callback=None, 
                 use_playwright=False, 
                 remove_query_strings=False,
                 max_retries=3,
                 timeout=10):
        """
        :param url: The URL of the page to rip images from.
        :param download_path: The local directory to save images.
        :param log_callback: A function to call with log messages (optional).
        :param progress_callback: A function to call with progress updates (optional).
        :param use_playwright: If True and playwright is available, render the page with JS.
        :param remove_query_strings: If True, remove query parameters from image URLs before download.
        :param max_retries: Number of retries for network requests.
        :param timeout: Timeout in seconds for requests.
        """
        self.url = url
        self.download_path = download_path
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.stop_event = threading.Event()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})
        self.use_playwright = use_playwright and PLAYWRIGHT_AVAILABLE
        self.remove_query_strings = remove_query_strings
        self.max_retries = max_retries
        self.timeout = timeout

    def log(self, message):
        if self.log_callback:
            self.log_callback(message)

    def update_progress(self, value):
        if self.progress_callback:
            self.progress_callback(value)

    def stop(self):
        self.stop_event.set()

    def fetch_page(self, url):
        for attempt in range(self.max_retries):
            if self.stop_event.is_set():
                break
            try:
                resp = self.session.get(url, timeout=self.timeout)
                resp.raise_for_status()
                return resp
            except requests.RequestException as e:
                self.log(f"⚠️ Fetch error for {url}: {e}, retrying...")
                time.sleep(1)
        self.log(f"❌ Failed to fetch {url} after {self.max_retries} attempts.")
        return None

    def get_rendered_html(self):
        if not self.use_playwright:
            resp = self.fetch_page(self.url)
            if resp:
                return resp.text
            return ""
        
        self.log("🧭 Using Playwright to render page with JavaScript...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            page.goto(self.url, timeout=self.timeout * 1000)
            page.wait_for_load_state("networkidle")

            # Optionally scroll to load more images
            for _ in range(3):
                if self.stop_event.is_set():
                    break
                page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                page.wait_for_timeout(1000)  # wait for lazy loading

            content = page.content()
            browser.close()
            return content

    def download_images(self):
        # Validate URL
        parsed_url = urlparse(self.url)
        if not parsed_url.scheme.startswith('http'):
            self.log("❌ Invalid URL provided.")
            return

        if not os.path.exists(self.download_path):
            os.makedirs(self.download_path)

        self.log(f"🌐 Fetching {self.url}")
        html = self.get_rendered_html()
        if not html:
            self.log("❌ No HTML content retrieved.")
            return

        soup = BeautifulSoup(html, 'html.parser')

        images = set()
        images.update(self.get_img_tags(soup))
        images.update(self.get_lazy_load_images(soup))
        images.update(self.get_srcset_images(soup))
        images.update(self.get_picture_source_images(soup))
        images.update(self.get_inline_style_images(soup))
        images.update(self.get_css_images(soup))
        images.update(self.get_meta_images(soup))
        images.update(self.get_script_heuristic_images(soup))
        images.update(self.get_data_bg_images(soup))
        images.update(self.get_attr_url_images(soup))  # heuristic for any attr with 'url('

        # Filter known non-image formats (fonts, css, etc.)
        images = self.filter_non_images_by_extension(images)

        # Filter data URIs
        images = {img for img in images if not img.lower().startswith('data:')}

        images = list(set(images))
        total_images = len(images)
        self.log(f"🔍 Found {total_images} images.")

        if total_images == 0:
            return

        downloaded = 0
        for i, img_url in enumerate(images, start=1):
            if self.stop_event.is_set():
                self.log("🛑 Stopped by user.")
                break

            img_url = self.clean_image_url(img_url)
            self.log(f"⬇️ Downloading {img_url}")

            if self.download_image(img_url, i):
                downloaded += 1

            progress = int((i / total_images) * 100)
            self.update_progress(progress)

        self.log(f"🎉 Downloaded {downloaded} out of {total_images} images.")

    def clean_image_url(self, img_url):
        # Remove fragment
        img_url, frag = urldefrag(img_url)
        if self.remove_query_strings:
            parsed = urlparse(img_url)
            img_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
        return img_url

    def get_img_tags(self, soup):
        images = set()
        for img in soup.find_all('img', src=True):
            full_url = urljoin(self.url, img['src'])
            images.add(full_url)
        return images

    def get_lazy_load_images(self, soup):
        images = set()
        # Extended list of lazy attributes
        lazy_attributes = [
            'data-src', 'data-lazy', 'data-original', 'data-image', 
            'data-srcset', 'data-flickity-lazyload', 'data-lazy-src'
        ]
        for img in soup.find_all('img'):
            for attr in lazy_attributes:
                if img.has_attr(attr):
                    val = img[attr]
                    if val:
                        if ' ' in val and not val.startswith('http'):
                            images.update(self.parse_srcset_values(val, self.url))
                        else:
                            full_url = urljoin(self.url, val)
                            images.add(full_url)
        return images

    def get_srcset_images(self, soup):
        images = set()
        for tag in soup.find_all(['img', 'source'], srcset=True):
            srcset_val = tag['srcset']
            images.update(self.parse_srcset_values(srcset_val, self.url))
        return images

    def parse_srcset_values(self, srcset_val, base_url):
        images = set()
        candidates = srcset_val.split(',')
        for candidate in candidates:
            candidate = candidate.strip()
            url_part = candidate.split()[0] if ' ' in candidate else candidate
            full_url = urljoin(base_url, url_part)
            images.add(full_url)
        return images

    def get_picture_source_images(self, soup):
        images = set()
        for source in soup.find_all('source', src=True):
            full_url = urljoin(self.url, source['src'])
            images.add(full_url)
        return images

    def get_inline_style_images(self, soup):
        images = set()
        style_url_pattern = re.compile(r'url\((.*?)\)', re.IGNORECASE)
        for tag in soup.find_all(style=True):
            style_val = tag['style']
            matches = style_url_pattern.findall(style_val)
            for m in matches:
                img_url = m.strip('"').strip("'")
                full_url = urljoin(self.url, img_url)
                images.add(full_url)
        return images

    def get_css_images(self, soup):
        images = set()
        style_url_pattern = re.compile(r'url\((.*?)\)', re.IGNORECASE)
        # External CSS
        for link in soup.find_all('link', rel='stylesheet'):
            href = link.get('href')
            if href:
                css_url = urljoin(self.url, href)
                self.log(f"📝 Parsing CSS: {css_url}")
                css_resp = self.fetch_page(css_url)
                if css_resp:
                    css_content = css_resp.text
                    matches = style_url_pattern.findall(css_content)
                    for m in matches:
                        m = m.strip('"').strip("'")
                        if not m.lower().startswith('data:'):
                            full_url = urljoin(css_url, m)
                            images.add(full_url)

        # Inline <style> tags
        for style in soup.find_all('style'):
            css_content = style.string or ""
            matches = style_url_pattern.findall(css_content)
            for m in matches:
                m = m.strip('"').strip("'")
                if not m.lower().startswith('data:'):
                    full_url = urljoin(self.url, m)
                    images.add(full_url)
        return images

    def get_meta_images(self, soup):
        images = set()
        meta_props = ['og:image', 'twitter:image', 'og:image:url', 'og:image:secure_url']
        for meta in soup.find_all('meta'):
            prop = meta.get('property') or meta.get('name')
            if prop and prop.lower() in meta_props:
                content = meta.get('content')
                if content:
                    full_url = urljoin(self.url, content)
                    images.add(full_url)
        return images

    def get_script_heuristic_images(self, soup):
        images = set()
        # Include webp and svg in regex
        img_pattern = re.compile(r'(https?://[^\s"\'<]+(?:\.(?:jpg|jpeg|png|gif|webp|svg)))', re.IGNORECASE)
        for script in soup.find_all('script'):
            script_content = script.string or ""
            matches = img_pattern.findall(script_content)
            for m in matches:
                images.add(m)
        return images

    def get_data_bg_images(self, soup):
        """
        Some tags store images in data-bg, data-background, etc.
        """
        images = set()
        bg_attributes = ['data-bg', 'data-background', 'data-bg-url']
        for tag in soup.find_all():
            for attr in bg_attributes:
                if tag.has_attr(attr):
                    val = tag[attr]
                    if val:
                        full_url = urljoin(self.url, val)
                        images.add(full_url)
        return images

    def get_attr_url_images(self, soup):
        """
        Heuristic: look through all attributes of all tags; if an attribute contains `url(...)`,
        parse and extract images. This might catch unusual cases.
        """
        images = set()
        url_pattern = re.compile(r'url\((.*?)\)', re.IGNORECASE)
        for tag in soup.find_all():
            for attr, val in tag.attrs.items():
                if isinstance(val, str) and 'url(' in val.lower():
                    matches = url_pattern.findall(val)
                    for m in matches:
                        img_url = m.strip('"').strip("'")
                        full_url = urljoin(self.url, img_url)
                        images.add(full_url)
        return images

    def filter_non_images_by_extension(self, images):
        """
        Filter out URLs that clearly aren't images by extension
        (e.g., fonts, CSS, JS, etc.)
        """
        non_image_ext = ['.css', '.js', '.json', '.pdf', '.eot', '.woff', '.woff2', '.ttf', '.otf', '.map', '.txt']
        filtered = set()
        for img in images:
            parsed = urlparse(img)
            ext = os.path.splitext(parsed.path)[1].lower()
            if ext in non_image_ext:
                continue
            filtered.add(img)
        return filtered

    def download_image(self, img_url, count):
        if self.stop_event.is_set():
            return False
        content = self.fetch_resource(img_url)
        if not content:
            # Could not fetch after retries
            return False

        # Check MIME type
        ctype = content.headers.get('Content-Type', '').lower()
        if not ctype.startswith('image/'):
            self.log(f"⚠️ Skipping non-image resource: {img_url} [{ctype}]")
            return False

        filename = self.get_filename(img_url, ctype, count)
        local_path = os.path.join(self.download_path, filename)

        try:
            with open(local_path, 'wb') as f:
                for chunk in content.iter_content(chunk_size=8192):
                    f.write(chunk)
            self.log(f"✅ Saved: {local_path}")
            return True
        except Exception as e:
            self.log(f"❌ Error saving {img_url}: {e}")
            return False

    def fetch_resource(self, url):
        for attempt in range(self.max_retries):
            if self.stop_event.is_set():
                return None
            try:
                resp = self.session.get(url, stream=True, timeout=self.timeout)
                resp.raise_for_status()
                return resp
            except requests.RequestException as e:
                self.log(f"⚠️ Fetch error for {url}: {e}, retry {attempt+1}/{self.max_retries}")
                time.sleep(1)
        self.log(f"❌ Failed to download {url} after {self.max_retries} attempts.")
        return None

    def get_filename(self, img_url, content_type, count):
        parsed = urlparse(img_url)
        filename = os.path.basename(parsed.path)
        if not filename or '.' not in filename:
            # Guess extension from content type if not present
            ext = self.guess_extension(content_type)
            filename = f"image_{count}{ext}"
        return filename

    def guess_extension(self, content_type):
        if 'jpeg' in content_type:
            return '.jpg'
        elif 'png' in content_type:
            return '.png'
        elif 'gif' in content_type:
            return '.gif'
        elif 'webp' in content_type:
            return '.webp'
        elif 'svg' in content_type:
            return '.svg'
        return '.bin'  # fallback for unknown image type
