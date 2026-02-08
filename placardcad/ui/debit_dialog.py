"""
Dialogue d'optimisation de debit multi-projets/amenagements.

Permet de selectionner des amenagements a travers plusieurs projets,
configurer les parametres de decoupe, et exporter le plan de debit en PDF.
"""

import json

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QTreeWidget, QTreeWidgetItem, QPushButton, QSpinBox, QDoubleSpinBox,
    QCheckBox, QFileDialog, QMessageBox, QLabel,
)
from PyQt5.QtCore import Qt

from ..database import Database, PARAMS_DEFAUT
from ..schema_parser import schema_vers_config
from ..placard_builder import generer_geometrie_2d
from ..optimisation_debit import (
    ParametresDebit, PieceDebit, pieces_depuis_fiche,
    PANNEAU_STD_LONGUEUR, PANNEAU_STD_LARGEUR,
)
from ..pdf_export import exporter_pdf_debit


class DebitDialog(QDialog):
    """Dialogue pour optimiser le debit de panneaux multi-projets."""

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Optimisation de debit")
        self.resize(700, 550)
        self._init_ui()
        self._charger_arbre()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # --- Arbre de selection ---
        grp_select = QGroupBox("Selection des amenagements et pieces")
        select_layout = QVBoxLayout(grp_select)

        btn_bar = QHBoxLayout()
        btn_tout = QPushButton("Tout cocher")
        btn_tout.clicked.connect(self._tout_cocher)
        btn_rien = QPushButton("Tout decocher")
        btn_rien.clicked.connect(self._tout_decocher)
        btn_bar.addWidget(btn_tout)
        btn_bar.addWidget(btn_rien)
        btn_bar.addStretch()
        select_layout.addLayout(btn_bar)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Projet / Amenagement", "Schema"])
        self.tree.setColumnWidth(0, 350)
        select_layout.addWidget(self.tree)
        layout.addWidget(grp_select)

        # --- Parametres de decoupe ---
        grp_params = QGroupBox("Parametres de decoupe")
        params_layout = QFormLayout(grp_params)

        self.spin_panneau_l = QSpinBox()
        self.spin_panneau_l.setRange(1000, 5000)
        self.spin_panneau_l.setValue(PANNEAU_STD_LONGUEUR)
        self.spin_panneau_l.setSuffix(" mm")
        params_layout.addRow("Panneau longueur:", self.spin_panneau_l)

        self.spin_panneau_w = QSpinBox()
        self.spin_panneau_w.setRange(500, 3000)
        self.spin_panneau_w.setValue(PANNEAU_STD_LARGEUR)
        self.spin_panneau_w.setSuffix(" mm")
        params_layout.addRow("Panneau largeur:", self.spin_panneau_w)

        self.spin_trait = QDoubleSpinBox()
        self.spin_trait.setRange(0, 10)
        self.spin_trait.setValue(4.0)
        self.spin_trait.setSuffix(" mm")
        self.spin_trait.setDecimals(1)
        params_layout.addRow("Trait de scie:", self.spin_trait)

        self.spin_surcote = QDoubleSpinBox()
        self.spin_surcote.setRange(0, 10)
        self.spin_surcote.setValue(2.0)
        self.spin_surcote.setSuffix(" mm")
        self.spin_surcote.setDecimals(1)
        params_layout.addRow("Surcote (par cote):", self.spin_surcote)

        self.spin_delignage = QDoubleSpinBox()
        self.spin_delignage.setRange(0, 30)
        self.spin_delignage.setValue(10.0)
        self.spin_delignage.setSuffix(" mm")
        self.spin_delignage.setDecimals(1)
        params_layout.addRow("Delignage:", self.spin_delignage)

        self.chk_sens_fil = QCheckBox("Respecter le sens du fil (pas de rotation)")
        self.chk_sens_fil.setChecked(True)
        params_layout.addRow(self.chk_sens_fil)

        layout.addWidget(grp_params)

        # --- Boutons ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_exporter = QPushButton("Optimiser et exporter PDF")
        self.btn_exporter.setStyleSheet("font-weight: bold; padding: 8px 16px;")
        self.btn_exporter.clicked.connect(self._optimiser_et_exporter)
        btn_layout.addWidget(self.btn_exporter)

        btn_fermer = QPushButton("Fermer")
        btn_fermer.clicked.connect(self.reject)
        btn_layout.addWidget(btn_fermer)

        layout.addLayout(btn_layout)

    def _charger_arbre(self):
        """Charge les projets et amenagements dans l'arbre."""
        self.tree.clear()
        projets = self.db.lister_projets()

        for projet in projets:
            item_projet = QTreeWidgetItem([
                f"{projet['nom']} ({projet['client']})" if projet['client']
                else projet['nom'],
                ""
            ])
            item_projet.setFlags(item_projet.flags() | Qt.ItemIsUserCheckable)
            item_projet.setCheckState(0, Qt.Unchecked)
            item_projet.setData(0, Qt.UserRole, ("projet", projet["id"]))

            amenagements = self.db.lister_amenagements(projet["id"])
            for am in amenagements:
                schema_preview = (am["schema_txt"] or "")[:40].replace("\n", " ")
                item_am = QTreeWidgetItem([am["nom"], schema_preview])
                item_am.setFlags(item_am.flags() | Qt.ItemIsUserCheckable)
                item_am.setCheckState(0, Qt.Unchecked)
                item_am.setData(0, Qt.UserRole, ("amenagement", am["id"], projet["id"]))
                item_projet.addChild(item_am)

            # Noeud pieces manuelles
            pieces_m = self.db.lister_pieces_manuelles(projet["id"])
            nb = len(pieces_m)
            if nb > 0:
                label = f"Pieces manuelles ({nb})"
                nb_pcs = sum(pm["quantite"] for pm in pieces_m)
                item_pm = QTreeWidgetItem([label, f"{nb_pcs} pcs"])
                item_pm.setFlags(item_pm.flags() | Qt.ItemIsUserCheckable)
                item_pm.setCheckState(0, Qt.Unchecked)
                item_pm.setData(0, Qt.UserRole, ("pieces_manuelles", projet["id"]))
                font = item_pm.font(0)
                font.setItalic(True)
                item_pm.setFont(0, font)
                item_projet.addChild(item_pm)

            self.tree.addTopLevelItem(item_projet)

        self.tree.expandAll()
        self.tree.itemChanged.connect(self._on_item_changed)

    def _on_item_changed(self, item: QTreeWidgetItem, column: int):
        """Propage le check du projet vers ses enfants."""
        data = item.data(0, Qt.UserRole)
        if not data or data[0] != "projet":
            return
        state = item.checkState(0)
        self.tree.blockSignals(True)
        for i in range(item.childCount()):
            item.child(i).setCheckState(0, state)
        self.tree.blockSignals(False)

    def _tout_cocher(self):
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            item.setCheckState(0, Qt.Checked)
            for j in range(item.childCount()):
                item.child(j).setCheckState(0, Qt.Checked)
        self.tree.blockSignals(False)

    def _tout_decocher(self):
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            item.setCheckState(0, Qt.Unchecked)
            for j in range(item.childCount()):
                item.child(j).setCheckState(0, Qt.Unchecked)
        self.tree.blockSignals(False)

    def _get_params_debit(self) -> ParametresDebit:
        """Lit les parametres depuis les widgets."""
        return ParametresDebit(
            trait_scie=self.spin_trait.value(),
            surcote=self.spin_surcote.value(),
            delignage=self.spin_delignage.value(),
            panneau_longueur=self.spin_panneau_l.value(),
            panneau_largeur=self.spin_panneau_w.value(),
            sens_fil=self.chk_sens_fil.isChecked(),
        )

    def _collecter_pieces(self) -> tuple[list[PieceDebit], dict | None]:
        """Collecte toutes les pieces des amenagements et pieces manuelles coches."""
        all_pieces: list[PieceDebit] = []
        projet_info = None
        erreurs = []

        for i in range(self.tree.topLevelItemCount()):
            item_projet = self.tree.topLevelItem(i)
            data_projet = item_projet.data(0, Qt.UserRole)
            projet_id = data_projet[1]

            for j in range(item_projet.childCount()):
                item_child = item_projet.child(j)
                if item_child.checkState(0) != Qt.Checked:
                    continue

                data_child = item_child.data(0, Qt.UserRole)

                if data_child[0] == "amenagement":
                    am_id = data_child[1]
                    am = self.db.get_amenagement(am_id)
                    if not am or not am["schema_txt"] or not am["schema_txt"].strip():
                        continue

                    if projet_info is None:
                        projet_info = self.db.get_projet(projet_id)

                    try:
                        params_json = am["params_json"]
                        params = json.loads(params_json) if params_json else dict(PARAMS_DEFAUT)
                    except json.JSONDecodeError:
                        params = dict(PARAMS_DEFAUT)

                    try:
                        config = schema_vers_config(am["schema_txt"], params)
                        _, fiche = generer_geometrie_2d(config)
                        pieces = pieces_depuis_fiche(fiche, projet_id, am_id)
                        all_pieces.extend(pieces)
                    except Exception as e:
                        erreurs.append(f"{am['nom']}: {e}")

                elif data_child[0] == "pieces_manuelles":
                    pid = data_child[1]
                    if projet_info is None:
                        projet_info = self.db.get_projet(pid)

                    pieces_m = self.db.lister_pieces_manuelles(pid)
                    for pm in pieces_m:
                        ref = pm["reference"] or f"P{pid}/M{pm['id']:02d}"
                        all_pieces.append(PieceDebit(
                            nom=pm["nom"] or "Piece manuelle",
                            reference=ref,
                            longueur=pm["longueur"],
                            largeur=pm["largeur"],
                            epaisseur=pm["epaisseur"],
                            couleur=pm["couleur"] or "Standard",
                            quantite=pm["quantite"],
                            sens_fil=bool(pm["sens_fil"]),
                        ))

        if erreurs:
            QMessageBox.warning(
                self, "Avertissement",
                f"Amenagements ignores ({len(erreurs)}):\n" + "\n".join(erreurs)
            )

        return all_pieces, projet_info

    def _optimiser_et_exporter(self):
        """Lance l'optimisation et exporte le PDF."""
        all_pieces, projet_info = self._collecter_pieces()

        if not all_pieces:
            QMessageBox.warning(self, "Optimisation",
                                "Aucune piece a optimiser.\n"
                                "Cochez au moins un amenagement ou des pieces manuelles.")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Exporter plan de debit", "plan_debit.pdf", "PDF (*.pdf)"
        )
        if not filepath:
            return

        params = self._get_params_debit()

        try:
            exporter_pdf_debit(
                filepath, all_pieces, params, projet_info,
                titre="Optimisation de debit"
            )
            QMessageBox.information(
                self, "Export reussi",
                f"Plan de debit exporte:\n{filepath}\n\n"
                f"{len(all_pieces)} pieces traitees."
            )
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))
