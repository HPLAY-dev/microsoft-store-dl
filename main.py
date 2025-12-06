import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QToolBar, QLineEdit,
    QProgressBar, QPushButton, QHBoxLayout, QWidget,
    QMessageBox, QLabel, QVBoxLayout
)
from PySide6.QtGui import QAction
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineDownloadRequest
from PySide6.QtCore import QUrl, Qt, QTimer
import api


def app_path():
    return os.path.dirname(os.path.abspath(__file__))

def install_msix(path):
    command = f'cmd /c start powershell -Command "Add-AppxPackage -Path \'{path}\'"'
    os.system(command)

class DownloadWidget(QWidget):
    """下载进度控件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumHeight(40)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # 下载信息标签
        self.label = QLabel("准备下载...")
        self.label.setMinimumWidth(200)
        layout.addWidget(self.label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar, 1)
        
        # 取消按钮
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setFixedWidth(60)
        self.cancel_btn.clicked.connect(self.cancel_download)
        layout.addWidget(self.cancel_btn)
        
        # 当前下载任务
        self.current_download = None
        self.is_active = False
        
    def start_download(self, download, filename):
        """开始新的下载"""
        if self.is_active:
            # 已有下载任务，忽略新任务
            QMessageBox.information(self, "下载任务", "已有下载任务正在进行中")
            return False
            
        self.current_download = download
        self.is_active = True
        self.label.setText(f"正在下载: {filename}")
        self.progress_bar.setValue(0)
        self.cancel_btn.setEnabled(True)
        self.setVisible(True)
        return True
        
    def update_progress(self, received_bytes, total_bytes):
        """更新下载进度"""
        if total_bytes > 0:
            progress = int((received_bytes / total_bytes) * 100)
            self.progress_bar.setValue(progress)
            
            # 显示大小信息
            size_info = f"{self.format_size(received_bytes)} / {self.format_size(total_bytes)}"
            self.label.setText(f"下载中: {size_info}")
        else:
            self.progress_bar.setValue(0)
            size_info = self.format_size(received_bytes)
            self.label.setText(f"已接收: {size_info}")
            
    def complete_download(self, success=True):
        if success:
            self.label.setText("下载完成")
            self.progress_bar.setValue(100)
            
            # 立即隐藏，不要延迟
            QTimer.singleShot(1000, self.hide_widget)
        else:
            self.label.setText("下载失败")
            
        self.current_download = None
        self.is_active = False
        self.cancel_btn.setEnabled(False)
        
    def cancel_download(self):
        """取消下载"""
        if self.current_download:
            reply = QMessageBox.question(
                self, "取消下载",
                "确定要取消当前下载吗？",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.current_download.cancel()
                self.label.setText("下载已取消")
                self.current_download = None
                self.is_active = False
                self.cancel_btn.setEnabled(False)
                
                # 3秒后自动隐藏
                QTimer.singleShot(3000, self.hide_widget)
                
    def hide_widget(self):
        """隐藏控件"""
        self.setVisible(False)
        self.progress_bar.setValue(0)
        
    def format_size(self, bytes):
        """格式化文件大小显示"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024.0:
                return f"{bytes:.1f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.1f} TB"


