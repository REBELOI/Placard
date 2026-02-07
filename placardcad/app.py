"""
Application PyQt5 principale de PlacardCAD.
"""

import sys
import os
from pathlib import Path

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont

from .database import Database
from .ui.main_window import MainWindow


def get_db_path() -> Path:
    """Retourne le chemin de la base de donnees."""
    # Base de donnees dans le dossier utilisateur
    data_dir = Path.home() / ".placardcad"
    data_dir.mkdir(exist_ok=True)
    return data_dir / "placardcad.db"


def run():
    """Lance l'application PlacardCAD."""
    app = QApplication(sys.argv)

    # Style global
    app.setStyle("Fusion")
    font = QFont()
    font.setPointSize(10)
    app.setFont(font)

    # Base de donnees
    db_path = get_db_path()
    db = Database(db_path)

    # Fenetre principale
    window = MainWindow(db)
    window.show()

    sys.exit(app.exec_())
