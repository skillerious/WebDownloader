import sys
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
                             QApplication)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap

class AboutWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        # Main layout for the about page
        # The margins and spacing provide padding around the edges and between elements
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(20)

        # Title area (icon + title)
        title_layout = QHBoxLayout()
        title_layout.setSpacing(10)

        icon_label = QLabel()
        # app_icon.png should have a transparent background already
        icon_pixmap = QPixmap("icons/app_icon.png").scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        icon_label.setPixmap(icon_pixmap)
        # Make the icon label background transparent
        icon_label.setStyleSheet("background-color: rgba(0,0,0,0);")

        title_label = QLabel("About Web Downloader")
        # Make the text transparent background and possibly the text slightly transparent if desired
        title_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0,0,0,0);
                color: rgba(255,255,255,1.0); /* Fully opaque white text */
                font-size: 24px;
                font-weight: bold;
            }
        """)

        title_layout.addWidget(icon_label, 0, Qt.AlignCenter)
        title_layout.addWidget(title_label, 0, Qt.AlignCenter | Qt.AlignVCenter)
        title_layout.addStretch()

        # Divider line
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)
        divider.setStyleSheet("border: 1px solid #555555;")

        # About content label (HTML text)
        about_label = QLabel()
        about_label.setWordWrap(True)
        about_label.setAlignment(Qt.AlignTop)
        about_label.setOpenExternalLinks(True)
        about_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #ffffff;
                font-family: "Segoe UI";
                font-size: 14px;
            }
            h2 {
                margin-bottom: 5px;
                font-size: 20px;
                font-weight: bold;
                color: #ffffff;
            }
            h3 {
                margin-top: 15px;
                font-size: 16px;
                font-weight: bold;
                color: #ffffff;
            }
            p {
                line-height: 1.5;
                margin-bottom: 10px;
                color: #ffffff;
            }
            ul {
                margin-left: 20px;
            }
            li {
                margin-bottom: 5px;
            }
            a {
                color: #1e90ff;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
            }
        """)
        about_label.setText("""
            <h2>Version 3.1</h2>
            <p><b>Developed with Python and PyQt5.</b></p>
            <p>This application allows you to download entire websites for offline use, handling HTML pages, images, CSS, JS, fonts, and more. 
            It provides an intuitive interface, customizable settings, and detailed logs to help you manage and monitor your downloads efficiently.</p>

            <h3>Features</h3>
            <ul>
                <li>Full website downloading (HTML, images, CSS, JS, and more)</li>
                <li>Configurable crawl depth and resource filters</li>
                <li>Proxy and authentication support</li>
                <li>Advanced settings: max pages, max resources, ignore MIME types</li>
                <li>Schedule downloads and export logs</li>
                <li>Image Ripper mode to extract all images from a URL</li>
            </ul>

            <h3>Developer</h3>
            <p><strong>Developer:</strong> Robin Doak<br>
            <i>GitHub:</i> <a href="https://github.com/skillerious" target="_blank">https://github.com/skillerious</a></p>

            <h3>Icons & Credits</h3>
            <p><i>Icons by</i> <a href="https://www.flaticon.com/authors/freepik" target="_blank">Freepik</a> 
            <i>from</i> <a href="https://www.flaticon.com/" target="_blank">Flaticon</a></p>

            <h3>Contact</h3>
            <p>If you have feedback, suggestions, or run into issues, please reach out via GitHub or file an issue on the project's repository.</p>

            <h3>License</h3>
            <p>This project is distributed under the MIT License. For details, see the <a href="https://opensource.org/licenses/MIT" target="_blank">MIT License</a>.<br>
            Special thanks to the open-source community for providing invaluable tools and libraries. Your contributions and innovations inspire continuous improvement.</p>
        """)

        # Card frame to hold the about content
        card_frame = QFrame()
        card_frame.setStyleSheet("""
            QFrame {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 8px;
            }
        """)
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background-color: #3c3c3c;")
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.addWidget(about_label)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)
        scroll.setWidget(scroll_widget)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #3c3c3c;
            }
            QScrollBar:vertical {
                background: #3c3c3c;
                width: 8px;
                margin: 2px;
            }
            QScrollBar::handle:vertical {
                background: #555555;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #777777;
            }
        """)

        card_layout.addWidget(scroll)
        card_frame.setLayout(card_layout)

        main_layout.addLayout(title_layout)
        main_layout.addWidget(divider)
        main_layout.addWidget(card_frame)

        self.setLayout(main_layout)
        # Background of the entire widget
        self.setStyleSheet("background-color: #2b2b2b;")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = AboutWidget()
    w.show()
    sys.exit(app.exec_())
