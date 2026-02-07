"""
Panneau arbre des projets et amenagements.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QToolBar, QAction, QInputDialog, QMessageBox, QMenu
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QIcon, QFont


class ProjectPanel(QWidget):
    """Arbre des projets avec leurs amenagements."""

    # Signaux
    projet_selectionne = pyqtSignal(int)          # projet_id
    amenagement_selectionne = pyqtSignal(int, int) # projet_id, amenagement_id
    donnees_modifiees = pyqtSignal()

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._init_ui()
        self.rafraichir()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Barre d'outils
        toolbar = QToolBar()
        toolbar.setIconSize(toolbar.iconSize())

        self.action_nouveau_projet = QAction("+ Projet", self)
        self.action_nouveau_projet.setToolTip("Nouveau projet")
        self.action_nouveau_projet.triggered.connect(self._nouveau_projet)
        toolbar.addAction(self.action_nouveau_projet)

        self.action_nouvel_amenagement = QAction("+ Amenagement", self)
        self.action_nouvel_amenagement.setToolTip("Nouvel amenagement")
        self.action_nouvel_amenagement.triggered.connect(self._nouvel_amenagement)
        self.action_nouvel_amenagement.setEnabled(False)
        toolbar.addAction(self.action_nouvel_amenagement)

        self.action_supprimer = QAction("Supprimer", self)
        self.action_supprimer.setToolTip("Supprimer l'element selectionne")
        self.action_supprimer.triggered.connect(self._supprimer)
        self.action_supprimer.setEnabled(False)
        toolbar.addAction(self.action_supprimer)

        layout.addWidget(toolbar)

        # Arbre
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Projets / Amenagements"])
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu_contextuel)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree.itemDoubleClicked.connect(self._on_double_click)

        font = QFont()
        font.setPointSize(10)
        self.tree.setFont(font)

        layout.addWidget(self.tree)

    def rafraichir(self):
        """Recharge l'arbre depuis la base de donnees."""
        self.tree.clear()
        projets = self.db.lister_projets()

        for projet in projets:
            item_projet = QTreeWidgetItem([
                f"{projet['nom']} ({projet['client']})" if projet['client']
                else projet['nom']
            ])
            item_projet.setData(0, Qt.UserRole, ("projet", projet["id"]))
            font = item_projet.font(0)
            font.setBold(True)
            item_projet.setFont(0, font)

            amenagements = self.db.lister_amenagements(projet["id"])
            for am in amenagements:
                item_am = QTreeWidgetItem([f"  {am['nom']}"])
                item_am.setData(0, Qt.UserRole, ("amenagement", projet["id"], am["id"]))
                item_projet.addChild(item_am)

            self.tree.addTopLevelItem(item_projet)
            item_projet.setExpanded(True)

    def _on_selection_changed(self):
        items = self.tree.selectedItems()
        if not items:
            self.action_nouvel_amenagement.setEnabled(False)
            self.action_supprimer.setEnabled(False)
            return

        data = items[0].data(0, Qt.UserRole)
        if data[0] == "projet":
            self.action_nouvel_amenagement.setEnabled(True)
            self.action_supprimer.setEnabled(True)
            self.projet_selectionne.emit(data[1])
        elif data[0] == "amenagement":
            self.action_nouvel_amenagement.setEnabled(True)
            self.action_supprimer.setEnabled(True)
            self.amenagement_selectionne.emit(data[1], data[2])

    def _on_double_click(self, item, column):
        data = item.data(0, Qt.UserRole)
        if data[0] == "projet":
            self._renommer_projet(data[1])
        elif data[0] == "amenagement":
            self._renommer_amenagement(data[2])

    def _get_projet_id_selectionne(self) -> int | None:
        """Retourne l'id du projet selectionne (ou parent du amenagement selectionne)."""
        items = self.tree.selectedItems()
        if not items:
            return None
        data = items[0].data(0, Qt.UserRole)
        if data[0] == "projet":
            return data[1]
        elif data[0] == "amenagement":
            return data[1]
        return None

    def _nouveau_projet(self):
        nom, ok = QInputDialog.getText(self, "Nouveau projet", "Nom du projet:")
        if ok and nom:
            self.db.creer_projet(nom=nom)
            self.rafraichir()
            self.donnees_modifiees.emit()

    def _nouvel_amenagement(self):
        projet_id = self._get_projet_id_selectionne()
        if projet_id is None:
            QMessageBox.warning(self, "Attention", "Selectionnez d'abord un projet.")
            return
        am_id = self.db.creer_amenagement(projet_id)
        self.rafraichir()
        self.donnees_modifiees.emit()
        # Selectionner le nouvel amenagement
        self._selectionner_amenagement(projet_id, am_id)

    def _selectionner_amenagement(self, projet_id: int, amenagement_id: int):
        """Selectionne un amenagement dans l'arbre."""
        for i in range(self.tree.topLevelItemCount()):
            item_p = self.tree.topLevelItem(i)
            data_p = item_p.data(0, Qt.UserRole)
            if data_p[0] == "projet" and data_p[1] == projet_id:
                for j in range(item_p.childCount()):
                    item_a = item_p.child(j)
                    data_a = item_a.data(0, Qt.UserRole)
                    if data_a[0] == "amenagement" and data_a[2] == amenagement_id:
                        self.tree.setCurrentItem(item_a)
                        return

    def _supprimer(self):
        items = self.tree.selectedItems()
        if not items:
            return
        data = items[0].data(0, Qt.UserRole)

        if data[0] == "projet":
            rep = QMessageBox.question(
                self, "Confirmer",
                "Supprimer ce projet et tous ses amenagements ?",
                QMessageBox.Yes | QMessageBox.No
            )
            if rep == QMessageBox.Yes:
                self.db.supprimer_projet(data[1])
                self.rafraichir()
                self.donnees_modifiees.emit()

        elif data[0] == "amenagement":
            rep = QMessageBox.question(
                self, "Confirmer",
                "Supprimer cet amenagement ?",
                QMessageBox.Yes | QMessageBox.No
            )
            if rep == QMessageBox.Yes:
                self.db.supprimer_amenagement(data[2])
                self.rafraichir()
                self.donnees_modifiees.emit()

    def _renommer_projet(self, projet_id: int):
        projet = self.db.get_projet(projet_id)
        if not projet:
            return
        nom, ok = QInputDialog.getText(
            self, "Renommer le projet", "Nouveau nom:", text=projet["nom"]
        )
        if ok and nom:
            self.db.modifier_projet(projet_id, nom=nom)
            self.rafraichir()
            self.donnees_modifiees.emit()

    def _renommer_amenagement(self, amenagement_id: int):
        am = self.db.get_amenagement(amenagement_id)
        if not am:
            return
        nom, ok = QInputDialog.getText(
            self, "Renommer l'amenagement", "Nouveau nom:", text=am["nom"]
        )
        if ok and nom:
            self.db.modifier_amenagement(amenagement_id, nom=nom)
            self.rafraichir()
            self.donnees_modifiees.emit()

    def _menu_contextuel(self, pos):
        item = self.tree.itemAt(pos)
        menu = QMenu(self)

        if item is None:
            action = menu.addAction("Nouveau projet")
            action.triggered.connect(self._nouveau_projet)
        else:
            data = item.data(0, Qt.UserRole)
            if data[0] == "projet":
                a1 = menu.addAction("Renommer")
                a1.triggered.connect(lambda: self._renommer_projet(data[1]))
                a2 = menu.addAction("Nouvel amenagement")
                a2.triggered.connect(self._nouvel_amenagement)
                menu.addSeparator()
                a3 = menu.addAction("Modifier infos projet...")
                a3.triggered.connect(lambda: self.projet_selectionne.emit(data[1]))
                menu.addSeparator()
                a4 = menu.addAction("Supprimer")
                a4.triggered.connect(self._supprimer)
            elif data[0] == "amenagement":
                a1 = menu.addAction("Renommer")
                a1.triggered.connect(lambda: self._renommer_amenagement(data[2]))
                menu.addSeparator()
                a2 = menu.addAction("Supprimer")
                a2.triggered.connect(self._supprimer)

        menu.exec_(self.tree.mapToGlobal(pos))
