from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QListWidget, QSizePolicy, QProgressBar, QPushButton, QApplication, QMainWindow
from PyQt5.QtGui import QPixmap

from minecraft_launcher_lib.utils import get_minecraft_directory, get_version_list
from minecraft_launcher_lib.install import install_minecraft_version
from minecraft_launcher_lib.command import get_minecraft_command

minecraft_directory = get_minecraft_directory().replace('minecraft', 'hexolauncher')

class LaunchThread(QThread):
    launch_setup_signal = pyqtSignal(str, str)
    progress_update_signal = pyqtSignal(int, int, str)
    state_update_signal = pyqtSignal(bool)

    version_id = ''
    username = ''

    progress = 0
    progress_max = 0
    progress_label = ''

    def __init__(self):
        super().__init__()
        self.launch_setup_signal.connect(self.launch_setup)

    def launch_setup(self, version_id, username):
        self.version_id = version_id
        self.username = username
    
    def update_progress_label(self, value):
        self.progress_label = value
        self.progress_update_signal.emit(self.progress, self.progress_max, self.progress_label)
    def update_progress(self, value):
        self.progress = value
        self.progress_update_signal.emit(self.progress, self.progress_max, self.progress_label)
    def update_progress_max(self, value):
        self.progress_max = value
        self.progress_update_signal.emit(self.progress, self.progress_max, self.progress_label)

    def run(self):
        self.state_update_signal.emit(True)

        install_minecraft_version(versionid=self.version_id, minecraft_directory=minecraft_directory, callback={ 'setStatus': self.update_progress_label, 'setProgress': self.update_progress, 'setMax': self.update_progress_max })

        if self.username == '':
            self.username = generate_username()[0]
        
        options = {
            'username': self.username,
            'uuid': str(uuid1()),
            'token': ''
        }

        call(get_minecraft_command(version=self.version_id, minecraft_directory=minecraft_directory, options=options))
        self.state_update_signal.emit(False)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("HexoLauncher")
        self.setStyleSheet("color: white; background-color: #000F1A;")

        self.centralwidget = QWidget(self)

        self.logo_path = "C:/Users/Eldreamer/Desktop/hexolauncher/assets/minecraft_logo.png"
        self.logo = QLabel(self.centralwidget)
        self.logo.setAlignment(Qt.AlignCenter)
        self.set_logo_icon(self.logo_path)

        self.description = QLabel(self.centralwidget)
        self.description.setText("Welcome! Choose your Minecraft version:")
        self.description.setAlignment(Qt.AlignCenter)
        self.description.setStyleSheet("font-size: 16px;")

        self.version_list = QListWidget(self.centralwidget)
        self.version_list.setStyleSheet("font-size: 14px; background-color: #34495E; border: 1px solid #2C3E50; border-radius: 5px; padding: 5px; color: white;")
        self.populate_version_list()

        self.username = QLineEdit(self.centralwidget)
        self.username.setPlaceholderText('Enter Username')
        self.username.setAlignment(Qt.AlignCenter)
        self.username.setStyleSheet("font-size: 14px; background-color: #34495E; border: 1px solid #2C3E50; border-radius: 5px; padding: 5px; color: white;")

        self.start_progress = QProgressBar(self.centralwidget)
        self.start_progress.setVisible(False)
        self.start_progress.setStyleSheet("QProgressBar { color: #3498DB; border: 1px solid #2C3E50; border-radius: 5px; background-color: #34495E; } QProgressBar::chunk { background-color: #2E86C1; }")

        self.start_button = QPushButton(self.centralwidget)
        self.start_button.setText('Play')
        self.start_button.setStyleSheet("QPushButton { background-color: #3498DB; color: white; border: none; border-radius: 5px; padding: 10px; font-size: 16px; } QPushButton:hover { background-color: #2E86C1; }")
        self.start_button.clicked.connect(self.launch_game)

        self.vertical_layout = QVBoxLayout(self.centralwidget)
        self.vertical_layout.addWidget(self.logo)
        self.vertical_layout.addWidget(self.description)
        self.vertical_layout.addWidget(self.version_list)
        self.vertical_layout.addWidget(self.username)
        self.vertical_layout.addWidget(self.start_progress)
        self.vertical_layout.addWidget(self.start_button)
        self.vertical_layout.setAlignment(Qt.AlignCenter)

        self.launch_thread = LaunchThread()
        self.launch_thread.state_update_signal.connect(self.state_update)
        self.launch_thread.progress_update_signal.connect(self.update_progress)

        self.setCentralWidget(self.centralwidget)

    def set_logo_icon(self, path):
        pixmap = QPixmap(path)
        self.logo.setPixmap(pixmap.scaledToHeight(200))  # Установите размеры изображения

    def populate_version_list(self):
        versions = get_version_list()
        for version in versions:
            self.version_list.addItem(version['id'])
        
    def state_update(self, value):
        self.start_button.setDisabled(value)
        self.start_progress.setVisible(value)

    def update_progress(self, progress, max_progress, label):
        self.start_progress.setValue(progress)
        self.start_progress.setMaximum(max_progress)
        self.start_progress.setFormat(label)

    def launch_game(self):
        selected_version = self.version_list.currentItem().text()
        self.launch_thread.launch_setup_signal.emit(selected_version, self.username.text())
        self.launch_thread.start()

if __name__ == '__main__':
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec_()

