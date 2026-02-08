"""
Dialogue de gestion des pieces manuelles d'un projet.

Permet d'ajouter, editer, supprimer des pieces complementaires
et de les importer depuis un fichier CSV.
"""

import csv
import io

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QFileDialog, QMessageBox, QLabel,
    QAbstractItemView, QWidget,
)
from PyQt5.QtCore import Qt

from ..database import Database

# Colonnes du tableau
COLONNES = [
    ("Nom", 180),
    ("Reference", 90),
    ("Longueur", 75),
    ("Largeur", 75),
    ("Epaisseur", 75),
    ("Couleur / Decor", 140),
    ("Fil", 40),
    ("Quantite", 65),
]

# Entetes CSV attendues (pour l'import)
CSV_CHAMPS = ["nom", "reference", "longueur", "largeur", "epaisseur",
              "couleur", "sens_fil", "quantite"]


class PiecesManualesDialog(QDialog):
    """Dialogue d'edition des pieces manuelles d'un projet."""

    def __init__(self, db: Database, projet_id: int, parent=None):
        super().__init__(parent)
        self.db = db
        self.projet_id = projet_id
        self.setWindowTitle("Pieces manuelles (complementaires)")
        self.resize(820, 500)
        self._init_ui()
        self._charger_pieces()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Info
        projet = self.db.get_projet(self.projet_id)
        nom_projet = projet["nom"] if projet else "?"
        info = QLabel(f"Pieces complementaires du projet : {nom_projet}")
        info.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(info)

        # Tableau
        self.table = QTableWidget(0, len(COLONNES))
        headers = [c[0] for c in COLONNES]
        self.table.setHorizontalHeaderLabels(headers)
        for i, (_, w) in enumerate(COLONNES):
            self.table.setColumnWidth(i, w)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # Boutons d'action
        btn_layout = QHBoxLayout()

        btn_ajouter = QPushButton("Ajouter une piece")
        btn_ajouter.clicked.connect(self._ajouter_ligne)
        btn_layout.addWidget(btn_ajouter)

        btn_dupliquer = QPushButton("Dupliquer")
        btn_dupliquer.clicked.connect(self._dupliquer_ligne)
        btn_layout.addWidget(btn_dupliquer)

        btn_supprimer = QPushButton("Supprimer")
        btn_supprimer.clicked.connect(self._supprimer_lignes)
        btn_layout.addWidget(btn_supprimer)

        btn_layout.addStretch()

        btn_import = QPushButton("Importer CSV...")
        btn_import.clicked.connect(self._importer_csv)
        btn_layout.addWidget(btn_import)

        btn_export_csv = QPushButton("Exporter CSV...")
        btn_export_csv.clicked.connect(self._exporter_csv)
        btn_layout.addWidget(btn_export_csv)

        layout.addLayout(btn_layout)

        # Boutons bas
        bottom = QHBoxLayout()
        bottom.addStretch()

        lbl_format = QLabel(
            "Format CSV : nom;reference;longueur;largeur;epaisseur;"
            "couleur;sens_fil(0/1);quantite"
        )
        lbl_format.setStyleSheet("color: gray; font-size: 9px;")
        bottom.addWidget(lbl_format)

        bottom.addStretch()

        btn_sauver = QPushButton("Sauvegarder et fermer")
        btn_sauver.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        btn_sauver.clicked.connect(self._sauver_et_fermer)
        bottom.addWidget(btn_sauver)

        btn_annuler = QPushButton("Annuler")
        btn_annuler.clicked.connect(self.reject)
        bottom.addWidget(btn_annuler)

        layout.addLayout(bottom)

    # --- Chargement / Sauvegarde ---

    def _charger_pieces(self):
        """Charge les pieces manuelles depuis la base."""
        pieces = self.db.lister_pieces_manuelles(self.projet_id)
        self.table.setRowCount(0)
        for p in pieces:
            self._ajouter_ligne_donnees(
                p["nom"], p["reference"],
                p["longueur"], p["largeur"], p["epaisseur"],
                p["couleur"], bool(p["sens_fil"]), p["quantite"],
                piece_id=p["id"],
            )

    def _sauver_et_fermer(self):
        """Sauvegarde toutes les pieces en base et ferme."""
        # Supprimer les anciennes
        self.db.supprimer_pieces_manuelles_projet(self.projet_id)

        # Re-inserer depuis le tableau
        for row in range(self.table.rowCount()):
            donnees = self._lire_ligne(row)
            if donnees is None:
                continue
            nom, ref, longueur, largeur, ep, couleur, fil, qte = donnees
            if longueur <= 0 or largeur <= 0:
                continue
            self.db.ajouter_piece_manuelle(
                self.projet_id,
                nom=nom, reference=ref,
                longueur=longueur, largeur=largeur,
                epaisseur=ep, couleur=couleur,
                sens_fil=fil, quantite=qte,
            )
        self.accept()

    # --- Manipulation du tableau ---

    def _ajouter_ligne(self):
        """Ajoute une ligne vide."""
        self._ajouter_ligne_donnees("", "", 0, 0, 19, "", True, 1)
        # Focus sur la premiere cellule de la nouvelle ligne
        row = self.table.rowCount() - 1
        self.table.setCurrentCell(row, 0)
        self.table.editItem(self.table.item(row, 0))

    def _ajouter_ligne_donnees(self, nom: str, reference: str,
                                longueur: float, largeur: float,
                                epaisseur: float, couleur: str,
                                sens_fil: bool, quantite: int,
                                piece_id: int = 0):
        """Ajoute une ligne avec des donnees."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        self.table.setItem(row, 0, QTableWidgetItem(nom))
        self.table.setItem(row, 1, QTableWidgetItem(reference))
        self.table.setItem(row, 2, QTableWidgetItem(
            f"{longueur:.0f}" if longueur else ""))
        self.table.setItem(row, 3, QTableWidgetItem(
            f"{largeur:.0f}" if largeur else ""))
        self.table.setItem(row, 4, QTableWidgetItem(
            f"{epaisseur:.0f}" if epaisseur else "19"))
        self.table.setItem(row, 5, QTableWidgetItem(couleur))

        # Checkbox pour sens du fil
        chk_widget = QWidget()
        chk = QCheckBox()
        chk.setChecked(sens_fil)
        chk_layout = QHBoxLayout(chk_widget)
        chk_layout.addWidget(chk)
        chk_layout.setAlignment(Qt.AlignCenter)
        chk_layout.setContentsMargins(0, 0, 0, 0)
        self.table.setCellWidget(row, 6, chk_widget)

        self.table.setItem(row, 7, QTableWidgetItem(str(quantite)))

    def _dupliquer_ligne(self):
        """Duplique les lignes selectionnees."""
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()))
        if not rows:
            return
        for row in rows:
            donnees = self._lire_ligne(row)
            if donnees:
                nom, ref, l, lg, ep, coul, fil, qte = donnees
                self._ajouter_ligne_donnees(nom, ref, l, lg, ep, coul, fil, qte)

    def _supprimer_lignes(self):
        """Supprime les lignes selectionnees."""
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()),
                      reverse=True)
        if not rows:
            return
        for row in rows:
            self.table.removeRow(row)

    def _lire_ligne(self, row: int):
        """Lit les donnees d'une ligne. Retourne None si invalide."""
        try:
            nom = (self.table.item(row, 0).text().strip()
                   if self.table.item(row, 0) else "")
            ref = (self.table.item(row, 1).text().strip()
                   if self.table.item(row, 1) else "")
            longueur = float(self.table.item(row, 2).text() or 0)
            largeur = float(self.table.item(row, 3).text() or 0)
            epaisseur = float(self.table.item(row, 4).text() or 19)
            couleur = (self.table.item(row, 5).text().strip()
                       if self.table.item(row, 5) else "")

            chk_widget = self.table.cellWidget(row, 6)
            if chk_widget:
                chk = chk_widget.findChild(QCheckBox)
                sens_fil = chk.isChecked() if chk else True
            else:
                sens_fil = True

            quantite = int(self.table.item(row, 7).text() or 1)
            if quantite < 1:
                quantite = 1

            return nom, ref, longueur, largeur, epaisseur, couleur, sens_fil, quantite
        except (ValueError, AttributeError):
            return None

    # --- Import / Export CSV ---

    def _importer_csv(self):
        """Importe des pieces depuis un fichier CSV."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Importer des pieces (CSV)",
            "", "CSV (*.csv);;Texte (*.txt);;Tous (*)"
        )
        if not filepath:
            return

        nb_importees = 0
        nb_erreurs = 0
        erreurs = []

        try:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                contenu = f.read()
        except Exception as e:
            QMessageBox.critical(self, "Erreur lecture", str(e))
            return

        # Detecter le delimiteur
        delimiteur = ";"
        if "\t" in contenu and ";" not in contenu:
            delimiteur = "\t"
        elif "," in contenu and ";" not in contenu:
            delimiteur = ","

        reader = csv.reader(io.StringIO(contenu), delimiter=delimiteur)

        for num_ligne, row in enumerate(reader, 1):
            # Ignorer les lignes vides
            if not row or all(c.strip() == "" for c in row):
                continue

            # Ignorer l'entete si detectee
            if num_ligne == 1 and row[0].strip().lower() in ("nom", "name", "piece"):
                continue

            try:
                nom = row[0].strip() if len(row) > 0 else ""
                ref = row[1].strip() if len(row) > 1 else ""
                longueur = float(row[2].strip()) if len(row) > 2 and row[2].strip() else 0
                largeur = float(row[3].strip()) if len(row) > 3 and row[3].strip() else 0
                epaisseur = float(row[4].strip()) if len(row) > 4 and row[4].strip() else 19
                couleur = row[5].strip() if len(row) > 5 else ""
                sens_fil_str = row[6].strip().lower() if len(row) > 6 else "1"
                sens_fil = sens_fil_str not in ("0", "false", "non", "no", "n")
                quantite = int(row[7].strip()) if len(row) > 7 and row[7].strip() else 1

                if longueur <= 0 or largeur <= 0:
                    erreurs.append(f"Ligne {num_ligne}: dimensions invalides")
                    nb_erreurs += 1
                    continue

                self._ajouter_ligne_donnees(
                    nom, ref, longueur, largeur, epaisseur,
                    couleur, sens_fil, quantite
                )
                nb_importees += 1

            except (ValueError, IndexError) as e:
                erreurs.append(f"Ligne {num_ligne}: {e}")
                nb_erreurs += 1

        msg = f"{nb_importees} piece(s) importee(s)."
        if nb_erreurs > 0:
            msg += f"\n{nb_erreurs} ligne(s) ignoree(s)."
            if erreurs:
                msg += "\n\nDetails:\n" + "\n".join(erreurs[:10])
        QMessageBox.information(self, "Import CSV", msg)

    def _exporter_csv(self):
        """Exporte les pieces du tableau en CSV."""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Exporter les pieces (CSV)",
            "pieces_manuelles.csv", "CSV (*.csv)"
        )
        if not filepath:
            return

        try:
            with open(filepath, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(CSV_CHAMPS)
                for row in range(self.table.rowCount()):
                    donnees = self._lire_ligne(row)
                    if donnees is None:
                        continue
                    nom, ref, l, lg, ep, coul, fil, qte = donnees
                    writer.writerow([
                        nom, ref,
                        f"{l:.0f}", f"{lg:.0f}", f"{ep:.0f}",
                        coul, "1" if fil else "0", qte
                    ])
            QMessageBox.information(
                self, "Export CSV",
                f"Pieces exportees:\n{filepath}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Erreur export", str(e))
