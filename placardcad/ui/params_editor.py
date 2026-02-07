"""
Editeur de parametres generaux d'un amenagement.
Formulaire avec onglets pour les differentes categories de parametres.
Support des configurations type (presets) sauvegardees en base.
"""

import json
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTabWidget, QSpinBox, QDoubleSpinBox, QCheckBox,
    QLineEdit, QLabel, QGroupBox, QScrollArea,
    QPushButton, QInputDialog, QMessageBox, QComboBox, QMenu
)
from PyQt5.QtCore import pyqtSignal

# Labels lisibles pour les categories
LABELS_CATEGORIES = {
    "panneau_separation": "Separation",
    "panneau_rayon": "Rayon",
    "panneau_rayon_haut": "Rayon haut",
    "panneau_mur": "Panneau mur",
    "crem_encastree": "Crem. encastree",
    "crem_applique": "Crem. applique",
    "tasseau": "Tasseau",
}


class ParamsEditor(QWidget):
    """Editeur de parametres generaux avec formulaire a onglets et presets."""

    params_modifies = pyqtSignal(dict)

    def __init__(self, db=None, parent=None):
        super().__init__(parent)
        self.db = db
        self._params = {}
        self._widgets = {}
        self._blocked = False
        self._init_ui()

    def set_db(self, db):
        """Definit la base de donnees (pour les presets)."""
        self.db = db

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel("Parametres")
        label.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(label)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.tabs.addTab(self._creer_onglet_dimensions(), "Dimensions")
        self.tabs.addTab(self._creer_onglet_panneaux(), "Panneaux")
        self.tabs.addTab(self._creer_onglet_cremailleres(), "Cremailleres")
        self.tabs.addTab(self._creer_onglet_tasseaux(), "Tasseaux")

    def _creer_spin(self, key: str, minimum: int = 0, maximum: int = 10000,
                    suffix: str = " mm") -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSuffix(suffix)
        spin.valueChanged.connect(self._on_value_changed)
        self._widgets[key] = spin
        return spin

    def _creer_dspin(self, key: str, minimum: float = 0, maximum: float = 100,
                     suffix: str = " mm", decimals: int = 1) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSuffix(suffix)
        spin.setDecimals(decimals)
        spin.valueChanged.connect(self._on_value_changed)
        self._widgets[key] = spin
        return spin

    def _creer_text(self, key: str) -> QLineEdit:
        edit = QLineEdit()
        edit.textChanged.connect(self._on_value_changed)
        self._widgets[key] = edit
        return edit

    def _creer_boutons_preset(self, categorie: str) -> QWidget:
        """Cree les boutons Sauver / Charger config type pour une categorie."""
        bar = QWidget()
        h = QHBoxLayout(bar)
        h.setContentsMargins(0, 4, 0, 4)

        btn_sauver = QPushButton("Sauver config type...")
        btn_sauver.setToolTip(f"Sauvegarder la config '{LABELS_CATEGORIES.get(categorie, categorie)}' comme preset reutilisable")
        btn_sauver.clicked.connect(lambda: self._sauver_preset(categorie))
        h.addWidget(btn_sauver)

        btn_charger = QPushButton("Charger config type...")
        btn_charger.setToolTip(f"Charger une config type sauvegardee")
        btn_charger.clicked.connect(lambda: self._charger_preset(categorie))
        h.addWidget(btn_charger)

        h.addStretch()
        return bar

    def _creer_onglet_dimensions(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        form.addRow("Hauteur:", self._creer_spin("hauteur", 500, 5000))
        form.addRow("Largeur:", self._creer_spin("largeur", 500, 10000))
        form.addRow("Profondeur:", self._creer_spin("profondeur", 200, 1500))
        form.addRow("Position rayon haut:", self._creer_spin("rayon_haut_position", 100, 2000))
        return widget

    def _creer_onglet_panneaux(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)

        for categorie, label_cat, avec_retrait in [
            ("panneau_separation", "Separation", False),
            ("panneau_rayon", "Rayon", True),
            ("panneau_rayon_haut", "Rayon haut", True),
            ("panneau_mur", "Panneau mur", False),
        ]:
            group = QGroupBox(label_cat)
            form = QFormLayout(group)
            form.addRow("Epaisseur:",
                        self._creer_spin(f"{categorie}.epaisseur", 6, 50))
            form.addRow("Couleur fab.:",
                        self._creer_text(f"{categorie}.couleur_fab"))
            form.addRow("Epaisseur chant:",
                        self._creer_dspin(f"{categorie}.chant_epaisseur", 0, 5))
            if avec_retrait:
                form.addRow("Retrait avant:",
                            self._creer_spin(f"{categorie}.retrait_avant", 0, 200))
                form.addRow("Retrait arriere:",
                            self._creer_spin(f"{categorie}.retrait_arriere", 0, 200))
            form.addRow(self._creer_boutons_preset(categorie))
            layout.addWidget(group)

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    def _creer_onglet_cremailleres(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)

        # Encastree
        group_enc = QGroupBox("Cremaillere encastree")
        form_enc = QFormLayout(group_enc)
        form_enc.addRow("Largeur:", self._creer_spin("crem_encastree.largeur", 5, 50))
        form_enc.addRow("Epaisseur:", self._creer_spin("crem_encastree.epaisseur", 1, 20))
        form_enc.addRow("Saillie:", self._creer_spin("crem_encastree.saillie", 0, 10))
        form_enc.addRow("Jeu rayon:", self._creer_spin("crem_encastree.jeu_rayon", 0, 10))
        form_enc.addRow("Retrait avant:", self._creer_spin("crem_encastree.retrait_avant", 10, 200))
        form_enc.addRow("Retrait arriere:", self._creer_spin("crem_encastree.retrait_arriere", 10, 200))
        form_enc.addRow(self._creer_boutons_preset("crem_encastree"))
        layout.addWidget(group_enc)

        # Applique
        group_app = QGroupBox("Cremaillere en applique")
        form_app = QFormLayout(group_app)
        form_app.addRow("Largeur:", self._creer_spin("crem_applique.largeur", 10, 50))
        form_app.addRow("Epaisseur saillie:", self._creer_spin("crem_applique.epaisseur_saillie", 5, 30))
        form_app.addRow("Jeu rayon:", self._creer_spin("crem_applique.jeu_rayon", 0, 10))
        form_app.addRow("Retrait avant:", self._creer_spin("crem_applique.retrait_avant", 10, 200))
        form_app.addRow("Retrait arriere:", self._creer_spin("crem_applique.retrait_arriere", 10, 200))
        form_app.addRow(self._creer_boutons_preset("crem_applique"))
        layout.addWidget(group_app)

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    def _creer_onglet_tasseaux(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        form.addRow("Section hauteur:", self._creer_spin("tasseau.section_h", 10, 100))
        form.addRow("Section largeur:", self._creer_spin("tasseau.section_l", 10, 100))
        form.addRow("Retrait avant:", self._creer_spin("tasseau.retrait_avant", 0, 100))
        form.addRow("Biseau longueur:", self._creer_spin("tasseau.biseau_longueur", 0, 50))
        form.addRow(self._creer_boutons_preset("tasseau"))
        return widget

    # --- Presets ---

    def _sauver_preset(self, categorie: str):
        """Sauvegarde les parametres courants de la categorie comme preset."""
        if not self.db:
            QMessageBox.warning(self, "Presets", "Base de donnees non disponible.")
            return

        self._lire_widgets_vers_params()
        params_cat = self._params.get(categorie, {})
        if not params_cat:
            return

        label = LABELS_CATEGORIES.get(categorie, categorie)
        nom, ok = QInputDialog.getText(
            self, "Sauver configuration type",
            f"Nom pour cette config '{label}' :"
        )
        if not ok or not nom:
            return

        self.db.sauver_configuration(nom, categorie, params_cat)
        QMessageBox.information(self, "Preset sauvegarde",
                                f"Configuration '{nom}' sauvegardee.\n"
                                f"Elle sera disponible dans tous vos projets.")

    def _charger_preset(self, categorie: str):
        """Charge un preset sauvegarde pour cette categorie."""
        if not self.db:
            QMessageBox.warning(self, "Presets", "Base de donnees non disponible.")
            return

        configs = self.db.lister_configurations(categorie)
        if not configs:
            QMessageBox.information(self, "Presets",
                                    f"Aucune configuration type sauvegardee "
                                    f"pour '{LABELS_CATEGORIES.get(categorie, categorie)}'.")
            return

        # Menu de selection avec option supprimer
        menu = QMenu(self)
        for cfg in configs:
            action = menu.addAction(f"{cfg['nom']}")
            action.setData(("charger", cfg["id"]))

        menu.addSeparator()
        for cfg in configs:
            action = menu.addAction(f"Supprimer: {cfg['nom']}")
            action.setData(("supprimer", cfg["id"]))

        action = menu.exec_(self.cursor().pos())
        if not action:
            return

        op, config_id = action.data()
        if op == "supprimer":
            cfg = self.db.get_configuration(config_id)
            rep = QMessageBox.question(
                self, "Supprimer preset",
                f"Supprimer la configuration '{cfg['nom']}' ?",
                QMessageBox.Yes | QMessageBox.No
            )
            if rep == QMessageBox.Yes:
                self.db.supprimer_configuration(config_id)
            return

        # Charger
        cfg = self.db.get_configuration(config_id)
        if not cfg:
            return

        self._params[categorie] = dict(cfg["params"])
        self._blocked = True
        try:
            self._ecrire_params_vers_widgets()
        finally:
            self._blocked = False
        self.params_modifies.emit(self._params)

    # --- Valeurs ---

    def _on_value_changed(self, *args):
        if self._blocked:
            return
        self._lire_widgets_vers_params()
        self.params_modifies.emit(self._params)

    def set_params(self, params: dict):
        """Charge les parametres dans le formulaire."""
        self._params = dict(params)
        self._blocked = True
        try:
            self._ecrire_params_vers_widgets()
        finally:
            self._blocked = False

    def get_params(self) -> dict:
        """Retourne les parametres courants."""
        self._lire_widgets_vers_params()
        return dict(self._params)

    def _ecrire_params_vers_widgets(self):
        """Ecrit les valeurs des params dans les widgets."""
        for key, widget in self._widgets.items():
            value = self._get_nested(self._params, key)
            if value is None:
                continue
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.setValue(value)
            elif isinstance(widget, QLineEdit):
                widget.setText(str(value))
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))

    def _lire_widgets_vers_params(self):
        """Lit les widgets et met a jour les params."""
        for key, widget in self._widgets.items():
            if isinstance(widget, QSpinBox):
                value = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                value = widget.value()
            elif isinstance(widget, QLineEdit):
                value = widget.text()
            elif isinstance(widget, QCheckBox):
                value = widget.isChecked()
            else:
                continue
            self._set_nested(self._params, key, value)

    def _get_nested(self, d: dict, key: str):
        """Acces a une cle imbriquee comme 'panneau_separation.epaisseur'."""
        parts = key.split(".")
        current = d
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    def _set_nested(self, d: dict, key: str, value):
        """Definit une valeur pour une cle imbriquee."""
        parts = key.split(".")
        current = d
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