class Browser(QMainWindow):
    def __init__(self, window_title: str, start_url: str):
        super().__init__()
        self.setWindowTitle(window_title)
        self.setGeometry(100, 100, 1200, 800)
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建导航栏容器
        navbar_container = QWidget()
        navbar_layout = QVBoxLayout(navbar_container)
        navbar_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建WebEngine视图
        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl(start_url))
        self.start_url = start_url
        
        # 创建导航栏
        self.create_navigation_bar()
        
        navbar_layout.addWidget(self.navbar)
        navbar_layout.addWidget(self.browser)
        
        main_layout.addWidget(navbar_container, 1)
        
        # 创建下载进度条
        self.create_download_widget()
        main_layout.addWidget(self.download_widget)
        
        # 初始化下载设置
        self.setup_download_handler()
        
        # 下载任务计数器
        self.download_count = 0
        
    def setup_download_handler(self):
        """设置下载处理器"""
        # 创建自定义下载目录
        download_dir = "downloads"
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)
            
        # 获取默认profile
        profile = QWebEngineProfile.defaultProfile()
        
        # 设置下载路径
        profile.setDownloadPath(download_dir)
        
        # 连接下载请求信号
        profile.downloadRequested.connect(self.on_download_requested)
        
        print(f"下载目录设置为: {download_dir}")
        
    def on_download_requested(self, download: QWebEngineDownloadRequest):
        """处理下载请求"""
        # 检查是否已有下载任务
        if self.download_widget.is_active:
            print("已有下载任务，忽略新下载请求")
            download.cancel()
            return
            
        # 获取文件名
        suggested_filename = download.suggestedFileName()
        download_url = download.url().toString()
        
        print(f"开始下载: {suggested_filename}")
        print(f"下载URL: {download_url}")
        
        # 设置下载路径（自动保存在downloads目录）
        save_path = suggested_filename
        
        # 如果文件已存在，添加序号
        counter = 1
        base_name, extension = os.path.splitext(suggested_filename)
        while os.path.exists(save_path):
            new_filename = f"{base_name} ({counter}){extension}"
            save_path = new_filename
            counter += 1
            
        # 配置下载任务
        download.setDownloadFileName(save_path)
        download.setSavePageFormat(QWebEngineDownloadRequest.CompleteHtmlSaveFormat)
        
        # 连接下载信号
        download.stateChanged.connect(lambda state, d=download: self.on_download_state_changed(d))
        download.receivedBytesChanged.connect(lambda d=download: self.on_download_progress(d))
        download.isFinishedChanged.connect(lambda d=download: self.on_download_finished(d))
        
        # 开始下载任务
        if self.download_widget.start_download(download, suggested_filename):
            download.accept()
            self.download_count += 1
        else:
            download.cancel()
            
    def on_download_state_changed(self, download: QWebEngineDownloadRequest):
        state = download.state()
        filename = os.path.basename(download.downloadFileName())
        
        # 使用枚举值检测状态
        if state == QWebEngineDownloadRequest.DownloadCompleted:
            print(f"下载完成")
            self.download_widget.complete_download(True)
            
            QMessageBox.information(
                self, "下载完成",
                f"下载完成\n保存位置: {download.downloadFileName()}"
            )

            install_msix(os.path.join(app_path(),'downloads', download.downloadFileName()))
            
        elif state == QWebEngineDownloadRequest.DownloadCancelled:
            print(f"下载取消: {filename}")
            self.download_widget.complete_download(False)
            
        elif state == QWebEngineDownloadRequest.DownloadInterrupted:
            print(f"下载中断: {filename}")
            self.download_widget.complete_download(False)
            
    def on_download_progress(self, download: QWebEngineDownloadRequest):
        if download == self.download_widget.current_download:
            received = download.receivedBytes()
            total = download.totalBytes()
            self.download_widget.update_progress(received, total)
            
            # 如果已经下载完成但状态未更新
            if total > 0 and received >= total:
                print("下载进度已完成，检查状态...")
                self.on_download_state_changed(download)
            
    def on_download_finished(self, download: QWebEngineDownloadRequest):
        """下载完成处理"""
        if download.isFinished():
            print(f"下载已完成: {download.suggestedFileName()}")
            
    def create_download_widget(self):
        """创建下载进度控件"""
        self.download_widget = DownloadWidget()
        self.download_widget.setVisible(False)  # 初始隐藏
        
    def create_navigation_bar(self):
        """创建导航工具栏"""
        self.navbar = QToolBar("导航栏")
        self.navbar.setMovable(False)
        
        # home按钮
        home_btn = QAction("⌂", self)
        home_btn.triggered.connect(self.home)
        self.navbar.addAction(home_btn)
        
        # 后退按钮
        back_btn = QAction("←", self)
        back_btn.triggered.connect(self.browser.back)
        self.navbar.addAction(back_btn)
        
        # 前进按钮
        forward_btn = QAction("→", self)
        forward_btn.triggered.connect(self.browser.forward)
        self.navbar.addAction(forward_btn)
        
        # 刷新按钮
        reload_btn = QAction("↻", self)
        reload_btn.triggered.connect(self.browser.reload)
        self.navbar.addAction(reload_btn)
        
        self.navbar.addSeparator()
        
        # 地址栏
        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("输入网址或应用链接...")
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        self.navbar.addWidget(self.url_bar)
        
        # 下载按钮
        download_btn = QAction("↓", self)
        download_btn.setToolTip("解析当前页面并下载")
        download_btn.triggered.connect(self.download_app)
        self.navbar.addAction(download_btn)
        
        # 更新地址栏显示
        self.browser.urlChanged.connect(self.update_url_bar)
        
    def home(self):
        """回到首页"""
        self.browser.setUrl(QUrl(self.start_url))
        
    def navigate_to_url(self):
        """导航到输入的URL"""
        url = self.url_bar.text().strip()
        if not url:
            return
            
        if not url.startswith(('http://', 'https://')):
            url = f'https://apps.microsoft.com/search?query={url}'
            
        self.browser.setUrl(QUrl(url))
        
    def update_url_bar(self, url):
        """更新地址栏显示"""
        self.url_bar.setText(url.toString())
        
    def download_app(self):
        """解析当前页面并下载"""
        current_url = self.browser.url().toString()
        
        if not current_url.startswith('https://apps.microsoft.com/detail/'):
            QMessageBox.warning(
                self, "无效链接",
                "请在 Microsoft Store 应用详情页面使用此功能！\n"
                "当前页面URL应以 'https://apps.microsoft.com/detail/' 开头。"
            )
            return
            
        try:
            # 调用API获取下载链接
            self.setWindowTitle("Microsoft Store - 获取文件中")
            receive = api.request_files_raw(current_url, url_type='url')
            self.browser.setHtml(receive)
            self.setWindowTitle("Microsoft Store")
                
        except Exception as e:
            QMessageBox.critical(
                self, "错误",
                f"下载过程中出现错误:\n{str(e)}"
            )
            
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 如果有正在进行的下载，询问用户
        if self.download_widget.is_active:
            reply = QMessageBox.question(
                self, "正在下载",
                "有文件正在下载，确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                event.ignore()
                return
                
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置应用程序信息
    app.setApplicationName("Microsoft Store")
    app.setOrganizationName("NOT Microsoft")
    
    # 设置高DPI支持
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    
    # 创建浏览器
    browser = Browser(
        window_title="Microsoft Store",
        start_url='https://apps.microsoft.com/'
    )
    
    browser.show()
    sys.exit(app.exec())