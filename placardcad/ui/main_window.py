"""
Fenetre principale de PlacardCAD.
"""

import json
import os

from PyQt5.QtWidgets import (
    QMainWindow, QSplitter, QWidget, QVBoxLayout, QHBoxLayout,
    QAction, QToolBar, QStatusBar, QFileDialog, QMessageBox,
    QLabel, QTabWidget, QStackedWidget
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from .project_panel import ProjectPanel
from .schema_editor import SchemaEditor
from .params_editor import ParamsEditor
from .viewer_3d import PlacardViewer
from .debit_dialog import DebitDialog
from .pieces_manuelles_editor import PiecesManualesEditor

from ..database import Database, PARAMS_DEFAUT
from ..schema_parser import schema_vers_config
from ..placard_builder import generer_geometrie_2d
from ..pdf_export import exporter_pdf, exporter_pdf_projet
from ..optimisation_debit import pieces_depuis_fiche, PieceDebit


class MainWindow(QMainWindow):
    """Fenetre principale de l'application PlacardCAD."""

    def __init__(self, db: Database, parent=None):
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
        self.resize(1400, 900)
        self._init_ui()
        self._init_toolbar()
        self._init_statusbar()

    def _init_ui(self):
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

        # Regenerer
        self.action_regenerer = QAction("Actualiser vue", self)
        self.action_regenerer.triggered.connect(self._regenerer_vue)
        toolbar.addAction(self.action_regenerer)

        toolbar.addSeparator()

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

        toolbar.addSeparator()

        # Optimisation debit
        self.action_optim_debit = QAction("Optimisation debit", self)
        self.action_optim_debit.triggered.connect(self._ouvrir_debit_dialog)
        toolbar.addAction(self.action_optim_debit)

    def _init_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Pret. Creez ou selectionnez un projet pour commencer.")

    # =====================================================================
    #  SLOTS
    # =====================================================================

    def _on_projet_selectionne(self, projet_id: int):
        self._current_projet_id = projet_id
        self._current_amenagement_id = None
        projet = self.db.get_projet(projet_id)
        if projet:
            self.statusbar.showMessage(f"Projet: {projet['nom']}")

    def _on_amenagement_selectionne(self, projet_id: int, amenagement_id: int):
        self._current_projet_id = projet_id
        self._current_amenagement_id = amenagement_id
        # Basculer sur les editeurs schema/params
        self.stacked_centre.setCurrentIndex(0)
        self._charger_amenagement(amenagement_id)

    def _on_pieces_manuelles_selectionnees(self, projet_id: int):
        """Affiche l'editeur de pieces manuelles dans le panneau central."""
        self._current_projet_id = projet_id
        self._current_amenagement_id = None
        # Basculer sur l'editeur de pieces manuelles
        self.pieces_editor.set_projet(projet_id)
        self.stacked_centre.setCurrentIndex(1)
        projet = self.db.get_projet(projet_id)
        nom = projet["nom"] if projet else "?"
        self.statusbar.showMessage(f"Pieces manuelles — {nom}")

    def _on_pieces_manuelles_modifiees(self):
        """Rafraichit l'arbre quand les pieces manuelles changent."""
        self.project_panel.rafraichir()

    def _charger_amenagement(self, amenagement_id: int):
        """Charge un amenagement dans les editeurs."""
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

        # Regenerer la vue
        self._regenerer_vue()

    def _on_schema_modifie(self, schema_text: str):
        """Appele quand le schema est modifie."""
        self._auto_save_timer.start()
        self._regenerer_vue()

    def _on_params_modifies(self, params: dict):
        """Appele quand les parametres sont modifies."""
        self._auto_save_timer.start()
        self._regenerer_vue()

    def _sauvegarder_amenagement(self):
        """Sauvegarde l'amenagement courant en base."""
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
    #  GENERATION VUE
    # =====================================================================

    def _regenerer_vue(self):
        """Regenere la vue de face depuis le schema et les parametres courants."""
        schema_text = self.schema_editor.get_schema()
        if not schema_text.strip():
            self.viewer.clear()
            return

        params = self.params_editor.get_params()

        try:
            config = schema_vers_config(schema_text, params)
            self._rects, self._fiche = generer_geometrie_2d(config)
            self.viewer.set_geometrie(
                self._rects,
                config["largeur"],
                config["hauteur"]
            )
            self.statusbar.showMessage(
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
        """Collecte les pieces de tous les amenagements + pieces manuelles du projet."""
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
        """Convertit les pieces manuelles du projet en PieceDebit."""
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

    def _exporter_pdf(self):
        """Exporte le placard en PDF avec debit mixte du projet."""
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
                         all_pieces_projet=all_pieces if all_pieces else None,
                         pieces_manuelles=pieces_m if pieces_m else None)
            self.statusbar.showMessage(f"PDF exporte: {filepath}")
            QMessageBox.information(self, "Export PDF",
                                    f"PDF exporte avec succes:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur export PDF", str(e))

    def _exporter_pdf_projet(self):
        """Exporte tout le projet en PDF (une page par amenagement)."""
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
        """Exporte la fiche de fabrication en texte."""
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

    def _ouvrir_debit_dialog(self):
        """Ouvre le dialogue d'optimisation de debit multi-projets."""
        dialog = DebitDialog(self.db, parent=self)
        dialog.exec_()

    def closeEvent(self, event):
        """Sauvegarde avant fermeture."""
        self._sauvegarder_amenagement()
        self.pieces_editor.sauvegarder_maintenant()
        self.db.close()
        event.accept()
