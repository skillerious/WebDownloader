from PyQt5.QtWidgets import (QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout,
                             QHBoxLayout, QFileDialog, QProgressBar, QMessageBox,
                             QTextEdit, QTableWidget, QTableWidgetItem, QCheckBox)
from PyQt5.QtCore import Qt, QTime, QTimer
from PyQt5.QtGui import QFont, QColor, QBrush
import time, os
from managers import SettingsManager, HistoryManager
from downloader import DownloaderThread
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False

class HomeWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.downloader_thread = None
        self.stop_event = threading.Event() if 'threading' in globals() else None
        self.schedule_timer = None
        self.preview_button = None
        self.open_folder_button = None
        self.init_ui()

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
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 12px;
                text-align: center;
                background-color: #3c3c3c;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1e90ff, stop:1 #63b8ff
                );
                width: 20px;
                border-radius: 12px;
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

        self.start_download(urls)

    def start_download(self, urls):
        default_resources = SettingsManager.get_setting('default_resource_types')

        resource_types = default_resources

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
        if self.stop_event:
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
            if self.stop_event:
                self.stop_event.set()
            self.update_status("🛑 Stopping download...")

    def clear_logs(self):
        self.logs_text.clear()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_status(self, message):
        self.status_label.setText(message)

    def update_logs(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.logs_text.append(f"[{timestamp}] {message}")
        self.logs_text.verticalScrollBar().setValue(self.logs_text.verticalScrollBar().maximum())

    def update_resource_table(self, url, status, path):
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

        # Add "Open Download Folder" button
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
        from PyQt5.QtCore import QUrl
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
