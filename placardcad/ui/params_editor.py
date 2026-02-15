"""
Editeur de parametres generaux d'un amenagement.
Formulaire avec onglets pour les differentes categories de parametres.
Support de deux modes (Placard / Meuble) avec onglets specifiques.
Support d'une configuration type globale (preset) sauvegardee en base.
"""

import json
import sip
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTabWidget, QSpinBox, QDoubleSpinBox, QCheckBox,
    QLineEdit, QLabel, QGroupBox, QScrollArea,
    QPushButton, QInputDialog, QMessageBox, QMenu,
    QComboBox,
)
from PyQt5.QtCore import pyqtSignal

# Cles regroupees dans une config type (tout sauf dimensions)
CLES_CONFIG_TYPE_PLACARD = [
    "panneau_separation",
    "panneau_rayon",
    "panneau_rayon_haut",
    "panneau_mur",
    "crem_encastree",
    "crem_applique",
    "tasseau",
]

CLES_CONFIG_TYPE_MEUBLE = [
    "panneau",
    "facade",
    "poignee",
    "dessus",
    "dessous",
    "fond",
    "plinthe",
    "tiroir",
    "porte",
    "etagere",
    "separation",
    "cremaillere",
]


class ParamsEditor(QWidget):
    """Editeur de parametres generaux avec formulaire a onglets, preset global et aide contextuelle."""

    params_modifies = pyqtSignal(dict)

    # Tooltips pour chaque champ de parametres
    _TOOLTIPS = {
        # Dimensions placard
        "hauteur": "Hauteur totale du placard (sol au plafond), en mm",
        "largeur": "Largeur totale du placard (mur a mur), en mm",
        "profondeur": "Profondeur du placard (de la face avant au mur du fond), en mm",
        "rayon_haut_position": "Distance entre le plafond et le rayon haut, en mm",

        # Dimensions meuble
        "epaisseur": "Epaisseur des panneaux de structure du meuble, en mm",
        "epaisseur_facade": "Epaisseur des facades (portes/tiroirs), en mm",
        "hauteur_plinthe": "Hauteur de la plinthe sous le meuble (0 = pas de plinthe), en mm",

        # Panneaux placard
        "panneau_separation.epaisseur": "Epaisseur du panneau de separation vertical entre compartiments",
        "panneau_separation.couleur_fab": "Reference couleur/decor du panneau chez le fournisseur",
        "panneau_separation.chant_epaisseur": "Epaisseur du chant colle sur les bords visibles, en mm",
        "panneau_separation.sens_fil": "Cocher pour aligner le fil du bois dans le sens de la longueur lors du debit",
        "panneau_rayon.epaisseur": "Epaisseur des rayons (etageres reglables), en mm",
        "panneau_rayon.couleur_fab": "Reference couleur/decor du rayon chez le fournisseur",
        "panneau_rayon.chant_epaisseur": "Epaisseur du chant colle sur le bord avant du rayon",
        "panneau_rayon.sens_fil": "Respecter le sens du fil du bois pour les rayons",
        "panneau_rayon.retrait_avant": "Recul du rayon par rapport a la face avant du placard, en mm",
        "panneau_rayon.retrait_arriere": "Recul du rayon par rapport au mur du fond, en mm",
        "panneau_rayon_haut.epaisseur": "Epaisseur du rayon haut (etagere fixe en haut), en mm",
        "panneau_rayon_haut.couleur_fab": "Reference couleur/decor du rayon haut",
        "panneau_rayon_haut.chant_epaisseur": "Epaisseur du chant du rayon haut",
        "panneau_rayon_haut.sens_fil": "Respecter le sens du fil pour le rayon haut",
        "panneau_rayon_haut.retrait_avant": "Recul du rayon haut par rapport a la face avant, en mm",
        "panneau_rayon_haut.retrait_arriere": "Recul du rayon haut par rapport au mur du fond, en mm",
        "panneau_mur.epaisseur": "Epaisseur du panneau mur (fixe sur le mur lateral pour les cremailleres), en mm",
        "panneau_mur.couleur_fab": "Reference couleur/decor du panneau mur",
        "panneau_mur.chant_epaisseur": "Epaisseur du chant du panneau mur",
        "panneau_mur.sens_fil": "Respecter le sens du fil pour le panneau mur",

        # Cremailleres
        "crem_encastree.largeur": "Largeur de la cremaillere encastree (rainure dans le panneau), en mm",
        "crem_encastree.epaisseur": "Epaisseur de la cremaillere encastree, en mm",
        "crem_encastree.saillie": "Depassement de la cremaillere hors du panneau, en mm",
        "crem_encastree.jeu_rayon": "Jeu entre le rayon et la cremaillere (pour insertion facile), en mm",
        "crem_encastree.pas": "Pas de perforation de la cremaillere (espacement entre trous), en mm",
        "crem_encastree.retrait_avant": "Distance entre la face avant et le debut de la cremaillere, en mm",
        "crem_encastree.retrait_arriere": "Distance entre le mur du fond et la fin de la cremaillere, en mm",
        "crem_applique.largeur": "Largeur de la cremaillere en applique, en mm",
        "crem_applique.epaisseur_saillie": "Epaisseur de la cremaillere en saillie (vissee sur le mur), en mm",
        "crem_applique.jeu_rayon": "Jeu entre le rayon et la cremaillere applique, en mm",
        "crem_applique.pas": "Pas de perforation de la cremaillere applique, en mm",
        "crem_applique.retrait_avant": "Distance entre la face avant et le debut de la cremaillere, en mm",
        "crem_applique.retrait_arriere": "Distance entre le mur du fond et la fin de la cremaillere, en mm",

        # Tasseaux
        "tasseau.section_h": "Hauteur de la section du tasseau, en mm",
        "tasseau.section_l": "Largeur de la section du tasseau, en mm",
        "tasseau.retrait_avant": "Recul du tasseau par rapport a la face avant du placard, en mm",
        "tasseau.biseau_longueur": "Longueur du biseau (coupe en angle) a l'extremite du tasseau, en mm",

        # Meuble — structure
        "assemblage": "Type d'assemblage : dessus_entre (entre les cotes) ou dessus_sur (sur les cotes)",
        "pose": "Mode de pose des facades : applique, semi-applique ou encloisonnee",
        "panneau.couleur_fab": "Reference couleur/decor des panneaux de structure",
        "panneau.chant_epaisseur": "Epaisseur du chant colle sur les bords visibles des panneaux",
        "panneau.chant_couleur_fab": "Reference couleur du chant (si different du panneau)",
        "facade.couleur_fab": "Reference couleur/decor des facades (portes et tiroirs)",
        "dessus.type": "Type de dessus : traverses (2 bandes avant/arriere) ou plein (panneau complet)",
        "dessus.largeur_traverse": "Largeur des traverses du dessus, en mm",
        "dessous.retrait_arriere": "Recul du panneau du dessous par rapport a l'arriere, en mm",
        "fond.type": "Mode de fixation du fond : rainure, vissage ou applique",
        "fond.epaisseur": "Epaisseur du panneau de fond, en mm",
        "fond.profondeur_rainure": "Profondeur de la rainure pour le fond (si mode rainure), en mm",
        "fond.distance_chant": "Distance entre le chant arriere et la rainure du fond, en mm",
        "fond.hauteur": "Hauteur du fond (0 = pleine hauteur du meuble), en mm",
        "plinthe.type": "Type de plinthe : avant seule, trois cotes ou aucune",
        "plinthe.retrait": "Recul de la plinthe par rapport a la face avant, en mm",
        "plinthe.retrait_gauche": "Recul de la plinthe cote gauche, en mm",
        "plinthe.retrait_droite": "Recul de la plinthe cote droit, en mm",
        "plinthe.epaisseur": "Epaisseur de la plinthe, en mm",

        # Meuble — facades
        "porte.jeu_haut": "Jeu entre le haut de la porte et le dessus du meuble, en mm",
        "porte.jeu_bas": "Jeu entre le bas de la porte et le dessous du meuble, en mm",
        "porte.jeu_lateral": "Jeu lateral entre la porte et le cote du meuble, en mm",
        "porte.jeu_entre": "Jeu entre deux portes adjacentes, en mm",
        "tiroir.hauteur": "Hauteur de coulisse LEGRABOX : M=90.5, K=128.5, C=193, F=257 mm",
        "tiroir.jeu_lateral": "Jeu lateral entre le tiroir et le cote du meuble, en mm",
        "tiroir.jeu_entre": "Jeu vertical entre deux tiroirs, en mm",
        "poignee.modele": "Modele de poignee : baton inox ou aucune",
        "poignee.entraxe": "Distance entre les deux vis de fixation de la poignee, en mm",
        "poignee.distance_haut": "Distance entre le haut de la facade et l'axe de la poignee, en mm",

        # Meuble — interieur
        "etagere.jeu_lateral": "Jeu lateral entre l'etagere et les cotes du meuble, en mm",
        "etagere.retrait_avant": "Recul de l'etagere par rapport a la face avant du meuble, en mm",
        "separation.epaisseur": "Epaisseur des panneaux de separation interieure, en mm",
        "separation.retrait_avant": "Recul de la separation par rapport a la face avant, en mm",
        "separation.retrait_arriere": "Recul de la separation par rapport a l'arriere, en mm",
        "cremaillere.largeur": "Largeur de la cremaillere aluminium interieure, en mm",
        "cremaillere.profondeur": "Profondeur d'encastrement de la cremaillere alu, en mm",
        "cremaillere.distance_avant": "Distance entre la face avant et la cremaillere, en mm",
        "cremaillere.distance_arriere": "Distance entre l'arriere et la cremaillere, en mm",

        # Debit
        "debit.panneau_longueur": "Longueur du panneau brut (format fournisseur), en mm",
        "debit.panneau_largeur": "Largeur du panneau brut (format fournisseur), en mm",
        "debit.trait_scie": "Largeur du trait de scie (perte de matiere a chaque coupe), en mm",
        "debit.surcote": "Surcote ajoutee de chaque cote des pieces (marge de securite), en mm",
        "debit.delignage": "Perte lors du premier trait de mise d'equerre du panneau brut, en mm",
        "debit.sens_fil": "Respecter le sens du fil du bois lors de l'optimisation de debit",
    }

    def __init__(self, db=None, parent=None):
        super().__init__(parent)
        self.db = db
        self._params = {}
        self._widgets = {}
        self._blocked = False
        self._mode = "Placard"
        self._init_ui()

    def set_db(self, db):
        """Definit la base de donnees (pour les presets)."""
        self.db = db

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Barre du haut : titre + boutons config type
        top_bar = QHBoxLayout()
        self._label_titre = QLabel("Parametres — Placard")
        self._label_titre.setStyleSheet("font-weight: bold; padding: 4px;")
        top_bar.addWidget(self._label_titre)
        top_bar.addStretch()

        btn_sauver = QPushButton("Sauver config type...")
        btn_sauver.setToolTip("Sauvegarder la configuration comme preset reutilisable")
        btn_sauver.clicked.connect(self._sauver_preset)
        top_bar.addWidget(btn_sauver)

        btn_charger = QPushButton("Charger config type...")
        btn_charger.setToolTip("Charger une config type sauvegardee")
        btn_charger.clicked.connect(self._charger_preset)
        top_bar.addWidget(btn_charger)

        layout.addLayout(top_bar)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self._creer_onglets_placard()

    # =================================================================
    #  MODE : basculer entre Placard et Meuble
    # =================================================================

    def set_mode(self, mode: str):
        """Change le mode d'affichage (Placard ou Meuble).

        Reconstruit les onglets avec les parametres specifiques au mode.

        Args:
            mode: 'Placard' ou 'Meuble'.
        """
        if mode == self._mode:
            return
        self._mode = mode
        # Sauver les params courants avant de reconstruire
        self._lire_widgets_vers_params()
        # Vider onglets et widgets
        while self.tabs.count() > 0:
            w = self.tabs.widget(0)
            self.tabs.removeTab(0)
            w.deleteLater()
        self._widgets.clear()
        # Bloquer les signaux pendant la reconstruction
        self._blocked = True
        try:
            if mode == "Meuble":
                self._creer_onglets_meuble()
                self._label_titre.setText("Parametres — Meuble")
            else:
                self._creer_onglets_placard()
                self._label_titre.setText("Parametres — Placard")
            # Re-peupler les widgets depuis les params
            self._ecrire_params_vers_widgets()
        finally:
            self._blocked = False

    def get_mode(self) -> str:
        """Retourne le mode courant ('Placard' ou 'Meuble')."""
        return self._mode

    # =================================================================
    #  WIDGETS DE BASE
    # =================================================================

    def _appliquer_tooltip(self, widget: QWidget, key: str):
        """Applique le tooltip contextuel correspondant a la cle du parametre."""
        tip = self._TOOLTIPS.get(key)
        if tip:
            widget.setToolTip(tip)

    def _creer_spin(self, key: str, minimum: int = 0, maximum: int = 10000,
                    suffix: str = " mm") -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSuffix(suffix)
        spin.valueChanged.connect(self._on_value_changed)
        self._widgets[key] = spin
        self._appliquer_tooltip(spin, key)
        return spin

    def _creer_dspin(self, key: str, minimum: float = 0, maximum: float = 100,
                     suffix: str = " mm", decimals: int = 1) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSuffix(suffix)
        spin.setDecimals(decimals)
        spin.valueChanged.connect(self._on_value_changed)
        self._widgets[key] = spin
        self._appliquer_tooltip(spin, key)
        return spin

    def _creer_check(self, key: str, label: str = "") -> QCheckBox:
        chk = QCheckBox(label)
        chk.stateChanged.connect(self._on_value_changed)
        self._widgets[key] = chk
        self._appliquer_tooltip(chk, key)
        return chk

    def _creer_text(self, key: str) -> QLineEdit:
        edit = QLineEdit()
        edit.textChanged.connect(self._on_value_changed)
        self._widgets[key] = edit
        self._appliquer_tooltip(edit, key)
        return edit

    def _creer_combo(self, key: str, options: list[str]) -> QComboBox:
        combo = QComboBox()
        combo.addItems(options)
        combo.currentTextChanged.connect(self._on_value_changed)
        self._widgets[key] = combo
        self._appliquer_tooltip(combo, key)
        return combo

    # =================================================================
    #  ONGLETS PLACARD
    # =================================================================

    def _creer_onglets_placard(self):
        """Cree les onglets specifiques au mode Placard."""
        self.tabs.addTab(self._creer_onglet_dimensions_placard(), "Dimensions")
        self.tabs.addTab(self._creer_onglet_panneaux(), "Panneaux")
        self.tabs.addTab(self._creer_onglet_cremailleres(), "Cremailleres")
        self.tabs.addTab(self._creer_onglet_tasseaux(), "Tasseaux")
        self.tabs.addTab(self._creer_onglet_debit(), "Debit")

    def _creer_onglet_dimensions_placard(self) -> QWidget:
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
            form.addRow("Sens du fil:",
                        self._creer_check(f"{categorie}.sens_fil",
                                          "Respecter le sens du fil (debit)"))
            if avec_retrait:
                form.addRow("Retrait avant:",
                            self._creer_spin(f"{categorie}.retrait_avant", 0, 200))
                form.addRow("Retrait arriere:",
                            self._creer_spin(f"{categorie}.retrait_arriere", 0, 200))
            layout.addWidget(group)

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    def _creer_onglet_cremailleres(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)

        group_enc = QGroupBox("Cremaillere encastree")
        form_enc = QFormLayout(group_enc)
        form_enc.addRow("Largeur:", self._creer_spin("crem_encastree.largeur", 5, 50))
        form_enc.addRow("Epaisseur:", self._creer_spin("crem_encastree.epaisseur", 1, 20))
        form_enc.addRow("Saillie:", self._creer_spin("crem_encastree.saillie", 0, 10))
        form_enc.addRow("Jeu rayon:", self._creer_spin("crem_encastree.jeu_rayon", 0, 10))
        form_enc.addRow("Pas:", self._creer_spin("crem_encastree.pas", 10, 100))
        form_enc.addRow("Retrait avant:", self._creer_spin("crem_encastree.retrait_avant", 10, 200))
        form_enc.addRow("Retrait arriere:", self._creer_spin("crem_encastree.retrait_arriere", 10, 200))
        layout.addWidget(group_enc)

        group_app = QGroupBox("Cremaillere en applique")
        form_app = QFormLayout(group_app)
        form_app.addRow("Largeur:", self._creer_spin("crem_applique.largeur", 10, 50))
        form_app.addRow("Epaisseur saillie:", self._creer_spin("crem_applique.epaisseur_saillie", 5, 30))
        form_app.addRow("Jeu rayon:", self._creer_spin("crem_applique.jeu_rayon", 0, 10))
        form_app.addRow("Pas:", self._creer_spin("crem_applique.pas", 10, 100))
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

    # =================================================================
    #  ONGLETS MEUBLE
    # =================================================================

    def _creer_onglets_meuble(self):
        """Cree les onglets specifiques au mode Meuble."""
        self.tabs.addTab(self._creer_onglet_dimensions_meuble(), "Dimensions")
        self.tabs.addTab(self._creer_onglet_structure_meuble(), "Structure")
        self.tabs.addTab(self._creer_onglet_facades_meuble(), "Facades")
        self.tabs.addTab(self._creer_onglet_interieur_meuble(), "Interieur")
        self.tabs.addTab(self._creer_onglet_debit(), "Debit")

    def _creer_onglet_dimensions_meuble(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        form.addRow("Hauteur:", self._creer_spin("hauteur", 200, 3000))
        form.addRow("Largeur:", self._creer_spin("largeur", 200, 5000))
        form.addRow("Profondeur:", self._creer_spin("profondeur", 200, 1000))
        form.addRow("Epaisseur panneaux:", self._creer_spin("epaisseur", 10, 50))
        form.addRow("Epaisseur facades:", self._creer_spin("epaisseur_facade", 10, 50))
        form.addRow("Hauteur plinthe:", self._creer_spin("hauteur_plinthe", 0, 300))
        return widget

    def _creer_onglet_structure_meuble(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)

        # Assemblage
        group_ass = QGroupBox("Assemblage")
        form_ass = QFormLayout(group_ass)
        form_ass.addRow("Type:", self._creer_combo(
            "assemblage", ["dessus_entre", "dessus_sur"]))
        form_ass.addRow("Pose facades:", self._creer_combo(
            "pose", ["applique", "semi_applique", "encloisonnee"]))
        layout.addWidget(group_ass)

        # Panneau structure
        group_pan = QGroupBox("Panneau structure")
        form_pan = QFormLayout(group_pan)
        form_pan.addRow("Couleur fab.:", self._creer_text("panneau.couleur_fab"))
        form_pan.addRow("Epaisseur chant:", self._creer_dspin(
            "panneau.chant_epaisseur", 0, 5))
        form_pan.addRow("Couleur chant:", self._creer_text("panneau.chant_couleur_fab"))
        layout.addWidget(group_pan)

        # Facade
        group_fac = QGroupBox("Facade")
        form_fac = QFormLayout(group_fac)
        form_fac.addRow("Couleur fab.:", self._creer_text("facade.couleur_fab"))
        layout.addWidget(group_fac)

        # Dessus
        group_dessus = QGroupBox("Dessus")
        form_dessus = QFormLayout(group_dessus)
        form_dessus.addRow("Type:", self._creer_combo(
            "dessus.type", ["traverses", "plein"]))
        form_dessus.addRow("Largeur traverse:", self._creer_spin(
            "dessus.largeur_traverse", 50, 300))
        layout.addWidget(group_dessus)

        # Dessous
        group_dessous = QGroupBox("Dessous")
        form_dessous = QFormLayout(group_dessous)
        form_dessous.addRow("Retrait arriere:", self._creer_spin(
            "dessous.retrait_arriere", 0, 200))
        layout.addWidget(group_dessous)

        # Fond
        group_fond = QGroupBox("Fond")
        form_fond = QFormLayout(group_fond)
        form_fond.addRow("Type:", self._creer_combo(
            "fond.type", ["rainure", "vissage", "applique"]))
        form_fond.addRow("Epaisseur:", self._creer_spin("fond.epaisseur", 2, 20))
        form_fond.addRow("Profondeur rainure:", self._creer_spin(
            "fond.profondeur_rainure", 2, 20))
        form_fond.addRow("Distance chant:", self._creer_spin(
            "fond.distance_chant", 0, 50))
        form_fond.addRow("Hauteur (0=pleine):", self._creer_spin(
            "fond.hauteur", 0, 3000))
        layout.addWidget(group_fond)

        # Plinthe
        group_plinthe = QGroupBox("Plinthe")
        form_plinthe = QFormLayout(group_plinthe)
        form_plinthe.addRow("Type:", self._creer_combo(
            "plinthe.type", ["avant", "trois_cotes", "aucune"]))
        form_plinthe.addRow("Retrait avant:", self._creer_spin("plinthe.retrait", 0, 100))
        form_plinthe.addRow("Retrait gauche:", self._creer_spin("plinthe.retrait_gauche", 0, 100))
        form_plinthe.addRow("Retrait droite:", self._creer_spin("plinthe.retrait_droite", 0, 100))
        form_plinthe.addRow("Epaisseur:", self._creer_spin("plinthe.epaisseur", 6, 50))
        layout.addWidget(group_plinthe)

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    def _creer_onglet_facades_meuble(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)

        # Portes
        group_porte = QGroupBox("Portes (charnieres CLIP top)")
        form_porte = QFormLayout(group_porte)
        form_porte.addRow("Jeu haut:", self._creer_spin("porte.jeu_haut", 0, 20))
        form_porte.addRow("Jeu bas:", self._creer_spin("porte.jeu_bas", 0, 20))
        form_porte.addRow("Jeu lateral:", self._creer_spin("porte.jeu_lateral", 0, 20))
        form_porte.addRow("Jeu entre portes:", self._creer_spin("porte.jeu_entre", 0, 20))
        layout.addWidget(group_porte)

        # Tiroirs
        group_tiroir = QGroupBox("Tiroirs (LEGRABOX Blum)")
        form_tiroir = QFormLayout(group_tiroir)
        form_tiroir.addRow("Hauteur coulisse:", self._creer_combo(
            "tiroir.hauteur", ["M", "K", "C", "F"]))
        form_tiroir.addRow("Jeu lateral:", self._creer_spin("tiroir.jeu_lateral", 0, 20))
        form_tiroir.addRow("Jeu entre tiroirs:", self._creer_spin(
            "tiroir.jeu_entre", 0, 20))

        # Info hauteurs LEGRABOX
        info = QLabel("M=90.5  K=128.5  C=193  F=257 mm")
        info.setStyleSheet("color: #666; font-size: 10px; padding: 4px;")
        form_tiroir.addRow("", info)
        layout.addWidget(group_tiroir)

        # Poignees
        group_poignee = QGroupBox("Poignees")
        form_poignee = QFormLayout(group_poignee)
        form_poignee.addRow("Modele:", self._creer_combo(
            "poignee.modele", ["baton_inox", "aucune"]))
        entraxes = ["96", "128", "160", "192", "224", "256",
                    "320", "392", "492", "592", "692", "792"]
        form_poignee.addRow("Entraxe (mm):", self._creer_combo(
            "poignee.entraxe", entraxes))
        form_poignee.addRow("Distance haut:", self._creer_spin(
            "poignee.distance_haut", 10, 200))
        layout.addWidget(group_poignee)

    def _creer_onglet_interieur_meuble(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)

        # Etageres
        group_etag = QGroupBox("Etageres")
        form_etag = QFormLayout(group_etag)
        form_etag.addRow("Jeu lateral:", self._creer_spin("etagere.jeu_lateral", 0, 10))
        form_etag.addRow("Retrait avant:", self._creer_spin(
            "etagere.retrait_avant", 0, 100))
        layout.addWidget(group_etag)

        # Separations
        group_sep = QGroupBox("Separations")
        form_sep = QFormLayout(group_sep)
        form_sep.addRow("Epaisseur:", self._creer_spin("separation.epaisseur", 10, 50))
        form_sep.addRow("Retrait avant:", self._creer_spin(
            "separation.retrait_avant", 0, 100))
        form_sep.addRow("Retrait arriere:", self._creer_spin(
            "separation.retrait_arriere", 0, 100))
        layout.addWidget(group_sep)

        # Cremailleres alu
        group_crem = QGroupBox("Cremailleres aluminium")
        form_crem = QFormLayout(group_crem)
        form_crem.addRow("Largeur:", self._creer_spin("cremaillere.largeur", 5, 50))
        form_crem.addRow("Profondeur:", self._creer_spin("cremaillere.profondeur", 2, 20))
        form_crem.addRow("Distance avant:", self._creer_spin(
            "cremaillere.distance_avant", 10, 100))
        form_crem.addRow("Distance arriere:", self._creer_spin(
            "cremaillere.distance_arriere", 10, 100))
        layout.addWidget(group_crem)

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    # =================================================================
    #  ONGLET PARTAGE : DEBIT
    # =================================================================

    def _creer_onglet_debit(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        form.addRow("Panneau longueur:", self._creer_spin("debit.panneau_longueur", 500, 5000))
        form.addRow("Panneau largeur:", self._creer_spin("debit.panneau_largeur", 500, 3000))
        form.addRow("Trait de scie:", self._creer_dspin("debit.trait_scie", 0, 10))
        form.addRow("Surcote (par cote):", self._creer_dspin("debit.surcote", 0, 10))
        form.addRow("Delignage:", self._creer_dspin("debit.delignage", 0, 30))
        form.addRow("Sens du fil:", self._creer_check("debit.sens_fil",
                                                       "Respecter le sens du fil"))
        return widget

    # =================================================================
    #  PRESET GLOBAL
    # =================================================================

    def _get_cles_config_type(self) -> list[str]:
        """Retourne les cles de config type selon le mode courant."""
        if self._mode == "Meuble":
            return CLES_CONFIG_TYPE_MEUBLE
        return CLES_CONFIG_TYPE_PLACARD

    def _extraire_config_type(self) -> dict:
        """Extrait les parametres de config type (sans dimensions)."""
        self._lire_widgets_vers_params()
        cles = self._get_cles_config_type()
        result = {}
        for cle in cles:
            if cle in self._params:
                val = self._params[cle]
                result[cle] = dict(val) if isinstance(val, dict) else val
        return result

    def _appliquer_config_type(self, config_type: dict):
        """Applique une config type sur les parametres courants (sans toucher aux dimensions)."""
        cles = self._get_cles_config_type()
        for cle in cles:
            if cle in config_type:
                val = config_type[cle]
                self._params[cle] = dict(val) if isinstance(val, dict) else val
        self._blocked = True
        try:
            self._ecrire_params_vers_widgets()
        finally:
            self._blocked = False
        self.params_modifies.emit(self._params)

    def _sauver_preset(self):
        """Sauvegarde la config comme preset global."""
        if not self.db:
            QMessageBox.warning(self, "Config type", "Base de donnees non disponible.")
            return

        config_type = self._extraire_config_type()
        if not config_type:
            return

        categorie = "globale" if self._mode == "Placard" else "meuble"
        configs = self.db.lister_configurations(categorie)

        menu = QMenu(self)
        action_new = menu.addAction("Nouvelle configuration...")
        action_new.setData(("nouveau", 0))

        if configs:
            menu.addSeparator()
            label_action = menu.addAction("-- Ecraser une config existante --")
            label_action.setEnabled(False)
            for cfg in configs:
                action = menu.addAction(f"  {cfg['nom']}")
                action.setData(("ecraser", cfg["id"]))

        action = menu.exec_(self.cursor().pos())
        if not action or not action.data():
            return

        op, config_id = action.data()

        if op == "nouveau":
            nom, ok = QInputDialog.getText(
                self, f"Sauver configuration type ({self._mode})",
                "Nom de la configuration :"
            )
            if not ok or not nom:
                return
            self.db.sauver_configuration(nom, categorie, config_type)
            QMessageBox.information(
                self, "Configuration sauvegardee",
                f"Configuration '{nom}' sauvegardee.\n"
                f"Reutilisable sur tous vos projets ({self._mode})."
            )
        elif op == "ecraser":
            cfg = self.db.get_configuration(config_id)
            if not cfg:
                return
            rep = QMessageBox.question(
                self, "Ecraser configuration",
                f"Ecraser la configuration '{cfg['nom']}' avec les parametres actuels ?",
                QMessageBox.Yes | QMessageBox.No
            )
            if rep == QMessageBox.Yes:
                self.db.modifier_configuration(config_id, params=config_type)
                QMessageBox.information(
                    self, "Configuration ecrasee",
                    f"Configuration '{cfg['nom']}' mise a jour."
                )

    def _charger_preset(self):
        """Charge un preset global sauvegarde."""
        if not self.db:
            QMessageBox.warning(self, "Config type", "Base de donnees non disponible.")
            return

        categorie = "globale" if self._mode == "Placard" else "meuble"
        configs = self.db.lister_configurations(categorie)
        if not configs:
            QMessageBox.information(
                self, "Config type",
                "Aucune configuration type sauvegardee.\n"
                "Utilisez 'Sauver config type...' pour en creer une."
            )
            return

        menu = QMenu(self)
        for cfg in configs:
            action = menu.addAction(cfg["nom"])
            action.setData(("charger", cfg["id"]))

        if len(configs) > 0:
            menu.addSeparator()
            sub = menu.addMenu("Supprimer...")
            for cfg in configs:
                action = sub.addAction(cfg["nom"])
                action.setData(("supprimer", cfg["id"]))

        action = menu.exec_(self.cursor().pos())
        if not action or not action.data():
            return

        op, config_id = action.data()
        if op == "supprimer":
            cfg = self.db.get_configuration(config_id)
            rep = QMessageBox.question(
                self, "Supprimer",
                f"Supprimer la configuration '{cfg['nom']}' ?",
                QMessageBox.Yes | QMessageBox.No
            )
            if rep == QMessageBox.Yes:
                self.db.supprimer_configuration(config_id)
            return

        cfg = self.db.get_configuration(config_id)
        if not cfg:
            return

        self._appliquer_config_type(cfg["params"])

    # =================================================================
    #  VALEURS
    # =================================================================

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
            if sip.isdeleted(widget):
                continue
            value = self._get_nested(self._params, key)
            if value is None:
                continue
            if isinstance(widget, QComboBox):
                idx = widget.findText(str(value))
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.setValue(value)
            elif isinstance(widget, QLineEdit):
                widget.setText(str(value))
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))

    def _lire_widgets_vers_params(self):
        """Lit les widgets et met a jour les params."""
        for key, widget in list(self._widgets.items()):
            if sip.isdeleted(widget):
                continue
            if isinstance(widget, QComboBox):
                value = widget.currentText()
            elif isinstance(widget, QSpinBox):
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
