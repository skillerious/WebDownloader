import json
import os

SETTINGS_FILE = "settings.json"
HISTORY_FILE = "history.json"

class SettingsManager:
    default_settings = {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "timeout": 10,
        "retries": 3,
        "default_resource_types": {
            "html": True,
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
        "proxy": None,  # can be {"http": "...", "https": "..."}
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
        "include_subdomains": True, # NEW
        "follow_external_links": False,
        "custom_headers": [],
        "basic_auth_user": "",
        "basic_auth_pass": "",
        "schedule_download": False,
        "schedule_time": "00:00",
        "ignore_mime_types": [],
        # NEW settings:
        "auth_token": "",
        "token_refresh_endpoint": "",
        "remove_query_strings": False,
        "max_pages": 0,
        "max_resources": 0,
        "max_images": 0
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
            except:
                cls.settings = cls.default_settings.copy()
                cls.save_settings()
        else:
            cls.settings = cls.default_settings.copy()
            cls.save_settings()

    @classmethod
    def save_settings(cls):
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(cls.settings, f, indent=4)

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
            except:
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
        with open(HISTORY_FILE, 'w') as f:
            json.dump(data, f, indent=4)

    @classmethod
    def add_history(cls, url, path):
        if url not in cls.history:
            cls.history.append(url)
            cls.download_paths[url] = path
            cls.save_history()

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
