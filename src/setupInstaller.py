import sys
import os
import json
import zipfile
import tempfile
import shutil
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QTextEdit, QProgressBar, QLineEdit, QHBoxLayout,
    QCheckBox
)
from PyQt5.QtCore import Qt
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2

PASSWORD = "amarlanguage"  # same hardcoded password as compiler


class SetupInstaller(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MMR App Installer (Linux)")
        self.setGeometry(250, 250, 600, 550)

        self.mmr_file = None
        self.metadata = None
        self.temp_dir = None
        self.license_text = None

        self.initUI()

    def initUI(self):
        central = QWidget()
        layout = QVBoxLayout()

        self.label = QLabel("Select an .mmr file to install")
        layout.addWidget(self.label)

        self.open_btn = QPushButton("Open .mmr File")
        self.open_btn.clicked.connect(self.open_mmr)
        layout.addWidget(self.open_btn)

        # License display
        self.license_box = QTextEdit()
        self.license_box.setReadOnly(True)
        self.license_box.hide()
        layout.addWidget(self.license_box)

        # Install path chooser
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Default: /usr/local/<app_name>")
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self.browse_install_path)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.browse_btn)
        layout.addLayout(path_layout)

        # Checkbox for desktop shortcut
        self.desktop_checkbox = QCheckBox("Create Desktop Shortcut (.desktop)")
        self.desktop_checkbox.setChecked(True)
        layout.addWidget(self.desktop_checkbox)

        self.install_btn = QPushButton("Install")
        self.install_btn.clicked.connect(self.install_app)
        self.install_btn.setEnabled(False)
        layout.addWidget(self.install_btn)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        central.setLayout(layout)
        self.setCentralWidget(central)

    def open_mmr(self):
        file, _ = QFileDialog.getOpenFileName(self, "Open MMR File", filter="MMR Files (*.mmr)")
        if file:
            self.mmr_file = file
            self.extract_mmr()
            if self.license_text:
                self.license_box.setPlainText(self.license_text)
                self.license_box.show()
            self.install_btn.setEnabled(True)
            self.label.setText(f"Loaded {os.path.basename(file)}")

    def extract_mmr(self):
        with open(self.mmr_file, "rb") as f:
            data = f.read()

        # Decrypt
        salt, nonce, tag, ciphertext = data[:16], data[16:32], data[32:48], data[48:]
        key = PBKDF2(PASSWORD, salt, dkLen=32)
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        decrypted = cipher.decrypt_and_verify(ciphertext, tag)

        # Extract zip
        self.temp_dir = tempfile.mkdtemp()
        with tempfile.NamedTemporaryFile(delete=False) as tmp_zip:
            tmp_zip.write(decrypted)
            tmp_zip.flush()
            with zipfile.ZipFile(tmp_zip.name, "r") as z:
                z.extractall(self.temp_dir)

        # Load metadata
        metadata_file = os.path.join(self.temp_dir, "metadata.json")
        with open(metadata_file, "r") as f:
            self.metadata = json.load(f)

        # Load license
        license_file = os.path.join(self.temp_dir, "LICENSE.txt")
        if os.path.exists(license_file):
            with open(license_file, "r") as f:
                self.license_text = f.read()
        else:
            self.license_text = None

    def browse_install_path(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Install Directory")
        if folder:
            self.path_input.setText(folder)

    def install_app(self):
        if not self.metadata:
            QMessageBox.warning(self, "Error", "No metadata found.")
            return

        app_name = self.metadata["app_name"]

        # Determine install path
        base_path = self.path_input.text().strip()
        if not base_path:
            base_path = f"/usr/local/{app_name}"
        install_path = Path(base_path)
        os.makedirs(install_path, exist_ok=True)

        files_dir = Path(self.temp_dir) / "FILES"

        total_files = sum(len(files) for _, _, files in os.walk(files_dir))
        done = 0

        for root, _, files in os.walk(files_dir):
            rel_path = os.path.relpath(root, files_dir)
            target_dir = install_path / rel_path
            os.makedirs(target_dir, exist_ok=True)
            for file in files:
                src = Path(root) / file
                dst = target_dir / file
                shutil.copy2(src, dst)
                done += 1
                self.progress.setValue(int((done / total_files) * 100))

        # Optional .desktop entry
        if self.desktop_checkbox.isChecked():
            desktop_entry = f"""[Desktop Entry]
Name={app_name}
Exec={install_path}/main
Icon={install_path}/icon.png
Type=Application
Terminal=false
"""
            desktop_path = f"/usr/share/applications/{app_name}.desktop"
            try:
                with open(desktop_path, "w") as f:
                    f.write(desktop_entry)
            except PermissionError:
                user_local = Path.home() / ".local/share/applications"
                user_local.mkdir(parents=True, exist_ok=True)
                with open(user_local / f"{app_name}.desktop", "w") as f:
                    f.write(desktop_entry)

        self.progress.setValue(100)
        QMessageBox.information(self, "Success", f"{app_name} installed successfully!")

        # Cleanup
        shutil.rmtree(self.temp_dir)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = SetupInstaller()
    win.show()
    sys.exit(app.exec_())
