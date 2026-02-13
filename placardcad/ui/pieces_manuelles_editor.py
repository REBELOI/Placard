"""
Widget tableur integre pour gestion des pieces manuelles d'un projet.

Remplace le dialogue modal par un widget integre dans le panneau central,
affiche quand le noeud 'Pieces manuelles' est selectionne dans l'arbre.
Le choix du panneau (couleur + epaisseur) se fait via un QComboBox
alimente par les presets (configurations type) et les parametres par defaut.
"""

import csv
import io

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QComboBox, QFileDialog, QMessageBox, QLabel,
    QAbstractItemView,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal

from ..database import Database, PARAMS_DEFAUT

# Types de panneaux a extraire des presets
_TYPES_PANNEAUX = [
    "panneau_separation", "panneau_rayon",
    "panneau_rayon_haut", "panneau_mur",
]

# Colonnes du tableau
COLONNES = [
    ("Nom", 160),
    ("Reference", 80),
    ("Longueur", 70),
    ("Largeur", 70),
    ("Panneau", 200),
    ("Fil", 40),
    ("Quantite", 60),
]

# Entetes CSV
CSV_CHAMPS = ["nom", "reference", "longueur", "largeur", "epaisseur",
              "couleur", "sens_fil", "quantite"]


class PiecesManualesEditor(QWidget):
    """Widget tableur pour editer les pieces manuelles d'un projet."""

    donnees_modifiees = pyqtSignal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.projet_id = None
        self._panneaux_presets = []  # [(label, couleur, epaisseur, sens_fil)]
        self._loading = False
        self._save_timer = QTimer()
        self._save_timer.setInterval(2000)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._sauvegarder)
        self._init_ui()
        self._actualiser_presets()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Info projet
        self.lbl_info = QLabel("Pieces complementaires")
        self.lbl_info.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(self.lbl_info)

        # Tableau
        self.table = QTableWidget(0, len(COLONNES))
        headers = [c[0] for c in COLONNES]
        self.table.setHorizontalHeaderLabels(headers)
        for i, (_, w) in enumerate(COLONNES):
            self.table.setColumnWidth(i, w)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.cellChanged.connect(self._on_cell_changed)
        layout.addWidget(self.table)

        # Boutons d'action
        btn_layout = QHBoxLayout()

        btn_ajouter = QPushButton("Ajouter")
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

        btn_export = QPushButton("Exporter CSV...")
        btn_export.clicked.connect(self._exporter_csv)
        btn_layout.addWidget(btn_export)

        layout.addLayout(btn_layout)

        # Indication format CSV
        lbl_fmt = QLabel(
            "Format CSV : nom;reference;longueur;largeur;epaisseur;"
            "couleur;sens_fil(0/1);quantite"
        )
        lbl_fmt.setStyleSheet("color: gray; font-size: 9px;")
        layout.addWidget(lbl_fmt)

    # =================================================================
    #  PRESETS PANNEAUX
    # =================================================================

    def _actualiser_presets(self):
        """Reconstruit la liste des panneaux depuis les presets et PARAMS_DEFAUT."""
        seen = set()
        self._panneaux_presets = []

        # Depuis PARAMS_DEFAUT
        for tp in _TYPES_PANNEAUX:
            p = PARAMS_DEFAUT.get(tp, {})
            couleur = p.get("couleur_fab", "Standard")
            ep = p.get("epaisseur", 19)
            fil = p.get("sens_fil", True)
            key = (couleur, ep)
            if key not in seen:
                seen.add(key)
                label = f"{couleur} - {ep:.0f}mm"
                self._panneaux_presets.append((label, couleur, ep, fil))

        # Depuis les configurations sauvegardees
        configs = self.db.lister_configurations()
        for cfg in configs:
            params = cfg.get("params", {})
            for tp in _TYPES_PANNEAUX:
                p = params.get(tp, {})
                if not p:
                    continue
                couleur = p.get("couleur_fab", "")
                ep = p.get("epaisseur", 19)
                fil = p.get("sens_fil", True)
                if not couleur:
                    continue
                key = (couleur, ep)
                if key not in seen:
                    seen.add(key)
                    label = f"{couleur} - {ep:.0f}mm"
                    self._panneaux_presets.append((label, couleur, ep, fil))

    # =================================================================
    #  CHARGEMENT / SAUVEGARDE
    # =================================================================

    def set_projet(self, projet_id: int):
        """Charge les pieces manuelles du projet donne."""
        if self.projet_id is not None and self.projet_id != projet_id:
            self._sauvegarder()

        self.projet_id = projet_id
        self._actualiser_presets()

        projet = self.db.get_projet(projet_id)
        nom = projet["nom"] if projet else "?"
        self.lbl_info.setText(f"Pieces complementaires \u2014 {nom}")

        self._charger_pieces()

    def _charger_pieces(self):
        """Charge les pieces depuis la base de donnees."""
        self._loading = True
        self.table.setRowCount(0)

        if self.projet_id is None:
            self._loading = False
            return

        pieces = self.db.lister_pieces_manuelles(self.projet_id)
        for p in pieces:
            self._ajouter_ligne_donnees(
                p["nom"], p["reference"],
                p["longueur"], p["largeur"],
                p["epaisseur"], p["couleur"],
                bool(p["sens_fil"]), p["quantite"],
            )
        self._loading = False

    def _sauvegarder(self):
        """Sauvegarde toutes les pieces en base."""
        if self.projet_id is None:
            return

        self.db.supprimer_pieces_manuelles_projet(self.projet_id)

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

        self.donnees_modifiees.emit()

    def sauvegarder_maintenant(self):
        """Force la sauvegarde immediate (appele avant fermeture)."""
        self._save_timer.stop()
        self._sauvegarder()

    # =================================================================
    #  CREATION DE WIDGETS CELLULE
    # =================================================================

    def _creer_combo_panneau(self, couleur: str = "", epaisseur: float = 19) -> QComboBox:
        """Cree un QComboBox pour la selection du panneau."""
        combo = QComboBox()
        idx_select = -1

        for i, (label, c, ep, fil) in enumerate(self._panneaux_presets):
            combo.addItem(label, {"couleur": c, "epaisseur": ep, "sens_fil": fil})
            if c == couleur and abs(ep - epaisseur) < 0.5:
                idx_select = i

        # Si le panneau de la piece n'est pas dans les presets, l'ajouter
        if idx_select < 0 and couleur:
            label = f"{couleur} - {epaisseur:.0f}mm"
            combo.addItem(label, {
                "couleur": couleur, "epaisseur": epaisseur, "sens_fil": True
            })
            idx_select = combo.count() - 1

        if idx_select >= 0:
            combo.setCurrentIndex(idx_select)

        combo.currentIndexChanged.connect(self._on_combo_changed)
        return combo

    def _creer_check_fil(self, checked: bool = True) -> QWidget:
        """Cree un widget avec checkbox centree pour le sens du fil."""
        w = QWidget()
        chk = QCheckBox()
        chk.setChecked(checked)
        lay = QHBoxLayout(w)
        lay.addWidget(chk)
        lay.setAlignment(Qt.AlignCenter)
        lay.setContentsMargins(0, 0, 0, 0)
        chk.stateChanged.connect(lambda: self._schedule_save())
        return w

    # =================================================================
    #  MANIPULATION DU TABLEAU
    # =================================================================

    def _ajouter_ligne_donnees(self, nom: str, reference: str,
                                longueur: float, largeur: float,
                                epaisseur: float, couleur: str,
                                sens_fil: bool, quantite: int):
        """Ajoute une ligne avec des donnees."""
        was_loading = self._loading
        self._loading = True

        row = self.table.rowCount()
        self.table.insertRow(row)

        self.table.setItem(row, 0, QTableWidgetItem(nom))
        self.table.setItem(row, 1, QTableWidgetItem(reference))
        self.table.setItem(row, 2, QTableWidgetItem(
            f"{longueur:.0f}" if longueur else ""))
        self.table.setItem(row, 3, QTableWidgetItem(
            f"{largeur:.0f}" if largeur else ""))

        # Panneau combo (col 4)
        combo = self._creer_combo_panneau(couleur, epaisseur)
        self.table.setCellWidget(row, 4, combo)

        # Fil checkbox (col 5)
        chk_w = self._creer_check_fil(sens_fil)
        self.table.setCellWidget(row, 5, chk_w)

        # Quantite (col 6)
        self.table.setItem(row, 6, QTableWidgetItem(str(quantite)))

        self._loading = was_loading

    def _ajouter_ligne(self):
        """Ajoute une ligne vide avec les valeurs par defaut du premier preset."""
        couleur = self._panneaux_presets[0][1] if self._panneaux_presets else ""
        ep = self._panneaux_presets[0][2] if self._panneaux_presets else 19
        self._ajouter_ligne_donnees("", "", 0, 0, ep, couleur, True, 1)
        row = self.table.rowCount() - 1
        self.table.setCurrentCell(row, 0)
        self.table.editItem(self.table.item(row, 0))
        self._schedule_save()

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
        self._schedule_save()

    def _supprimer_lignes(self):
        """Supprime les lignes selectionnees."""
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()),
                      reverse=True)
        if not rows:
            return
        for row in rows:
            self.table.removeRow(row)
        self._schedule_save()

    def _lire_ligne(self, row: int):
        """Lit les donnees d'une ligne. Retourne None si invalide."""
        try:
            nom = (self.table.item(row, 0).text().strip()
                   if self.table.item(row, 0) else "")
            ref = (self.table.item(row, 1).text().strip()
                   if self.table.item(row, 1) else "")
            longueur = float(self.table.item(row, 2).text() or 0)
            largeur = float(self.table.item(row, 3).text() or 0)

            # Panneau combo (col 4)
            combo = self.table.cellWidget(row, 4)
            if combo and isinstance(combo, QComboBox):
                data = combo.currentData()
                couleur = data.get("couleur", "") if data else ""
                epaisseur = data.get("epaisseur", 19) if data else 19
            else:
                couleur = ""
                epaisseur = 19

            # Fil checkbox (col 5)
            chk_widget = self.table.cellWidget(row, 5)
            if chk_widget:
                chk = chk_widget.findChild(QCheckBox)
                sens_fil = chk.isChecked() if chk else True
            else:
                sens_fil = True

            quantite = int(self.table.item(row, 6).text() or 1)
            if quantite < 1:
                quantite = 1

            return nom, ref, longueur, largeur, epaisseur, couleur, sens_fil, quantite
        except (ValueError, AttributeError):
            return None

    # =================================================================
    #  SIGNAUX INTERNES
    # =================================================================

    def _on_cell_changed(self, row, col):
        """Declenchee quand le texte d'une cellule change."""
        self._schedule_save()

    def _on_combo_changed(self, index):
        """Declenchee quand le panneau selectionne change dans un combo."""
        combo = self.sender()
        if not combo:
            self._schedule_save()
            return
        # Mettre a jour le checkbox fil selon le preset selectionne
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, 4) is combo:
                data = combo.currentData()
                if data:
                    chk_w = self.table.cellWidget(row, 5)
                    if chk_w:
                        chk = chk_w.findChild(QCheckBox)
                        if chk:
                            chk.setChecked(data.get("sens_fil", True))
                break
        self._schedule_save()

    def _schedule_save(self):
        """Planifie une sauvegarde avec delai (debounce)."""
        if self._loading:
            return
        self._save_timer.start()

    # =================================================================
    #  IMPORT / EXPORT CSV
    # =================================================================

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
            if not row or all(c.strip() == "" for c in row):
                continue
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

        self._schedule_save()

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
