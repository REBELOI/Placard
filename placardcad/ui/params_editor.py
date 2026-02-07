"""
Editeur de parametres generaux d'un amenagement.
Formulaire avec onglets pour les differentes categories de parametres.
"""

import json
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTabWidget, QSpinBox, QDoubleSpinBox, QCheckBox,
    QLineEdit, QLabel, QGroupBox, QScrollArea
)
from PyQt5.QtCore import pyqtSignal


class ParamsEditor(QWidget):
    """Editeur de parametres generaux avec formulaire a onglets."""

    params_modifies = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._params = {}
        self._widgets = {}
        self._blocked = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel("Parametres")
        label.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(label)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Onglet Dimensions
        self.tabs.addTab(self._creer_onglet_dimensions(), "Dimensions")
        # Onglet Panneaux
        self.tabs.addTab(self._creer_onglet_panneaux(), "Panneaux")
        # Onglet Cremailleres
        self.tabs.addTab(self._creer_onglet_cremailleres(), "Cremailleres")
        # Onglet Tasseaux
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

        for categorie, label_cat in [
            ("panneau_separation", "Separation"),
            ("panneau_rayon", "Rayon"),
            ("panneau_rayon_haut", "Rayon haut"),
            ("panneau_mur", "Panneau mur"),
        ]:
            group = QGroupBox(label_cat)
            form = QFormLayout(group)
            form.addRow("Epaisseur:",
                        self._creer_spin(f"{categorie}.epaisseur", 6, 50))
            form.addRow("Couleur fab.:",
                        self._creer_text(f"{categorie}.couleur_fab"))
            form.addRow("Epaisseur chant:",
                        self._creer_dspin(f"{categorie}.chant_epaisseur", 0, 5))
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
        layout.addWidget(group_enc)

        # Applique
        group_app = QGroupBox("Cremaillere en applique")
        form_app = QFormLayout(group_app)
        form_app.addRow("Largeur:", self._creer_spin("crem_applique.largeur", 10, 50))
        form_app.addRow("Epaisseur saillie:", self._creer_spin("crem_applique.epaisseur_saillie", 5, 30))
        form_app.addRow("Jeu rayon:", self._creer_spin("crem_applique.jeu_rayon", 0, 10))
        form_app.addRow("Retrait avant:", self._creer_spin("crem_applique.retrait_avant", 10, 200))
        form_app.addRow("Retrait arriere:", self._creer_spin("crem_applique.retrait_arriere", 10, 200))
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
        return widget

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
