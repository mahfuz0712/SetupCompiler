import sys
import os
import json
import zipfile
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QTextEdit, QPushButton,
    QFileDialog, QVBoxLayout, QHBoxLayout, QListWidget, QMessageBox
)
from PyQt5.QtGui import QIcon
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes

PASSWORD = "amarlanguage"  # Hardcoded password for encryption/decryption


class MMRCreator(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MMR Setup Compiler")
        self.resize(600, 550)

        # ----------------------
        # Set window icon (cross-platform safe)
        # ----------------------
        possible_icons = [
            Path("src/assets/compiler.ico"),
            Path("icons/app_icon.png"),
            Path("assets/compiler.ico"),
            Path("assets/app_icon.png"),
        ]
        for icon_path in possible_icons:
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
                break

        # Metadata fields
        self.name_input = QLineEdit()
        self.version_input = QLineEdit()
        self.author_input = QLineEdit()
        self.desc_input = QTextEdit()
        self.path_input = QLineEdit()
        self.license_file = None

        # File list
        self.files_list = QListWidget()

        # Buttons
        self.add_files_btn = QPushButton("Add Files")
        self.add_folder_btn = QPushButton("Add Folder")
        self.remove_btn = QPushButton("Remove Selected")
        self.create_btn = QPushButton("Compile to .mmr")
        self.license_btn = QPushButton("Add License File")
        self.save_project_btn = QPushButton("Save Project (.mrsc)")
        self.load_project_btn = QPushButton("Load Project (.mrsc)")

        # Layouts
        layout = QVBoxLayout()

        layout.addWidget(QLabel("App Name:"))
        layout.addWidget(self.name_input)

        layout.addWidget(QLabel("Version:"))
        layout.addWidget(self.version_input)

        layout.addWidget(QLabel("Author:"))
        layout.addWidget(self.author_input)

        layout.addWidget(QLabel("Description:"))
        layout.addWidget(self.desc_input)

        layout.addWidget(QLabel("Default Install Path (e.g. /usr/local/bin):"))
        layout.addWidget(self.path_input)

        layout.addWidget(QLabel("Files to Include:"))
        layout.addWidget(self.files_list)

        # File buttons row
        file_btns = QHBoxLayout()
        file_btns.addWidget(self.add_files_btn)
        file_btns.addWidget(self.add_folder_btn)
        file_btns.addWidget(self.remove_btn)
        layout.addLayout(file_btns)

        # Project buttons row
        proj_btns = QHBoxLayout()
        proj_btns.addWidget(self.license_btn)
        proj_btns.addWidget(self.save_project_btn)
        proj_btns.addWidget(self.load_project_btn)
        layout.addLayout(proj_btns)

        layout.addWidget(self.create_btn)
        self.setLayout(layout)

        # Connect signals
        self.add_files_btn.clicked.connect(self.add_files)
        self.add_folder_btn.clicked.connect(self.add_folder)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.create_btn.clicked.connect(self.create_mmr)
        self.license_btn.clicked.connect(self.select_license)
        self.save_project_btn.clicked.connect(self.save_project)
        self.load_project_btn.clicked.connect(self.load_project)

        # Internal storage
        self.included_files = []

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files")
        for f in files:
            if f not in self.included_files:
                self.included_files.append(f)
                self.files_list.addItem(f)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            for root, dirs, files in os.walk(folder):
                for f in files:
                    full_path = os.path.join(root, f)
                    if full_path not in self.included_files:
                        self.included_files.append(full_path)
                        self.files_list.addItem(full_path)

    def remove_selected(self):
        for item in self.files_list.selectedItems():
            self.included_files.remove(item.text())
            self.files_list.takeItem(self.files_list.row(item))

    def select_license(self):
        file, _ = QFileDialog.getOpenFileName(
            self,
            "Select License File",
            "",
            "All Files (*)"
        )
        if file:
            filename = os.path.basename(file)
            if filename == "LICENSE":
                self.license_file = file
                QMessageBox.information(self, "Selected", f"License file set: {file}")
            else:
                QMessageBox.warning(
                    self,
                    "Invalid File",
                    "Please select a file named LICENSE (with no extension)."
                )

    def save_project(self):
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", f"{self.name_input.text() or 'project'}.mrsc", "MRSC Project (*.mrsc)"
        )
        if not save_path:
            return

        project_data = {
            "name": self.name_input.text().strip(),
            "version": self.version_input.text().strip(),
            "author": self.author_input.text().strip(),
            "description": self.desc_input.toPlainText().strip(),
            "default_path": self.path_input.text().strip(),
            "files": self.included_files,
            "license": self.license_file,
        }

        with open(save_path, "w") as f:
            json.dump(project_data, f, indent=4)

        QMessageBox.information(self, "Saved", f"Project saved:\n{save_path}")

    def load_project(self):
        file, _ = QFileDialog.getOpenFileName(self, "Open Project", filter="MRSC Project (*.mrsc)")
        if not file:
            return

        with open(file, "r") as f:
            data = json.load(f)

        self.name_input.setText(data.get("name", ""))
        self.version_input.setText(data.get("version", ""))
        self.author_input.setText(data.get("author", ""))
        self.desc_input.setPlainText(data.get("description", ""))
        self.path_input.setText(data.get("default_path", ""))
        self.included_files = data.get("files", [])
        self.license_file = data.get("license", None)

        self.files_list.clear()
        for f in self.included_files:
            self.files_list.addItem(f)

        QMessageBox.information(self, "Loaded", f"Project loaded:\n{file}")

    def create_mmr(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Error", "App Name is required")
            return
        if not self.included_files:
            QMessageBox.warning(self, "Error", "No files selected")
            return

        # Metadata
        metadata = {
            "app_name": self.name_input.text().strip(),
            "version": self.version_input.text().strip(),
            "author": self.author_input.text().strip(),
            "description": self.desc_input.toPlainText().strip(),
            "default_path": self.path_input.text().strip(),
        }

        # Save as .mmr
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Package", f"{metadata['app_name']}.mmr", "MMR Files (*.mmr)"
        )
        if not save_path:
            return

        # Create temp zip
        temp_zip = save_path + ".zip"
        with zipfile.ZipFile(temp_zip, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("metadata.json", json.dumps(metadata, indent=4))
            if self.license_file:
                z.write(self.license_file, "LICENSE.txt")
            for f in self.included_files:
                arcname = os.path.join("FILES", os.path.relpath(f, start=os.path.dirname(self.included_files[0])))
                z.write(f, arcname)

        # Encrypt with AES
        salt = get_random_bytes(16)
        key = PBKDF2(PASSWORD, salt, dkLen=32)
        cipher = AES.new(key, AES.MODE_GCM)
        with open(temp_zip, "rb") as f:
            plaintext = f.read()
        ciphertext, tag = cipher.encrypt_and_digest(plaintext)

        with open(save_path, "wb") as f:
            f.write(salt + cipher.nonce + tag + ciphertext)

        os.remove(temp_zip)

        QMessageBox.information(self, "Success", f"Compiled Successfully:\n{save_path}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MMRCreator()
    win.show()
    sys.exit(app.exec_())
