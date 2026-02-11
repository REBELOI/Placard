"""Application PyQt5 principale de PlacardCAD.

Point d'entree de l'application. Initialise l'interface graphique PyQt5,
la base de donnees SQLite et lance la fenetre principale.
"""

import sys
import os
from pathlib import Path

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont, QIcon

from .database import Database
from .ui.main_window import MainWindow


def get_db_path() -> Path:
    """Retourne le chemin de la base de donnees SQLite.

    Cree le repertoire ~/.placardcad/ s'il n'existe pas.

    Returns:
        Chemin absolu vers le fichier placardcad.db dans le dossier utilisateur.
    """
    # Base de donnees dans le dossier utilisateur
    data_dir = Path.home() / ".placardcad"
    data_dir.mkdir(exist_ok=True)
    return data_dir / "placardcad.db"


def run():
    """Lance l'application PlacardCAD.

    Initialise QApplication avec le style Fusion, configure la police globale,
    cree la base de donnees et affiche la fenetre principale.
    L'application se termine quand la fenetre est fermee.
    """
    app = QApplication(sys.argv)

    # Style global
    app.setStyle("Fusion")
    font = QFont()
    font.setPointSize(10)
    app.setFont(font)

    # Icone application
    icon_path = os.path.join(os.path.dirname(__file__), "resources", "icon_256.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Base de donnees
    db_path = get_db_path()
    db = Database(db_path)

    # Fenetre principale
    window = MainWindow(db)
    window.show()

    sys.exit(app.exec_())
