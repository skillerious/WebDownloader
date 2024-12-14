from PyQt5.QtWidgets import QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog, QProgressBar, QTextEdit, QMessageBox
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
import os
import time
from image_ripper import ImageRipper

class ImageRipperThread(QThread):
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, url, path):
        super().__init__()
        self.url = url
        self.path = path
        self.ripper = ImageRipper(url=self.url, download_path=self.path, 
                                  log_callback=self.emit_log,
                                  progress_callback=self.emit_progress)

    def run(self):
        self.ripper.download_images()
        self.finished.emit()

    def emit_log(self, message):
        self.log.emit(message)

    def emit_progress(self, value):
        self.progress.emit(value)

    def stop(self):
        self.ripper.stop()


class ImageRipperWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.thread = None

    def init_ui(self):
        url_label = QLabel("Website URL:")
        url_label.setFont(QFont("Segoe UI", 12))
        self.url_input = QLineEdit()
        self.url_input.setFont(QFont("Segoe UI", 12))
        self.url_input.setPlaceholderText("https://example.com")

        path_label = QLabel("Download Path:")
        path_label.setFont(QFont("Segoe UI", 12))
        self.path_input = QLineEdit()
        self.path_input.setFont(QFont("Segoe UI", 12))
        self.path_input.setReadOnly(True)
        browse_button = QPushButton("Browse")
        browse_button.setFont(QFont("Segoe UI", 12))
        browse_button.setFixedWidth(100)
        browse_button.clicked.connect(self.browse_folder)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(path_label)
        buttons_layout.addWidget(self.path_input)
        buttons_layout.addWidget(browse_button)

        self.download_button = QPushButton("Download Images")
        self.download_button.setFont(QFont("Segoe UI", 12))
        self.download_button.setFixedHeight(40)
        self.download_button.setStyleSheet("""
            QPushButton {
                background-color: #1e90ff;
                color: white;
            }
            QPushButton:hover {
                background-color: #63b8ff;
            }
        """)
        self.download_button.clicked.connect(self.start_download)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setFont(QFont("Segoe UI", 12))
        self.stop_button.setFixedHeight(40)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #ff4d4d;
                color: white;
            }
            QPushButton:hover {
                background-color: #ff6666;
            }
        """)
        self.stop_button.clicked.connect(self.stop_download)
        self.stop_button.setEnabled(False)

        control_layout = QHBoxLayout()
        control_layout.addWidget(self.download_button)
        control_layout.addWidget(self.stop_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFont(QFont("Segoe UI", 10))
        self.progress_bar.setFixedHeight(25)
        self.progress_bar.hide()

        logs_label = QLabel("Logs:")
        logs_label.setFont(QFont("Segoe UI", 12))

        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        self.logs_text.setFont(QFont("Segoe UI", 10))
        self.logs_text.setStyleSheet("""
            QTextEdit {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                color: #ffffff;
            }
        """)

        layout = QVBoxLayout()
        layout.addWidget(url_label)
        layout.addWidget(self.url_input)
        layout.addLayout(buttons_layout)
        layout.addSpacing(20)
        layout.addLayout(control_layout)
        layout.addWidget(self.progress_bar)
        layout.addSpacing(10)
        layout.addWidget(logs_label)
        layout.addWidget(self.logs_text)
        layout.addStretch()

        self.setLayout(layout)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if folder:
            self.path_input.setText(folder)

    def start_download(self):
        url = self.url_input.text().strip()
        path = self.path_input.text().strip()

        if not url:
            QMessageBox.warning(self, "Input Error", "Please enter a URL.")
            return
        if not path:
            QMessageBox.warning(self, "Input Error", "Please select a download path.")
            return

        self.download_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.logs_text.clear()

        self.thread = ImageRipperThread(url, path)
        self.thread.log.connect(self.update_logs)
        self.thread.progress.connect(self.update_progress)
        self.thread.finished.connect(self.download_finished)
        self.thread.start()

    def stop_download(self):
        if self.thread and self.thread.isRunning():
            self.thread.stop()
            self.update_logs("🛑 Stop requested.")

    def update_logs(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.logs_text.append(f"[{timestamp}] {message}")
        self.logs_text.verticalScrollBar().setValue(self.logs_text.verticalScrollBar().maximum())

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def download_finished(self):
        QMessageBox.information(self, "Done", "Image download completed.")
        self.download_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.hide()
