"""Fenetre principale de PlacardCAD.

Contient la classe MainWindow qui orchestre l'ensemble de l'interface :
arbre des projets, editeurs de schema et parametres, vue 2D de face,
et toutes les actions d'export (PDF, DXF, FreeCAD, etiquettes, liste de courses).
"""

import json
import os
import tempfile
import subprocess
import sys

from PyQt5.QtWidgets import (
    QMainWindow, QSplitter, QWidget, QVBoxLayout, QHBoxLayout,
    QAction, QToolBar, QStatusBar, QFileDialog, QMessageBox,
    QLabel, QTabWidget, QStackedWidget, QComboBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QIcon

from .project_panel import ProjectPanel
from .schema_editor import SchemaEditor
from .params_editor import ParamsEditor
from .viewer_3d import PlacardViewer
from .debit_dialog import DebitDialog
from .pieces_manuelles_editor import PiecesManualesEditor

from ..database import Database, PARAMS_DEFAUT
from ..schema_parser import schema_vers_config
from ..placard_builder import generer_geometrie_2d
from ..meuble_schema_parser import est_schema_meuble, meuble_schema_vers_config
from ..meuble_builder import generer_geometrie_meuble
from ..pdf_export import exporter_pdf, exporter_pdf_projet
from ..optimisation_debit import pieces_depuis_fiche, PieceDebit, ParametresDebit
from ..freecad_export import exporter_freecad
from ..dxf_export import exporter_dxf
from ..etiquettes_export import exporter_etiquettes
from ..liste_courses import generer_liste_courses, exporter_liste_courses


class MainWindow(QMainWindow):
    """Fenetre principale de l'application PlacardCAD.

    Organise l'interface en trois panneaux horizontaux :
    arbre projets (gauche), editeurs schema/parametres (centre),
    vue de face 2D (droite). Gere la sauvegarde automatique,
    la generation de la vue et les exports.

    Attributes:
        db: Instance de la base de donnees SQLite.
        splitter_main: Splitter horizontal principal.
        project_panel: Panneau arbre des projets et amenagements.
        schema_editor: Editeur du schema compact.
        params_editor: Editeur des parametres generaux.
        pieces_editor: Editeur tableur des pieces manuelles.
        viewer: Widget de visualisation 2D de face.
        stacked_centre: Widget empile pour alterner editeurs / pieces manuelles.
    """

    def __init__(self, db: Database, parent=None):
        """Initialise la fenetre principale.

        Args:
            db: Instance de la base de donnees a utiliser.
            parent: Widget parent optionnel.
        """
        super().__init__(parent)
        self.db = db
        self._current_projet_id = None
        self._current_amenagement_id = None
        self._auto_save_timer = QTimer()
        self._auto_save_timer.setInterval(2000)
        self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.timeout.connect(self._sauvegarder_amenagement)

        self._rects = []
        self._fiche = None

        self.setWindowTitle("PlacardCAD - Conception de placards")
        icon_path = os.path.join(os.path.dirname(__file__), "..", "resources", "icon_256.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.resize(1400, 900)
        self._init_ui()
        self._init_toolbar()
        self._init_statusbar()

    def _init_ui(self):
        """Initialise l'interface utilisateur.

        Cree le splitter principal avec trois panneaux :
        arbre projets, editeurs (schema/parametres/pieces manuelles)
        et viewer 2D.
        """
        # Splitter principal : gauche (arbre) | centre (editeurs) | droite (viewer)
        self.splitter_main = QSplitter(Qt.Horizontal)
        self.setCentralWidget(self.splitter_main)

        # --- Panneau gauche : arbre projets ---
        self.project_panel = ProjectPanel(self.db)
        self.project_panel.setMinimumWidth(220)
        self.project_panel.setMaximumWidth(400)
        self.project_panel.amenagement_selectionne.connect(self._on_amenagement_selectionne)
        self.project_panel.projet_selectionne.connect(self._on_projet_selectionne)
        self.project_panel.pieces_manuelles_selectionnees.connect(
            self._on_pieces_manuelles_selectionnees
        )
        self.splitter_main.addWidget(self.project_panel)

        # --- Panneau centre : stacked widget (editeurs / pieces manuelles) ---
        centre_widget = QWidget()
        centre_layout = QVBoxLayout(centre_widget)
        centre_layout.setContentsMargins(0, 0, 0, 0)

        self.stacked_centre = QStackedWidget()

        # Page 0 : Editeurs schema + parametres (amenagement)
        self.schema_editor = SchemaEditor()
        self.schema_editor.schema_modifie.connect(self._on_schema_modifie)

        self.params_editor = ParamsEditor(db=self.db)
        self.params_editor.params_modifies.connect(self._on_params_modifies)

        self.tabs_editeurs = QTabWidget()
        self.tabs_editeurs.addTab(self.schema_editor, "Schema")
        self.tabs_editeurs.addTab(self.params_editor, "Parametres")
        self.stacked_centre.addWidget(self.tabs_editeurs)  # index 0

        # Page 1 : Editeur pieces manuelles (tableur)
        self.pieces_editor = PiecesManualesEditor(self.db)
        self.pieces_editor.donnees_modifiees.connect(self._on_pieces_manuelles_modifiees)
        self.stacked_centre.addWidget(self.pieces_editor)  # index 1

        centre_layout.addWidget(self.stacked_centre)
        self.splitter_main.addWidget(centre_widget)

        # --- Panneau droite : viewer ---
        viewer_widget = QWidget()
        viewer_layout = QVBoxLayout(viewer_widget)
        viewer_layout.setContentsMargins(0, 0, 0, 0)

        viewer_label = QLabel("Vue de face")
        viewer_label.setStyleSheet("font-weight: bold; padding: 4px;")
        viewer_layout.addWidget(viewer_label)

        self.viewer = PlacardViewer()
        viewer_layout.addWidget(self.viewer)

        self.splitter_main.addWidget(viewer_widget)

        # Proportions du splitter
        self.splitter_main.setStretchFactor(0, 1)  # arbre
        self.splitter_main.setStretchFactor(1, 2)  # editeurs
        self.splitter_main.setStretchFactor(2, 3)  # viewer

    def _init_toolbar(self):
        """Initialise la barre d'outils avec les actions principales.

        Ajoute les boutons pour la creation de projets/amenagements,
        l'actualisation de la vue, les exports et l'optimisation de debit.
        """
        toolbar = QToolBar("Actions")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Nouveau projet
        self.action_new_projet = QAction("Nouveau projet", self)
        self.action_new_projet.triggered.connect(self.project_panel._nouveau_projet)
        toolbar.addAction(self.action_new_projet)

        # Nouvel amenagement
        self.action_new_amenagement = QAction("Nouvel amenagement", self)
        self.action_new_amenagement.triggered.connect(self.project_panel._nouvel_amenagement)
        toolbar.addAction(self.action_new_amenagement)

        toolbar.addSeparator()

        # Selecteur de mode Placard / Meuble
        mode_label = QLabel(" Mode: ")
        toolbar.addWidget(mode_label)
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Placard", "Meuble"])
        self.combo_mode.setToolTip("Choisir le type: Placard ou Meuble")
        self.combo_mode.currentTextChanged.connect(self._on_mode_change)
        toolbar.addWidget(self.combo_mode)

        # Bouton template
        self.action_template = QAction("Inserer modele", self)
        self.action_template.setToolTip("Inserer un schema exemple dans l'editeur")
        self.action_template.triggered.connect(self._inserer_template)
        toolbar.addAction(self.action_template)

        toolbar.addSeparator()

        # Regenerer
        self.action_regenerer = QAction("Actualiser vue", self)
        self.action_regenerer.triggered.connect(self._regenerer_vue)
        toolbar.addAction(self.action_regenerer)

        toolbar.addSeparator()

        # Apercu PDF
        self.action_apercu_pdf = QAction("Apercu PDF", self)
        self.action_apercu_pdf.triggered.connect(self._apercu_pdf)
        toolbar.addAction(self.action_apercu_pdf)

        # Export PDF
        self.action_export_pdf = QAction("Exporter PDF", self)
        self.action_export_pdf.triggered.connect(self._exporter_pdf)
        toolbar.addAction(self.action_export_pdf)

        # Export PDF projet complet
        self.action_export_pdf_projet = QAction("Exporter PDF projet", self)
        self.action_export_pdf_projet.triggered.connect(self._exporter_pdf_projet)
        toolbar.addAction(self.action_export_pdf_projet)

        # Export fiche texte
        self.action_export_texte = QAction("Exporter fiche texte", self)
        self.action_export_texte.triggered.connect(self._exporter_fiche_texte)
        toolbar.addAction(self.action_export_texte)

        # Export FreeCAD
        self.action_export_freecad = QAction("Exporter FreeCAD", self)
        self.action_export_freecad.triggered.connect(self._exporter_freecad)
        toolbar.addAction(self.action_export_freecad)

        # Export DXF
        self.action_export_dxf = QAction("Exporter DXF", self)
        self.action_export_dxf.triggered.connect(self._exporter_dxf)
        toolbar.addAction(self.action_export_dxf)

        # Etiquettes
        self.action_etiquettes = QAction("Etiquettes", self)
        self.action_etiquettes.triggered.connect(self._exporter_etiquettes)
        toolbar.addAction(self.action_etiquettes)

        # Liste de courses
        self.action_liste_courses = QAction("Liste de courses", self)
        self.action_liste_courses.triggered.connect(self._exporter_liste_courses)
        toolbar.addAction(self.action_liste_courses)

        toolbar.addSeparator()

        # Optimisation debit
        self.action_optim_debit = QAction("Optimisation debit", self)
        self.action_optim_debit.triggered.connect(self._ouvrir_debit_dialog)
        toolbar.addAction(self.action_optim_debit)

    def _init_statusbar(self):
        """Initialise la barre de statut en bas de la fenetre."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Pret. Creez ou selectionnez un projet pour commencer.")

    # =====================================================================
    #  SLOTS
    # =====================================================================

    def _on_projet_selectionne(self, projet_id: int):
        """Slot appele lorsqu'un projet est selectionne dans l'arbre.

        Args:
            projet_id: Identifiant du projet selectionne.
        """
        self._current_projet_id = projet_id
        self._current_amenagement_id = None
        projet = self.db.get_projet(projet_id)
        if projet:
            self.statusbar.showMessage(f"Projet: {projet['nom']}")

    def _on_amenagement_selectionne(self, projet_id: int, amenagement_id: int):
        """Slot appele lorsqu'un amenagement est selectionne dans l'arbre.

        Bascule le panneau central sur les editeurs schema/parametres
        et charge l'amenagement.

        Args:
            projet_id: Identifiant du projet parent.
            amenagement_id: Identifiant de l'amenagement selectionne.
        """
        self._current_projet_id = projet_id
        self._current_amenagement_id = amenagement_id
        # Basculer sur les editeurs schema/params
        self.stacked_centre.setCurrentIndex(0)
        self._charger_amenagement(amenagement_id)

    def _on_pieces_manuelles_selectionnees(self, projet_id: int):
        """Affiche l'editeur de pieces manuelles dans le panneau central.

        Bascule le stacked widget sur la page de l'editeur tableur
        de pieces manuelles.

        Args:
            projet_id: Identifiant du projet dont on edite les pieces.
        """
        self._current_projet_id = projet_id
        self._current_amenagement_id = None
        # Basculer sur l'editeur de pieces manuelles
        self.pieces_editor.set_projet(projet_id)
        self.stacked_centre.setCurrentIndex(1)
        projet = self.db.get_projet(projet_id)
        nom = projet["nom"] if projet else "?"
        self.statusbar.showMessage(f"Pieces manuelles — {nom}")

    def _on_pieces_manuelles_modifiees(self):
        """Rafraichit l'arbre des projets quand les pieces manuelles changent.

        Slot connecte au signal donnees_modifiees du PiecesManualesEditor.
        """
        self.project_panel.rafraichir()

    def _charger_amenagement(self, amenagement_id: int):
        """Charge un amenagement dans les editeurs schema et parametres.

        Recupere les donnees depuis la base, met a jour l'editeur de schema
        et l'editeur de parametres, puis regenere la vue.

        Args:
            amenagement_id: Identifiant de l'amenagement a charger.
        """
        am = self.db.get_amenagement(amenagement_id)
        if not am:
            return

        # Charger le schema
        self.schema_editor.set_schema(am["schema_txt"])

        # Charger les parametres
        try:
            params = json.loads(am["params_json"]) if am["params_json"] else dict(PARAMS_DEFAUT)
        except json.JSONDecodeError:
            params = dict(PARAMS_DEFAUT)
        self.params_editor.set_params(params)

        self.statusbar.showMessage(f"Amenagement: {am['nom']}")

        # Synchroniser le combo mode
        self._sync_combo_from_schema()

        # Regenerer la vue
        self._regenerer_vue()

    def _on_schema_modifie(self, schema_text: str):
        """Slot appele quand le schema compact est modifie.

        Demarre le timer de sauvegarde automatique et regenere la vue.

        Args:
            schema_text: Nouveau texte du schema compact.
        """
        self._auto_save_timer.start()
        self._regenerer_vue()

    def _on_params_modifies(self, params: dict):
        """Slot appele quand les parametres generaux sont modifies.

        Demarre le timer de sauvegarde automatique et regenere la vue.

        Args:
            params: Dictionnaire des parametres mis a jour.
        """
        self._auto_save_timer.start()
        self._regenerer_vue()

    def _sauvegarder_amenagement(self):
        """Sauvegarde l'amenagement courant en base de donnees.

        Recupere le schema et les parametres depuis les editeurs
        et met a jour l'enregistrement en base. Ne fait rien si
        aucun amenagement n'est selectionne.
        """
        if self._current_amenagement_id is None:
            return

        schema_txt = self.schema_editor.get_schema()
        params = self.params_editor.get_params()
        params_json = json.dumps(params, ensure_ascii=False)

        self.db.modifier_amenagement(
            self._current_amenagement_id,
            schema_txt=schema_txt,
            params_json=params_json,
        )
        self.statusbar.showMessage("Sauvegarde automatique effectuee.", 3000)

    # =====================================================================
    #  MODE PLACARD / MEUBLE
    # =====================================================================

    _TEMPLATE_PLACARD = (
        "*-----------*-----------*-----------*\n"
        "|__________|__________|__________|\n"
        "|__________|__________|__________|\n"
        "|__________|__________|"
    )

    _TEMPLATE_MEUBLE = (
        "#MEUBLE\n"
        "| PP  | TTT |\n"
        "| --  |     |\n"
        "| --  |     |\n"
        "  600   400"
    )

    def _on_mode_change(self, mode: str):
        """Reagit au changement de mode dans le selecteur.

        Met a jour les onglets de parametres et insere un template
        si le schema est vide.
        """
        self.params_editor.set_mode(mode)
        schema = self.schema_editor.get_schema().strip()
        if not schema:
            # Schema vide → inserer le template
            self._inserer_template()

    def _inserer_template(self):
        """Insere un schema modele dans l'editeur selon le mode selectionne."""
        mode = self.combo_mode.currentText()
        if mode == "Meuble":
            self.schema_editor.set_schema(self._TEMPLATE_MEUBLE)
        else:
            self.schema_editor.set_schema(self._TEMPLATE_PLACARD)
        self._regenerer_vue()

    def _sync_combo_from_schema(self):
        """Synchronise le combo mode et les onglets parametres avec le schema."""
        schema = self.schema_editor.get_schema().strip()
        if est_schema_meuble(schema):
            self.combo_mode.blockSignals(True)
            self.combo_mode.setCurrentText("Meuble")
            self.combo_mode.blockSignals(False)
            self.params_editor.set_mode("Meuble")
        elif schema:
            self.combo_mode.blockSignals(True)
            self.combo_mode.setCurrentText("Placard")
            self.combo_mode.blockSignals(False)
            self.params_editor.set_mode("Placard")

    # =====================================================================
    #  GENERATION VUE
    # =====================================================================

    def _regenerer_vue(self):
        """Regenere la vue de face depuis le schema et les parametres courants.

        Detecte automatiquement le type de schema (placard ou meuble)
        grace a l'en-tete ``#MEUBLE`` et utilise le parser/builder adapte.
        """
        schema_text = self.schema_editor.get_schema()
        if not schema_text.strip():
            self.viewer.clear()
            return

        params = self.params_editor.get_params()

        try:
            if est_schema_meuble(schema_text):
                config = meuble_schema_vers_config(schema_text, params)
                self._rects, self._fiche = generer_geometrie_meuble(config)
                type_label = "MEUBLE"
            else:
                config = schema_vers_config(schema_text, params)
                self._rects, self._fiche = generer_geometrie_2d(config)
                type_label = "PLACARD"

            self.viewer.set_geometrie(
                self._rects,
                config["largeur"],
                config["hauteur"]
            )
            self.statusbar.showMessage(
                f"[{type_label}] "
                f"{config['nombre_compartiments']} compartiments | "
                f"{len(self._fiche.pieces)} pieces | "
                f"{len(self._fiche.quincaillerie)} quincailleries"
            )
        except Exception as e:
            self.viewer.clear()
            self.statusbar.showMessage(f"Erreur schema: {e}")

    # =====================================================================
    #  EXPORT
    # =====================================================================

    def _collecter_pieces_projet(self) -> list:
        """Collecte les pieces de tous les amenagements et pieces manuelles du projet.

        Parcourt tous les amenagements du projet courant, genere leurs fiches
        de debit, puis ajoute les pieces manuelles.

        Returns:
            Liste de PieceDebit pour l'ensemble du projet. Liste vide si
            aucun projet n'est selectionne.
        """
        if not self._current_projet_id:
            return []

        all_pieces = []

        # Pieces des amenagements
        amenagements = self.db.lister_amenagements(self._current_projet_id)
        for am in amenagements:
            schema_txt = am["schema_txt"]
            if not schema_txt or not schema_txt.strip():
                continue
            try:
                params_json = am["params_json"]
                params = json.loads(params_json) if params_json else dict(PARAMS_DEFAUT)
            except json.JSONDecodeError:
                params = dict(PARAMS_DEFAUT)
            try:
                config = schema_vers_config(schema_txt, params)
                _, fiche = generer_geometrie_2d(config)
                for i, p in enumerate(fiche.pieces, 1):
                    p.reference = f"P{self._current_projet_id}/A{am['id']}/N{i:02d}"
                am_pieces = pieces_depuis_fiche(
                    fiche, self._current_projet_id, am["id"]
                )
                all_pieces.extend(am_pieces)
            except Exception:
                continue

        # Pieces manuelles
        all_pieces.extend(
            self._collecter_pieces_manuelles(self._current_projet_id)
        )

        return all_pieces

    def _collecter_pieces_manuelles(self, projet_id: int) -> list[PieceDebit]:
        """Convertit les pieces manuelles du projet en objets PieceDebit.

        Args:
            projet_id: Identifiant du projet.

        Returns:
            Liste de PieceDebit correspondant aux pieces manuelles du projet.
        """
        pieces_m = self.db.lister_pieces_manuelles(projet_id)
        result = []
        for pm in pieces_m:
            ref = pm["reference"] or f"P{projet_id}/M{pm['id']:02d}"
            result.append(PieceDebit(
                nom=pm["nom"] or "Piece manuelle",
                reference=ref,
                longueur=pm["longueur"],
                largeur=pm["largeur"],
                epaisseur=pm["epaisseur"],
                couleur=pm["couleur"] or "Standard",
                quantite=pm["quantite"],
                sens_fil=bool(pm["sens_fil"]),
            ))
        return result

    def _get_params_debit(self) -> ParametresDebit:
        """Construit les parametres de debit depuis l'onglet Debit de l'editeur.

        Lit les valeurs de l'onglet Debit dans l'editeur de parametres
        et retourne un objet ParametresDebit avec des valeurs par defaut
        si certaines cles sont absentes.

        Returns:
            Objet ParametresDebit configure selon les parametres courants.
        """
        params = self.params_editor.get_params()
        debit = params.get("debit", {})
        return ParametresDebit(
            panneau_longueur=debit.get("panneau_longueur", 2800),
            panneau_largeur=debit.get("panneau_largeur", 2070),
            trait_scie=debit.get("trait_scie", 4.0),
            surcote=debit.get("surcote", 2.0),
            delignage=debit.get("delignage", 10.0),
            sens_fil=debit.get("sens_fil", True),
        )

    def _apercu_pdf(self):
        """Genere un PDF temporaire et l'ouvre dans le lecteur PDF du systeme.

        Cree un fichier temporaire PDF avec la vue de face, la fiche de debit
        et les informations du projet, puis l'ouvre avec le lecteur par defaut
        du systeme (xdg-open, open ou startfile selon la plateforme).
        """
        if not self._rects:
            QMessageBox.warning(self, "Apercu PDF",
                                "Aucun amenagement a afficher. Editez un schema d'abord.")
            return

        schema_text = self.schema_editor.get_schema()
        params = self.params_editor.get_params()
        config = schema_vers_config(schema_text, params)

        projet_info = None
        if self._current_projet_id:
            projet_info = self.db.get_projet(self._current_projet_id)

        all_pieces = self._collecter_pieces_projet()
        pieces_m = (self._collecter_pieces_manuelles(self._current_projet_id)
                    if self._current_projet_id else [])

        try:
            tmp = tempfile.NamedTemporaryFile(
                suffix=".pdf", prefix="placardcad_apercu_", delete=False
            )
            tmp_path = tmp.name
            tmp.close()

            exporter_pdf(tmp_path, self._rects, config, self._fiche, projet_info,
                         projet_id=self._current_projet_id or 0,
                         amenagement_id=self._current_amenagement_id or 0,
                         params_debit=self._get_params_debit(),
                         all_pieces_projet=all_pieces if all_pieces else None,
                         pieces_manuelles=pieces_m if pieces_m else None)

            # Ouvrir avec le lecteur PDF du systeme
            if sys.platform == "win32":
                os.startfile(tmp_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", tmp_path])
            else:
                subprocess.Popen(["xdg-open", tmp_path])

            self.statusbar.showMessage("Apercu PDF ouvert.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur apercu PDF", str(e))

    def _exporter_pdf(self):
        """Exporte le placard courant en PDF avec debit mixte du projet.

        Demande a l'utilisateur un chemin de fichier via un dialogue de
        sauvegarde, puis genere le PDF contenant la vue de face, la fiche
        de debit et le plan de decoupe.
        """
        if not self._rects:
            QMessageBox.warning(self, "Export PDF",
                                "Aucun amenagement a exporter. Editez un schema d'abord.")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Exporter PDF", "placard.pdf", "PDF (*.pdf)"
        )
        if not filepath:
            return

        schema_text = self.schema_editor.get_schema()
        params = self.params_editor.get_params()
        config = schema_vers_config(schema_text, params)

        # Infos projet
        projet_info = None
        if self._current_projet_id:
            projet_info = self.db.get_projet(self._current_projet_id)

        # Collecter toutes les pieces du projet pour debit mixte
        all_pieces = self._collecter_pieces_projet()
        pieces_m = (self._collecter_pieces_manuelles(self._current_projet_id)
                    if self._current_projet_id else [])

        try:
            exporter_pdf(filepath, self._rects, config, self._fiche, projet_info,
                         projet_id=self._current_projet_id or 0,
                         amenagement_id=self._current_amenagement_id or 0,
                         params_debit=self._get_params_debit(),
                         all_pieces_projet=all_pieces if all_pieces else None,
                         pieces_manuelles=pieces_m if pieces_m else None)
            self.statusbar.showMessage(f"PDF exporte: {filepath}")
            QMessageBox.information(self, "Export PDF",
                                    f"PDF exporte avec succes:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur export PDF", str(e))

    def _exporter_pdf_projet(self):
        """Exporte tout le projet en PDF multi-pages.

        Genere un PDF avec une page par amenagement valide du projet,
        incluant les fiches de debit et les pieces manuelles.
        Affiche un avertissement si des amenagements sont ignores en
        raison d'erreurs de schema.
        """
        if not self._current_projet_id:
            QMessageBox.warning(self, "Export PDF projet",
                                "Aucun projet selectionne.")
            return

        amenagements = self.db.lister_amenagements(self._current_projet_id)
        if not amenagements:
            QMessageBox.warning(self, "Export PDF projet",
                                "Le projet ne contient aucun amenagement.")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Exporter PDF projet", "projet.pdf", "PDF (*.pdf)"
        )
        if not filepath:
            return

        projet_info = self.db.get_projet(self._current_projet_id)

        amenagements_data = []
        erreurs = []
        for am in amenagements:
            schema_txt = am["schema_txt"]
            if not schema_txt or not schema_txt.strip():
                continue
            try:
                params_json = am["params_json"]
                params = json.loads(params_json) if params_json else dict(PARAMS_DEFAUT)
            except json.JSONDecodeError:
                params = dict(PARAMS_DEFAUT)

            try:
                config = schema_vers_config(schema_txt, params)
                rects, fiche = generer_geometrie_2d(config)
                amenagements_data.append({
                    "rects": rects,
                    "config": config,
                    "fiche": fiche,
                    "nom": am["nom"],
                    "amenagement_id": am["id"],
                })
            except Exception as e:
                erreurs.append(f"{am['nom']}: {e}")

        if not amenagements_data:
            QMessageBox.warning(self, "Export PDF projet",
                                "Aucun amenagement valide a exporter.")
            return

        try:
            pieces_m = self._collecter_pieces_manuelles(self._current_projet_id)
            exporter_pdf_projet(filepath, amenagements_data, projet_info,
                                self._current_projet_id,
                                params_debit=self._get_params_debit(),
                                pieces_manuelles=pieces_m if pieces_m else None)
            msg = f"PDF projet exporte: {filepath}\n{len(amenagements_data)} page(s)."
            if pieces_m:
                msg += f"\n{len(pieces_m)} piece(s) manuelle(s) incluse(s)."
            if erreurs:
                msg += f"\n\nAmenagements ignores ({len(erreurs)}):\n" + "\n".join(erreurs)
            self.statusbar.showMessage(f"PDF projet exporte: {filepath}")
            QMessageBox.information(self, "Export PDF projet", msg)
        except Exception as e:
            QMessageBox.critical(self, "Erreur export PDF projet", str(e))

    def _exporter_fiche_texte(self):
        """Exporte la fiche de fabrication en fichier texte brut.

        Genere un fichier texte contenant la nomenclature des pieces,
        les dimensions et les quantites de l'amenagement courant.
        """
        if not self._fiche:
            QMessageBox.warning(self, "Export fiche",
                                "Aucun amenagement a exporter.")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Exporter fiche de fabrication",
            "fiche_fabrication.txt", "Texte (*.txt)"
        )
        if not filepath:
            return

        schema_text = self.schema_editor.get_schema()
        params = self.params_editor.get_params()
        config = schema_vers_config(schema_text, params)

        try:
            texte = self._fiche.generer_texte(config)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(texte)
            self.statusbar.showMessage(f"Fiche exportee: {filepath}")
            QMessageBox.information(self, "Export fiche",
                                    f"Fiche exportee:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur export", str(e))

    def _exporter_freecad(self):
        """Exporte le placard en fichier FreeCAD natif (.FCStd).

        Genere un fichier FreeCAD 3D a partir de la configuration courante
        du schema et des parametres. Le fichier peut etre ouvert dans
        FreeCAD pour visualisation et modification.
        """
        if not self._rects:
            QMessageBox.warning(self, "Export FreeCAD",
                                "Aucun amenagement a exporter. Editez un schema d'abord.")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Exporter fichier FreeCAD",
            "placard.FCStd",
            "FreeCAD (*.FCStd);;Tous (*)"
        )
        if not filepath:
            return

        schema_text = self.schema_editor.get_schema()
        params = self.params_editor.get_params()
        config = schema_vers_config(schema_text, params)

        try:
            exporter_freecad(filepath, config)
            self.statusbar.showMessage(f"FreeCAD exporte: {filepath}")
            QMessageBox.information(
                self, "Export FreeCAD",
                f"Fichier FreeCAD exporte:\n{filepath}\n\n"
                "Ouvrir dans FreeCAD puis Ctrl+Shift+R pour recalculer les formes."
            )
        except Exception as e:
            QMessageBox.critical(self, "Erreur export FreeCAD", str(e))

    def _exporter_etiquettes(self):
        """Exporte les etiquettes de pieces en PDF format A4.

        Genere un PDF avec une etiquette par piece de la fiche de
        fabrication, incluant les dimensions et la reference de chaque piece.
        """
        if not self._fiche:
            QMessageBox.warning(self, "Etiquettes",
                                "Aucun amenagement a exporter. Editez un schema d'abord.")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Exporter etiquettes", "etiquettes.pdf", "PDF (*.pdf)"
        )
        if not filepath:
            return

        projet_info = None
        if self._current_projet_id:
            projet_info = self.db.get_projet(self._current_projet_id)

        try:
            exporter_etiquettes(
                filepath, self._fiche,
                projet_id=self._current_projet_id or 0,
                amenagement_id=self._current_amenagement_id or 0,
                projet_info=projet_info,
            )
            self.statusbar.showMessage(f"Etiquettes exportees: {filepath}")
            QMessageBox.information(
                self, "Etiquettes",
                f"Etiquettes exportees:\n{filepath}\n\n"
                f"{sum(p.quantite for p in self._fiche.pieces)} etiquette(s) generee(s)."
            )
        except Exception as e:
            QMessageBox.critical(self, "Erreur etiquettes", str(e))

    def _exporter_liste_courses(self):
        """Exporte la liste de courses du projet en PDF.

        Analyse tous les amenagements du projet pour generer une liste
        consolidee des materiaux a acheter : panneaux bruts, cremailleres,
        taquets et tasseaux.
        """
        if not self._current_projet_id:
            QMessageBox.warning(self, "Liste de courses",
                                "Aucun projet selectionne.")
            return

        amenagements = self.db.lister_amenagements(self._current_projet_id)
        if not amenagements:
            QMessageBox.warning(self, "Liste de courses",
                                "Le projet ne contient aucun amenagement.")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Exporter liste de courses", "liste_courses.pdf", "PDF (*.pdf)"
        )
        if not filepath:
            return

        projet_info = self.db.get_projet(self._current_projet_id)

        amenagements_data = []
        erreurs = []
        for am in amenagements:
            schema_txt = am["schema_txt"]
            if not schema_txt or not schema_txt.strip():
                continue
            try:
                params_json = am["params_json"]
                params = json.loads(params_json) if params_json else dict(PARAMS_DEFAUT)
            except json.JSONDecodeError:
                params = dict(PARAMS_DEFAUT)

            try:
                config = schema_vers_config(schema_txt, params)
                _rects, fiche = generer_geometrie_2d(config)
                amenagements_data.append({
                    "fiche": fiche,
                    "nom": am["nom"],
                    "amenagement_id": am["id"],
                })
            except Exception as e:
                erreurs.append(f"{am['nom']}: {e}")

        if not amenagements_data:
            QMessageBox.warning(self, "Liste de courses",
                                "Aucun amenagement valide dans ce projet.")
            return

        try:
            pieces_m = self._collecter_pieces_manuelles(self._current_projet_id)
            liste = generer_liste_courses(
                amenagements_data,
                params_debit=self._get_params_debit(),
                projet_id=self._current_projet_id,
                pieces_manuelles=pieces_m if pieces_m else None,
            )
            exporter_liste_courses(filepath, liste, projet_info)
            nb_pan = sum(p["quantite"] for p in liste["panneaux_bruts"])
            nb_crem = sum(c["quantite"] for c in liste["cremailleres"])
            nb_taquets = liste.get("taquets", 0)
            nb_tass = sum(t["quantite"] for t in liste["tasseaux"])
            msg = (
                f"Liste de courses exportee:\n{filepath}\n\n"
                f"{len(amenagements_data)} amenagement(s) analyse(s)\n"
                f"{nb_pan} panneau(x) brut(s)\n"
                f"{nb_crem} cremaillere(s)\n"
                f"{nb_taquets} taquet(s)\n"
                f"{nb_tass} tasseau(x)"
            )
            if erreurs:
                msg += f"\n\nAmenagements ignores ({len(erreurs)}):\n" + "\n".join(erreurs)
            self.statusbar.showMessage(f"Liste de courses exportee: {filepath}")
            QMessageBox.information(self, "Liste de courses", msg)
        except Exception as e:
            QMessageBox.critical(self, "Erreur liste de courses", str(e))

    def _exporter_dxf(self):
        """Exporte le placard en fichier DXF pour plan 2D.

        Genere un fichier DXF compatible avec AutoCAD, LibreCAD et
        FreeCAD a partir de la geometrie et de la fiche de l'amenagement courant.
        """
        if not self._rects:
            QMessageBox.warning(self, "Export DXF",
                                "Aucun amenagement a exporter. Editez un schema d'abord.")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Exporter DXF", "placard.dxf", "DXF (*.dxf)"
        )
        if not filepath:
            return

        schema_text = self.schema_editor.get_schema()
        params = self.params_editor.get_params()
        config = schema_vers_config(schema_text, params)

        try:
            exporter_dxf(filepath, self._rects, config, self._fiche)
            self.statusbar.showMessage(f"DXF exporte: {filepath}")
            QMessageBox.information(
                self, "Export DXF",
                f"Fichier DXF exporte:\n{filepath}\n\n"
                "Compatible AutoCAD, LibreCAD, FreeCAD, etc."
            )
        except Exception as e:
            QMessageBox.critical(self, "Erreur export DXF", str(e))

    def _ouvrir_debit_dialog(self):
        """Ouvre le dialogue modal d'optimisation de debit multi-projets.

        Cree et affiche un DebitDialog permettant de selectionner des
        amenagements a travers plusieurs projets et de lancer l'optimisation
        de decoupe.
        """
        dialog = DebitDialog(self.db, parent=self)
        dialog.exec_()

    def closeEvent(self, event):
        """Sauvegarde les donnees avant fermeture de la fenetre.

        Sauvegarde l'amenagement courant et les pieces manuelles,
        puis ferme la connexion a la base de donnees.

        Args:
            event: Evenement de fermeture Qt.
        """
        self._sauvegarder_amenagement()
        self.pieces_editor.sauvegarder_maintenant()
        self.db.close()
        event.accept()
