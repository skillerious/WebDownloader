from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QLabel, QLineEdit, QPushButton, QMessageBox
from PyQt5.QtGui import QFont
import sys, os
from managers import HistoryManager

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
