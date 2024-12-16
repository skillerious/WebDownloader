from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QTextBrowser, QSizePolicy
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QFont, QColor

class AboutWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        # Adjust margins and spacing as desired
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(20)

        title_layout = QHBoxLayout()
        title_layout.setSpacing(10)

        icon_label = QLabel()
        icon_pixmap = QPixmap("icons/app_icon.png").scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        icon_label.setPixmap(icon_pixmap)

        title_label = QLabel("About Web Downloader")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 28px;
                font-weight: bold;
                color: #ffffff;
                background: transparent;
            }
        """)

        title_layout.addWidget(icon_label, 0, Qt.AlignCenter)
        title_layout.addWidget(title_label, 0, Qt.AlignCenter | Qt.AlignVCenter)
        title_layout.addStretch()

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)
        divider.setStyleSheet("border: 1px solid #555555;")

        about_label = QTextBrowser()
        about_label.setOpenExternalLinks(True)
        # Make background transparent so text appears over card gradient
        about_label.setStyleSheet("""
            QTextBrowser {
                color: #ffffff;
                background: transparent; 
                font-family: "Segoe UI";
                font-size: 16px;
                border: none;
            }
            a {
                color: #1e90ff;
            }
            a:hover {
                text-decoration: underline;
            }
            h2 {
                margin-bottom:5px; 
                font-size:20px;
            }
            h3 {
                font-size:18px;
                margin: 10px 0 5px 0;
            }
            p, ul, li {
                line-height: 1.4em;
            }
            ul {
                margin-left: 20px;
            }
        """)

        about_text = """
            <h2>Version 3.1</h2>
            <p><b>Developed with Python and PyQt5.</b></p>

            <p>This application allows you to download entire websites for offline use, handling:</p>
            <ul>
                <li>HTML pages</li>
                <li>Images and Videos</li>
                <li>CSS, JavaScript, and Fonts</li>
                <li>Documents (PDF, DOCX, etc.)</li>
            </ul>
            
            <h3>Key Features</h3>
            <p>
            - Intuitive interface to start and manage downloads<br>
            - Detailed logs and progress indicators<br>
            - Support for multiple file types and deep links<br>
            - Configurable concurrency, timeout, and proxy settings<br>
            - Caching and conditional requests for efficiency
            </p>
            
            <h3>Developer</h3>
            <p><strong>Robin Doak</strong></p>
            
            <h3>Credits & Acknowledgements</h3>
            <p>
            Icons by <a href="https://www.flaticon.com/authors/freepik" target="_blank">Freepik</a> 
            from <a href="https://www.flaticon.com/" target="_blank">Flaticon</a><br>
            Special thanks to the open-source community for providing invaluable tools and libraries.<br>
            Powered by <b>Python</b>, <b>PyQt5</b>, and <b>aiohttp</b>.
            </p>
            
            <h3>Learn More</h3>
            <p>
            Visit our <a href="https://example.com/docs" target="_blank">Documentation</a> for detailed guides, 
            or check out our <a href="https://example.com/support" target="_blank">Support Page</a> if you need assistance.
            </p>
            
            <h3>Open Source</h3>
            <p>
            Contribute on <a href="https://github.com/example/WebDownloader" target="_blank">GitHub</a> and help improve this tool!
            </p>
        """
        about_label.setHtml(about_text)

        # Create a scroll area and widget that fills space
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.addWidget(about_label)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)
        scroll.setWidget(scroll_widget)

        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
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

        card_frame = QFrame()
        # Give the card a subtle gradient and make it fully expand
        card_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2c2c2c, stop:1 #3c3c3c);
                border: 1px solid #555555;
                border-radius: 8px;
            }
        """)
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(10)
        card_layout.addWidget(scroll)

        # Make sure the card expands
        card_frame.setLayout(card_layout)
        card_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        main_layout.addLayout(title_layout)
        main_layout.addWidget(divider)
        main_layout.addWidget(card_frame)


        self.setLayout(main_layout)
        self.setStyleSheet("background-color: #2b2b2b;")

        # Ensure widget expands to fill space
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
