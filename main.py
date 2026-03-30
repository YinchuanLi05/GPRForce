import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # 全局样式优化
    app.setStyle('Fusion') 
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())