from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QFormLayout, QLabel, QComboBox,
                             QLineEdit, QCheckBox, QSpinBox, QDoubleSpinBox, QPushButton, QTextEdit,
                             QTableWidget, QTableWidgetItem, QGroupBox, QGridLayout, QTimeEdit, QFileDialog, QMessageBox)
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtCore import Qt, QTime
from managers import SettingsManager

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
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ...",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ...",
            "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 ...",
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

        # NEW fields for crawl limits and query removal:
        self.max_pages_spinbox = QSpinBox()
        self.max_pages_spinbox.setRange(0, 100000)  # 0 = no limit
        self.max_pages_spinbox.setToolTip("Max number of pages to crawl (0 = no limit)")

        self.max_resources_spinbox = QSpinBox()
        self.max_resources_spinbox.setRange(0, 100000) # 0 = no limit
        self.max_resources_spinbox.setToolTip("Max number of resources to download (0 = no limit)")

        self.max_images_spinbox = QSpinBox()
        self.max_images_spinbox.setRange(0, 100000)
        self.max_images_spinbox.setToolTip("Max number of images to download (0 = no limit)")

        self.remove_query_strings_checkbox = QCheckBox("Remove Query Strings from URLs")

        form.addRow(QLabel("Timeout (s):"), self.timeout_spinbox)
        form.addRow(QLabel("Retries:"), self.retries_spinbox)
        form.addRow(QLabel("Max Depth:"), self.depth_spinbox)
        form.addRow(QLabel("Concurrency:"), self.concurrency_spinbox)
        form.addRow(QLabel("Max File Size (MB):"), self.max_file_size_spinbox)
        form.addRow(QLabel("Download Structure:"), self.download_structure_combobox)
        form.addRow("", self.download_after_crawl_checkbox)

        # Add the new fields:
        form.addRow(QLabel("Max Pages:"), self.max_pages_spinbox)  # NEW
        form.addRow(QLabel("Max Resources:"), self.max_resources_spinbox)  # NEW
        form.addRow(QLabel("Max Images:"), self.max_images_spinbox)  # NEW
        form.addRow("", self.remove_query_strings_checkbox)  # NEW

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

        # NEW fields for auth_token and token_refresh_endpoint
        self.auth_token_input = QLineEdit()
        self.auth_token_input.setPlaceholderText("Bearer token...")

        self.token_refresh_endpoint_input = QLineEdit()
        self.token_refresh_endpoint_input.setPlaceholderText("URL for token refresh")

        form.addRow(QLabel("Proxy:"), self.proxy_address_input)
        form.addRow("", self.proxy_auth_checkbox)
        form.addRow(QLabel("Proxy Username:"), self.proxy_username_input)
        form.addRow(QLabel("Proxy Password:"), self.proxy_password_input)
        form.addRow("", self.robots_checkbox)
        form.addRow("", self.ignore_https_checkbox)
        form.addRow(QLabel("Rate Limit (s):"), self.rate_limit_spinbox)
        form.addRow("", self.include_subdomains_checkbox)

        # Add authentication token fields
        form.addRow(QLabel("Auth Token:"), self.auth_token_input) # NEW
        form.addRow(QLabel("Token Refresh Endpoint:"), self.token_refresh_endpoint_input) # NEW

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
        user_agent = SettingsManager.get_setting('user_agent')
        predefined_user_agents = [self.user_agent_combobox.itemText(i) for i in range(self.user_agent_combobox.count())]
        if user_agent in predefined_user_agents[:-1]:
            self.user_agent_combobox.setCurrentIndex(predefined_user_agents.index(user_agent))
            self.custom_user_agent_input.setEnabled(False)
        else:
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
                from urllib.parse import urlparse
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

        default_resources = SettingsManager.get_setting('default_resource_types')
        self.html_checkbox.setChecked(default_resources.get('html', True))
        self.css_checkbox.setChecked(default_resources.get('css', True))
        self.js_checkbox.setChecked(default_resources.get('js', True))
        self.images_checkbox.setChecked(default_resources.get('images', True))
        self.fonts_checkbox.setChecked(default_resources.get('fonts', False))
        self.videos_checkbox.setChecked(default_resources.get('videos', False))
        self.svg_checkbox.setChecked(default_resources.get('svg', False))
        self.documents_checkbox.setChecked(default_resources.get('documents', False))

        # NEW: Load new settings
        self.max_pages_spinbox.setValue(SettingsManager.get_setting('max_pages'))
        self.max_resources_spinbox.setValue(SettingsManager.get_setting('max_resources'))
        self.max_images_spinbox.setValue(SettingsManager.get_setting('max_images'))
        self.remove_query_strings_checkbox.setChecked(SettingsManager.get_setting('remove_query_strings'))

        self.auth_token_input.setText(SettingsManager.get_setting('auth_token'))
        self.token_refresh_endpoint_input.setText(SettingsManager.get_setting('token_refresh_endpoint'))

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

        # NEW: Get new settings
        max_pages = self.max_pages_spinbox.value()
        max_resources = self.max_resources_spinbox.value()
        max_images = self.max_images_spinbox.value()
        remove_query_strings = self.remove_query_strings_checkbox.isChecked()

        auth_token = self.auth_token_input.text().strip()
        token_refresh_endpoint = self.token_refresh_endpoint_input.text().strip()

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

        # NEW: Save new settings
        SettingsManager.set_setting('max_pages', max_pages)
        SettingsManager.set_setting('max_resources', max_resources)
        SettingsManager.set_setting('max_images', max_images)
        SettingsManager.set_setting('remove_query_strings', remove_query_strings)
        SettingsManager.set_setting('auth_token', auth_token)
        SettingsManager.set_setting('token_refresh_endpoint', token_refresh_endpoint)

        QMessageBox.information(self, "Success", "✅ Settings saved successfully.")

    def reset_to_default(self):
        confirm = QMessageBox.question(self, "Reset to Default",
                                       "Are you sure you want to reset all settings to default?",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm == QMessageBox.Yes:
            SettingsManager.reset_to_defaults()
            self.load_current_settings()
            QMessageBox.information(self, "Success", "✅ Settings have been reset to default.")
