import sys
from PyQt5.QtWidgets import QApplication
import qdarkstyle
from managers import SettingsManager, HistoryManager
from ui.mainwindow import MainWindow

def main():
    app = QApplication(sys.argv)
    SettingsManager.load_settings()
    HistoryManager.load_history()
    # Apply QDarkStyle theme
    app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt5'))
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
