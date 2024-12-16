from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame, QStackedWidget, 
                             QMessageBox, QLabel, QPushButton, QGraphicsOpacityEffect, QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QSize
from PyQt5.QtGui import QIcon, QFont, QPixmap, QColor, QBrush
import sys

from ui.home import HomeWidget
from ui.history import HistoryWidget
from ui.settings import SettingsWidget
from ui.about import AboutWidget

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


class TitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()
        self.start = QPoint(0, 0)
        self.pressing = False

    def init_ui(self):
        self.setFixedHeight(40)
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
        self._add_drop_shadow(self.btn_minimize)

        self.btn_maximize = QPushButton()
        self.btn_maximize.setIcon(QIcon("icons/maximize.png"))
        self.btn_maximize.setToolTip("Maximize")
        self.btn_maximize.clicked.connect(self.maximize_restore_window)
        self._add_drop_shadow(self.btn_maximize)

        self.btn_close = QPushButton()
        self.btn_close.setIcon(QIcon("icons/close.png"))
        self.btn_close.setToolTip("Close")
        self.btn_close.clicked.connect(self.close_window)
        self._add_drop_shadow(self.btn_close)

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

    def _add_drop_shadow(self, button):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 160))
        button.setGraphicsEffect(shadow)

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

        # Add a separator line below the title bar
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("QFrame {background-color: #444444; border: none; height: 1px;}")
        main_layout.addWidget(separator)

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
