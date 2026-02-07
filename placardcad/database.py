"""
Modele de donnees SQLite pour PlacardCAD.
Gestion des projets et amenagements.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


# Parametres par defaut pour un nouvel amenagement
PARAMS_DEFAUT = {
    "hauteur": 2500,
    "largeur": 3000,
    "profondeur": 600,
    "rayon_haut_position": 300,
    "panneau_separation": {
        "epaisseur": 19,
        "couleur_fab": "Chene clair",
        "couleur_rgb": [0.82, 0.71, 0.55],
        "chant_epaisseur": 1,
        "chant_couleur_fab": "Chene clair",
        "chant_couleur_rgb": [0.85, 0.74, 0.58],
    },
    "panneau_rayon": {
        "epaisseur": 19,
        "couleur_fab": "Chene clair",
        "couleur_rgb": [0.82, 0.71, 0.55],
        "chant_epaisseur": 1,
        "chant_couleur_fab": "Chene clair",
        "chant_couleur_rgb": [0.85, 0.74, 0.58],
    },
    "panneau_rayon_haut": {
        "epaisseur": 22,
        "couleur_fab": "Chene clair",
        "couleur_rgb": [0.82, 0.71, 0.55],
        "chant_epaisseur": 1,
        "chant_couleur_fab": "Chene clair",
        "chant_couleur_rgb": [0.85, 0.74, 0.58],
    },
    "panneau_mur": {
        "epaisseur": 19,
        "couleur_fab": "Chene clair",
        "couleur_rgb": [0.82, 0.71, 0.55],
        "chant_epaisseur": 1,
        "chant_couleur_fab": "Chene clair",
        "chant_couleur_rgb": [0.85, 0.74, 0.58],
    },
    "crem_encastree": {
        "largeur": 16,
        "epaisseur": 5,
        "saillie": 0,
        "jeu_rayon": 2,
        "retrait_avant": 80,
        "retrait_arriere": 80,
        "couleur_rgb": [0.6, 0.6, 0.6],
    },
    "crem_applique": {
        "largeur": 25,
        "epaisseur_saillie": 12,
        "jeu_rayon": 2,
        "retrait_avant": 80,
        "retrait_arriere": 80,
        "couleur_rgb": [0.6, 0.6, 0.6],
    },
    "tasseau": {
        "section_h": 30,
        "section_l": 30,
        "retrait_avant": 20,
        "couleur_rgb": [0.85, 0.75, 0.55],
        "biseau_longueur": 15,
    },
    "afficher_murs": True,
    "mur_epaisseur": 50,
    "mur_couleur_rgb": [0.85, 0.85, 0.82],
    "mur_transparence": 85,
    "export_fiche": True,
    "dossier_export": "",
}

SCHEMA_DEFAUT = """\
*-----------*-----------*-----------*
|__________|__________|__________|
|__________|__________|__________|
|__________|__________|__________|
|__________|__________|"""


SQL_INIT = """
CREATE TABLE IF NOT EXISTS projets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nom             TEXT NOT NULL DEFAULT 'Nouveau projet',
    client          TEXT DEFAULT '',
    adresse         TEXT DEFAULT '',
    date_creation   TEXT NOT NULL,
    date_modif      TEXT NOT NULL,
    notes           TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS amenagements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    projet_id       INTEGER NOT NULL REFERENCES projets(id) ON DELETE CASCADE,
    numero          INTEGER NOT NULL DEFAULT 1,
    nom             TEXT NOT NULL DEFAULT 'Amenagement 1',
    schema_txt      TEXT NOT NULL DEFAULT '',
    params_json     TEXT NOT NULL DEFAULT '{}',
    freecad_path    TEXT DEFAULT '',
    date_creation   TEXT NOT NULL,
    date_modif      TEXT NOT NULL,
    notes           TEXT DEFAULT ''
);
"""


class Database:
    """Gestionnaire de base de donnees SQLite pour PlacardCAD."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._init_tables()

    def _init_tables(self):
        """Cree les tables si elles n'existent pas."""
        self.conn.executescript(SQL_INIT)
        self.conn.commit()

    def close(self):
        self.conn.close()

    # --- Projets ---

    def creer_projet(self, nom: str = "Nouveau projet", client: str = "",
                     adresse: str = "", notes: str = "") -> int:
        """Cree un projet et retourne son id."""
        now = datetime.now().isoformat()
        cur = self.conn.execute(
            "INSERT INTO projets (nom, client, adresse, date_creation, date_modif, notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (nom, client, adresse, now, now, notes)
        )
        self.conn.commit()
        return cur.lastrowid

    def modifier_projet(self, projet_id: int, **kwargs):
        """Modifie les champs d'un projet."""
        allowed = {"nom", "client", "adresse", "notes"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        fields["date_modif"] = datetime.now().isoformat()
        sets = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values()) + [projet_id]
        self.conn.execute(f"UPDATE projets SET {sets} WHERE id = ?", vals)
        self.conn.commit()

    def supprimer_projet(self, projet_id: int):
        """Supprime un projet et ses amenagements (CASCADE)."""
        self.conn.execute("DELETE FROM projets WHERE id = ?", (projet_id,))
        self.conn.commit()

    def get_projet(self, projet_id: int) -> Optional[dict]:
        """Retourne un projet par son id."""
        row = self.conn.execute(
            "SELECT * FROM projets WHERE id = ?", (projet_id,)
        ).fetchone()
        return dict(row) if row else None

    def lister_projets(self) -> list[dict]:
        """Retourne tous les projets tries par date de modification."""
        rows = self.conn.execute(
            "SELECT * FROM projets ORDER BY date_modif DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    # --- Amenagements ---

    def creer_amenagement(self, projet_id: int, nom: str = "",
                          schema_txt: str = "", params_json: str = "") -> int:
        """Cree un amenagement et retourne son id."""
        row = self.conn.execute(
            "SELECT COALESCE(MAX(numero), 0) + 1 FROM amenagements WHERE projet_id = ?",
            (projet_id,)
        ).fetchone()
        numero = row[0]

        if not nom:
            nom = f"Amenagement {numero}"
        if not schema_txt:
            schema_txt = SCHEMA_DEFAUT
        if not params_json:
            params_json = json.dumps(PARAMS_DEFAUT, ensure_ascii=False)

        now = datetime.now().isoformat()
        cur = self.conn.execute(
            "INSERT INTO amenagements "
            "(projet_id, numero, nom, schema_txt, params_json, date_creation, date_modif) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (projet_id, numero, nom, schema_txt, params_json, now, now)
        )
        self.conn.commit()

        self.conn.execute(
            "UPDATE projets SET date_modif = ? WHERE id = ?",
            (now, projet_id)
        )
        self.conn.commit()

        return cur.lastrowid

    def modifier_amenagement(self, amenagement_id: int, **kwargs):
        """Modifie les champs d'un amenagement."""
        allowed = {"nom", "schema_txt", "params_json", "freecad_path", "notes"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        fields["date_modif"] = datetime.now().isoformat()
        sets = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values()) + [amenagement_id]
        self.conn.execute(f"UPDATE amenagements SET {sets} WHERE id = ?", vals)
        self.conn.commit()

        row = self.conn.execute(
            "SELECT projet_id FROM amenagements WHERE id = ?", (amenagement_id,)
        ).fetchone()
        if row:
            self.conn.execute(
                "UPDATE projets SET date_modif = ? WHERE id = ?",
                (fields["date_modif"], row["projet_id"])
            )
            self.conn.commit()

    def supprimer_amenagement(self, amenagement_id: int):
        """Supprime un amenagement."""
        self.conn.execute(
            "DELETE FROM amenagements WHERE id = ?", (amenagement_id,)
        )
        self.conn.commit()

    def get_amenagement(self, amenagement_id: int) -> Optional[dict]:
        """Retourne un amenagement par son id."""
        row = self.conn.execute(
            "SELECT * FROM amenagements WHERE id = ?", (amenagement_id,)
        ).fetchone()
        return dict(row) if row else None

    def lister_amenagements(self, projet_id: int) -> list[dict]:
        """Retourne les amenagements d'un projet tries par numero."""
        rows = self.conn.execute(
            "SELECT * FROM amenagements WHERE projet_id = ? ORDER BY numero",
            (projet_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_params(self, amenagement_id: int) -> dict:
        """Retourne les parametres d'un amenagement en tant que dict."""
        row = self.conn.execute(
            "SELECT params_json FROM amenagements WHERE id = ?",
            (amenagement_id,)
        ).fetchone()
        if row and row["params_json"]:
            return json.loads(row["params_json"])
        return dict(PARAMS_DEFAUT)
