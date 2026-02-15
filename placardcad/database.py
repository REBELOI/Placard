"""Modele de donnees SQLite pour PlacardCAD.

Ce module gere la persistance des projets, amenagements, configurations
type (presets) et pieces manuelles dans une base de donnees SQLite locale.

Il expose la classe ``Database`` qui encapsule toutes les operations CRUD
ainsi que les constantes ``PARAMS_DEFAUT`` et ``SCHEMA_DEFAUT`` utilisees
lors de la creation d'un nouvel amenagement.
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
        "materiau": "Chene clair",
        "chant_epaisseur": 1,
        "chant_couleur_fab": "Chene clair",
        "chant_couleur_rgb": [0.85, 0.74, 0.58],
        "sens_fil": True,
    },
    "panneau_rayon": {
        "epaisseur": 19,
        "couleur_fab": "Chene clair",
        "couleur_rgb": [0.82, 0.71, 0.55],
        "materiau": "Chene clair",
        "chant_epaisseur": 1,
        "chant_couleur_fab": "Chene clair",
        "chant_couleur_rgb": [0.85, 0.74, 0.58],
        "retrait_avant": 0,
        "retrait_arriere": 0,
        "sens_fil": True,
    },
    "panneau_rayon_haut": {
        "epaisseur": 22,
        "couleur_fab": "Chene clair",
        "couleur_rgb": [0.82, 0.71, 0.55],
        "materiau": "Chene clair",
        "chant_epaisseur": 1,
        "chant_couleur_fab": "Chene clair",
        "chant_couleur_rgb": [0.85, 0.74, 0.58],
        "retrait_avant": 0,
        "retrait_arriere": 0,
        "sens_fil": True,
    },
    "panneau_mur": {
        "epaisseur": 19,
        "couleur_fab": "Chene clair",
        "couleur_rgb": [0.82, 0.71, 0.55],
        "materiau": "Chene clair",
        "chant_epaisseur": 1,
        "chant_couleur_fab": "Chene clair",
        "chant_couleur_rgb": [0.85, 0.74, 0.58],
        "sens_fil": True,
    },
    "crem_encastree": {
        "largeur": 16,
        "epaisseur": 5,
        "saillie": 0,
        "jeu_rayon": 2,
        "retrait_avant": 80,
        "retrait_arriere": 80,
        "couleur_rgb": [0.6, 0.6, 0.6],
        "materiau": "Acier galvanise",
    },
    "crem_applique": {
        "largeur": 25,
        "epaisseur_saillie": 12,
        "jeu_rayon": 2,
        "retrait_avant": 80,
        "retrait_arriere": 80,
        "couleur_rgb": [0.6, 0.6, 0.6],
        "materiau": "Acier galvanise",
    },
    "tasseau": {
        "section_h": 30,
        "section_l": 30,
        "retrait_avant": 20,
        "couleur_rgb": [0.85, 0.75, 0.55],
        "materiau": "Chene clair",
        "biseau_longueur": 15,
    },
    "materiaux_rendu": {
        "mur": "Mur blanc",
        "sol": "Sol carrelage",
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
    plan_json       TEXT DEFAULT '{}',
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

CREATE TABLE IF NOT EXISTS configurations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nom             TEXT NOT NULL,
    categorie       TEXT NOT NULL,
    params_json     TEXT NOT NULL DEFAULT '{}',
    date_creation   TEXT NOT NULL,
    date_modif      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pieces_manuelles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    projet_id       INTEGER NOT NULL REFERENCES projets(id) ON DELETE CASCADE,
    nom             TEXT NOT NULL DEFAULT '',
    reference       TEXT DEFAULT '',
    longueur        REAL NOT NULL DEFAULT 0,
    largeur         REAL NOT NULL DEFAULT 0,
    epaisseur       REAL NOT NULL DEFAULT 19,
    couleur         TEXT DEFAULT '',
    sens_fil        INTEGER NOT NULL DEFAULT 1,
    quantite        INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS materiaux (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nom             TEXT NOT NULL UNIQUE,
    categorie       TEXT NOT NULL DEFAULT 'bois',
    couleur_rgb     TEXT NOT NULL DEFAULT '[0.8, 0.8, 0.8]',
    texture_diffuse TEXT DEFAULT '',
    texture_bump    TEXT DEFAULT '',
    texture_roughness TEXT DEFAULT '',
    rugosite        REAL NOT NULL DEFAULT 0.5,
    metallic        REAL NOT NULL DEFAULT 0.0,
    specular        REAL NOT NULL DEFAULT 0.5,
    ior             REAL NOT NULL DEFAULT 1.5,
    transparence    REAL NOT NULL DEFAULT 0.0,
    date_creation   TEXT NOT NULL,
    date_modif      TEXT NOT NULL
);
"""

# Cles regroupees dans une configuration type (tout sauf dimensions)
CLES_CONFIG_TYPE = [
    "panneau_separation",
    "panneau_rayon",
    "panneau_rayon_haut",
    "panneau_mur",
    "crem_encastree",
    "crem_applique",
    "tasseau",
]


class Database:
    """Gestionnaire de base de donnees SQLite pour PlacardCAD.

    Encapsule la connexion SQLite et fournit des methodes CRUD pour
    les projets, amenagements, configurations type et pieces manuelles.
    Les cles etrangeres sont activees et les suppressions en cascade
    sont gerees automatiquement.

    Attributes:
        db_path: Chemin vers le fichier de base de donnees SQLite.
        conn: Connexion SQLite active.
    """

    def __init__(self, db_path: str | Path):
        """Ouvre (ou cree) la base de donnees et initialise les tables.

        Args:
            db_path: Chemin vers le fichier de base de donnees SQLite.
                Le fichier est cree s'il n'existe pas.
        """
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._init_tables()

    def _init_tables(self):
        """Cree les tables si elles n'existent pas.

        Execute le script SQL d'initialisation qui cree les tables
        ``projets``, ``amenagements``, ``configurations`` et
        ``pieces_manuelles`` avec ``CREATE TABLE IF NOT EXISTS``.
        Migre le schema si necessaire (ajout de colonnes manquantes).
        """
        self.conn.executescript(SQL_INIT)
        self.conn.commit()
        self._migrate()

    def _migrate(self):
        """Ajoute les colonnes manquantes dans les bases existantes."""
        cols = {
            row[1]
            for row in self.conn.execute("PRAGMA table_info(projets)").fetchall()
        }
        if "plan_json" not in cols:
            self.conn.execute(
                "ALTER TABLE projets ADD COLUMN plan_json TEXT DEFAULT '{}'"
            )
            self.conn.commit()

        # Verifier si la table materiaux existe deja
        tables = {
            row[0]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "materiaux" not in tables:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS materiaux (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    nom             TEXT NOT NULL UNIQUE,
                    categorie       TEXT NOT NULL DEFAULT 'bois',
                    couleur_rgb     TEXT NOT NULL DEFAULT '[0.8, 0.8, 0.8]',
                    texture_diffuse TEXT DEFAULT '',
                    texture_bump    TEXT DEFAULT '',
                    texture_roughness TEXT DEFAULT '',
                    rugosite        REAL NOT NULL DEFAULT 0.5,
                    metallic        REAL NOT NULL DEFAULT 0.0,
                    specular        REAL NOT NULL DEFAULT 0.5,
                    ior             REAL NOT NULL DEFAULT 1.5,
                    transparence    REAL NOT NULL DEFAULT 0.0,
                    date_creation   TEXT NOT NULL DEFAULT '',
                    date_modif      TEXT NOT NULL DEFAULT ''
                );
            """)
            self.conn.commit()

    def close(self):
        """Ferme la connexion a la base de donnees."""
        self.conn.close()

    # --- Projets ---

    def creer_projet(self, nom: str = "Nouveau projet", client: str = "",
                     adresse: str = "", notes: str = "") -> int:
        """Cree un nouveau projet dans la base de donnees.

        Args:
            nom: Nom du projet / chantier.
            client: Nom du client.
            adresse: Adresse du chantier.
            notes: Notes complementaires.

        Returns:
            Identifiant (``id``) du projet nouvellement cree.
        """
        now = datetime.now().isoformat()
        cur = self.conn.execute(
            "INSERT INTO projets (nom, client, adresse, date_creation, date_modif, notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (nom, client, adresse, now, now, notes)
        )
        self.conn.commit()
        return cur.lastrowid

    def modifier_projet(self, projet_id: int, **kwargs):
        """Modifie les champs d'un projet existant.

        Seuls les champs autorises (``nom``, ``client``, ``adresse``,
        ``notes``) sont pris en compte. La date de modification est
        mise a jour automatiquement.

        Args:
            projet_id: Identifiant du projet a modifier.
            **kwargs: Champs a mettre a jour parmi ``nom``, ``client``,
                ``adresse`` et ``notes``.
        """
        allowed = {"nom", "client", "adresse", "notes", "plan_json"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        fields["date_modif"] = datetime.now().isoformat()
        sets = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values()) + [projet_id]
        self.conn.execute(f"UPDATE projets SET {sets} WHERE id = ?", vals)
        self.conn.commit()

    def supprimer_projet(self, projet_id: int):
        """Supprime un projet et ses amenagements associes par cascade.

        Args:
            projet_id: Identifiant du projet a supprimer.
        """
        self.conn.execute("DELETE FROM projets WHERE id = ?", (projet_id,))
        self.conn.commit()

    def get_projet(self, projet_id: int) -> Optional[dict]:
        """Retourne un projet par son identifiant.

        Args:
            projet_id: Identifiant du projet recherche.

        Returns:
            Dictionnaire contenant toutes les colonnes du projet,
            ou ``None`` si le projet n'existe pas.
        """
        row = self.conn.execute(
            "SELECT * FROM projets WHERE id = ?", (projet_id,)
        ).fetchone()
        return dict(row) if row else None

    def lister_projets(self) -> list[dict]:
        """Retourne tous les projets tries par date de modification decroissante.

        Returns:
            Liste de dictionnaires, chacun representant un projet avec
            toutes ses colonnes. Le projet le plus recemment modifie
            apparait en premier.
        """
        rows = self.conn.execute(
            "SELECT * FROM projets ORDER BY date_modif DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    # --- Amenagements ---

    def creer_amenagement(self, projet_id: int, nom: str = "",
                          schema_txt: str = "", params_json: str = "") -> int:
        """Cree un nouvel amenagement rattache a un projet.

        Le numero est auto-incremente par rapport aux amenagements existants
        du projet. Si ``nom``, ``schema_txt`` ou ``params_json`` ne sont pas
        fournis, les valeurs par defaut (``SCHEMA_DEFAUT``, ``PARAMS_DEFAUT``)
        sont utilisees. La date de modification du projet parent est mise a jour.

        Args:
            projet_id: Identifiant du projet parent.
            nom: Nom de l'amenagement. Si vide, genere automatiquement
                ``"Amenagement N"``.
            schema_txt: Texte du schema compact. Si vide, utilise
                ``SCHEMA_DEFAUT``.
            params_json: Parametres au format JSON. Si vide, utilise
                ``PARAMS_DEFAUT`` serialise.

        Returns:
            Identifiant (``id``) de l'amenagement nouvellement cree.
        """
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
        """Modifie les champs d'un amenagement existant.

        Seuls les champs autorises (``nom``, ``schema_txt``, ``params_json``,
        ``freecad_path``, ``notes``) sont pris en compte. La date de
        modification de l'amenagement et du projet parent est mise a jour
        automatiquement.

        Args:
            amenagement_id: Identifiant de l'amenagement a modifier.
            **kwargs: Champs a mettre a jour parmi ``nom``, ``schema_txt``,
                ``params_json``, ``freecad_path`` et ``notes``.
        """
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
        """Supprime un amenagement de la base de donnees.

        Args:
            amenagement_id: Identifiant de l'amenagement a supprimer.
        """
        self.conn.execute(
            "DELETE FROM amenagements WHERE id = ?", (amenagement_id,)
        )
        self.conn.commit()

    def get_amenagement(self, amenagement_id: int) -> Optional[dict]:
        """Retourne un amenagement par son identifiant.

        Args:
            amenagement_id: Identifiant de l'amenagement recherche.

        Returns:
            Dictionnaire contenant toutes les colonnes de l'amenagement,
            ou ``None`` si l'amenagement n'existe pas.
        """
        row = self.conn.execute(
            "SELECT * FROM amenagements WHERE id = ?", (amenagement_id,)
        ).fetchone()
        return dict(row) if row else None

    def lister_amenagements(self, projet_id: int) -> list[dict]:
        """Retourne les amenagements d'un projet tries par numero croissant.

        Args:
            projet_id: Identifiant du projet parent.

        Returns:
            Liste de dictionnaires, chacun representant un amenagement
            avec toutes ses colonnes.
        """
        rows = self.conn.execute(
            "SELECT * FROM amenagements WHERE projet_id = ? ORDER BY numero",
            (projet_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_params(self, amenagement_id: int) -> dict:
        """Retourne les parametres d'un amenagement sous forme de dictionnaire.

        Si l'amenagement n'existe pas ou si ses parametres sont vides,
        retourne une copie de ``PARAMS_DEFAUT``.

        Args:
            amenagement_id: Identifiant de l'amenagement.

        Returns:
            Dictionnaire des parametres (dimensions, panneaux, cremailleres,
            tasseaux, options d'affichage et d'export).
        """
        row = self.conn.execute(
            "SELECT params_json FROM amenagements WHERE id = ?",
            (amenagement_id,)
        ).fetchone()
        if row and row["params_json"]:
            return json.loads(row["params_json"])
        return dict(PARAMS_DEFAUT)

    # --- Configurations type (presets) ---

    def sauver_configuration(self, nom: str, categorie: str, params: dict) -> int:
        """Sauvegarde une nouvelle configuration type (preset).

        Args:
            nom: Nom de la configuration (ex. ``"Standard chene"``).
            categorie: Categorie de regroupement (ex. ``"panneau"``,
                ``"cremaillere"``).
            params: Dictionnaire des parametres a sauvegarder.

        Returns:
            Identifiant (``id``) de la configuration nouvellement creee.
        """
        now = datetime.now().isoformat()
        params_json = json.dumps(params, ensure_ascii=False)
        cur = self.conn.execute(
            "INSERT INTO configurations (nom, categorie, params_json, date_creation, date_modif) "
            "VALUES (?, ?, ?, ?, ?)",
            (nom, categorie, params_json, now, now)
        )
        self.conn.commit()
        return cur.lastrowid

    def modifier_configuration(self, config_id: int, nom: str = None, params: dict = None):
        """Met a jour une configuration type existante.

        Le nom et/ou les parametres peuvent etre modifies independamment.
        La date de modification est mise a jour automatiquement.

        Args:
            config_id: Identifiant de la configuration a modifier.
            nom: Nouveau nom de la configuration, ou ``None`` pour
                ne pas le modifier.
            params: Nouveau dictionnaire de parametres, ou ``None``
                pour ne pas le modifier.
        """
        now = datetime.now().isoformat()
        if nom is not None:
            self.conn.execute(
                "UPDATE configurations SET nom = ?, date_modif = ? WHERE id = ?",
                (nom, now, config_id)
            )
        if params is not None:
            self.conn.execute(
                "UPDATE configurations SET params_json = ?, date_modif = ? WHERE id = ?",
                (json.dumps(params, ensure_ascii=False), now, config_id)
            )
        self.conn.commit()

    def supprimer_configuration(self, config_id: int):
        """Supprime une configuration type de la base de donnees.

        Args:
            config_id: Identifiant de la configuration a supprimer.
        """
        self.conn.execute("DELETE FROM configurations WHERE id = ?", (config_id,))
        self.conn.commit()

    def lister_configurations(self, categorie: str = None) -> list[dict]:
        """Liste les configurations type, optionnellement filtrees par categorie.

        Chaque dictionnaire retourne contient une cle supplementaire
        ``params`` avec les parametres deserialises depuis le JSON.

        Args:
            categorie: Si fourni, filtre les configurations par cette
                categorie. Si ``None``, retourne toutes les configurations.

        Returns:
            Liste de dictionnaires representant les configurations,
            tries par categorie puis par nom.
        """
        if categorie:
            rows = self.conn.execute(
                "SELECT * FROM configurations WHERE categorie = ? ORDER BY nom",
                (categorie,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM configurations ORDER BY categorie, nom"
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["params"] = json.loads(d["params_json"])
            result.append(d)
        return result

    def get_configuration(self, config_id: int) -> Optional[dict]:
        """Retourne une configuration type par son identifiant.

        Le dictionnaire retourne contient une cle supplementaire
        ``params`` avec les parametres deserialises depuis le JSON.

        Args:
            config_id: Identifiant de la configuration recherchee.

        Returns:
            Dictionnaire contenant toutes les colonnes de la configuration
            plus la cle ``params``, ou ``None`` si la configuration
            n'existe pas.
        """
        row = self.conn.execute(
            "SELECT * FROM configurations WHERE id = ?", (config_id,)
        ).fetchone()
        if row:
            d = dict(row)
            d["params"] = json.loads(d["params_json"])
            return d
        return None

    # --- Pieces manuelles ---

    def ajouter_piece_manuelle(self, projet_id: int, nom: str = "",
                               reference: str = "", longueur: float = 0,
                               largeur: float = 0, epaisseur: float = 19,
                               couleur: str = "", sens_fil: bool = True,
                               quantite: int = 1) -> int:
        """Ajoute une piece manuelle a un projet.

        Les pieces manuelles sont des panneaux ajoutes librement par
        l'utilisateur, en dehors de la generation automatique a partir
        du schema.

        Args:
            projet_id: Identifiant du projet parent.
            nom: Designation de la piece.
            reference: Reference catalogue ou interne.
            longueur: Longueur de la piece en mm.
            largeur: Largeur de la piece en mm.
            epaisseur: Epaisseur de la piece en mm.
            couleur: Couleur / finition.
            sens_fil: ``True`` si le sens du fil suit la longueur.
            quantite: Nombre d'exemplaires identiques.

        Returns:
            Identifiant (``id``) de la piece nouvellement creee.
        """
        cur = self.conn.execute(
            "INSERT INTO pieces_manuelles "
            "(projet_id, nom, reference, longueur, largeur, epaisseur, "
            " couleur, sens_fil, quantite) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (projet_id, nom, reference, longueur, largeur, epaisseur,
             couleur, int(sens_fil), quantite)
        )
        self.conn.commit()
        return cur.lastrowid

    def modifier_piece_manuelle(self, piece_id: int, **kwargs):
        """Modifie les champs d'une piece manuelle existante.

        Seuls les champs autorises (``nom``, ``reference``, ``longueur``,
        ``largeur``, ``epaisseur``, ``couleur``, ``sens_fil``, ``quantite``)
        sont pris en compte.

        Args:
            piece_id: Identifiant de la piece a modifier.
            **kwargs: Champs a mettre a jour parmi les champs autorises.
        """
        allowed = {"nom", "reference", "longueur", "largeur", "epaisseur",
                   "couleur", "sens_fil", "quantite"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        if "sens_fil" in fields:
            fields["sens_fil"] = int(fields["sens_fil"])
        sets = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values()) + [piece_id]
        self.conn.execute(
            f"UPDATE pieces_manuelles SET {sets} WHERE id = ?", vals
        )
        self.conn.commit()

    def supprimer_piece_manuelle(self, piece_id: int):
        """Supprime une piece manuelle de la base de donnees.

        Args:
            piece_id: Identifiant de la piece a supprimer.
        """
        self.conn.execute(
            "DELETE FROM pieces_manuelles WHERE id = ?", (piece_id,)
        )
        self.conn.commit()

    def supprimer_pieces_manuelles_projet(self, projet_id: int):
        """Supprime toutes les pieces manuelles d'un projet."""
        self.conn.execute(
            "DELETE FROM pieces_manuelles WHERE projet_id = ?", (projet_id,)
        )
        self.conn.commit()

    def lister_pieces_manuelles(self, projet_id: int) -> list[dict]:
        """Retourne les pieces manuelles d'un projet."""
        rows = self.conn.execute(
            "SELECT * FROM pieces_manuelles WHERE projet_id = ? ORDER BY id",
            (projet_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    # --- Materiaux (rendu photoréaliste) ---

    def ajouter_materiau(self, nom: str, categorie: str = "bois",
                         couleur_rgb: list[float] | None = None,
                         texture_diffuse: str = "",
                         texture_bump: str = "",
                         texture_roughness: str = "",
                         rugosite: float = 0.5,
                         metallic: float = 0.0,
                         specular: float = 0.5,
                         ior: float = 1.5,
                         transparence: float = 0.0) -> int:
        """Ajoute un materiau personnalise dans la base de donnees.

        Args:
            nom: Nom unique du materiau.
            categorie: Categorie ('bois', 'metal', 'melamine', etc.).
            couleur_rgb: Couleur diffuse [R, G, B] en 0.0-1.0.
            texture_diffuse: Chemin vers l'image de texture diffuse.
            texture_bump: Chemin vers l'image de bump map.
            texture_roughness: Chemin vers la roughness map.
            rugosite: Rugosite de surface (0.0 - 1.0).
            metallic: Metallicite (0.0 - 1.0).
            specular: Intensite speculaire (0.0 - 1.0).
            ior: Indice de refraction.
            transparence: Transparence (0.0 - 1.0).

        Returns:
            Identifiant du materiau cree.
        """
        if couleur_rgb is None:
            couleur_rgb = [0.8, 0.8, 0.8]
        now = datetime.now().isoformat()
        cur = self.conn.execute(
            "INSERT INTO materiaux "
            "(nom, categorie, couleur_rgb, texture_diffuse, texture_bump, "
            " texture_roughness, rugosite, metallic, specular, ior, "
            " transparence, date_creation, date_modif) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (nom, categorie, json.dumps(couleur_rgb), texture_diffuse,
             texture_bump, texture_roughness, rugosite, metallic, specular,
             ior, transparence, now, now)
        )
        self.conn.commit()
        return cur.lastrowid

    def modifier_materiau(self, materiau_id: int, **kwargs):
        """Modifie les champs d'un materiau existant.

        Args:
            materiau_id: Identifiant du materiau a modifier.
            **kwargs: Champs a mettre a jour parmi nom, categorie,
                couleur_rgb, texture_diffuse, texture_bump,
                texture_roughness, rugosite, metallic, specular,
                ior, transparence.
        """
        allowed = {"nom", "categorie", "couleur_rgb", "texture_diffuse",
                   "texture_bump", "texture_roughness", "rugosite", "metallic",
                   "specular", "ior", "transparence"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        if "couleur_rgb" in fields:
            fields["couleur_rgb"] = json.dumps(fields["couleur_rgb"])
        fields["date_modif"] = datetime.now().isoformat()
        sets = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values()) + [materiau_id]
        self.conn.execute(f"UPDATE materiaux SET {sets} WHERE id = ?", vals)
        self.conn.commit()

    def supprimer_materiau(self, materiau_id: int):
        """Supprime un materiau de la base de donnees.

        Args:
            materiau_id: Identifiant du materiau a supprimer.
        """
        self.conn.execute("DELETE FROM materiaux WHERE id = ?", (materiau_id,))
        self.conn.commit()

    def get_materiau(self, materiau_id: int) -> Optional[dict]:
        """Retourne un materiau par son identifiant.

        Args:
            materiau_id: Identifiant du materiau recherche.

        Returns:
            Dictionnaire du materiau avec couleur_rgb deserialisee,
            ou None si non trouve.
        """
        row = self.conn.execute(
            "SELECT * FROM materiaux WHERE id = ?", (materiau_id,)
        ).fetchone()
        if row:
            d = dict(row)
            d["couleur_rgb"] = json.loads(d["couleur_rgb"])
            return d
        return None

    def get_materiau_par_nom(self, nom: str) -> Optional[dict]:
        """Retourne un materiau par son nom.

        Args:
            nom: Nom du materiau recherche.

        Returns:
            Dictionnaire du materiau ou None.
        """
        row = self.conn.execute(
            "SELECT * FROM materiaux WHERE nom = ?", (nom,)
        ).fetchone()
        if row:
            d = dict(row)
            d["couleur_rgb"] = json.loads(d["couleur_rgb"])
            return d
        return None

    def lister_materiaux(self, categorie: str | None = None) -> list[dict]:
        """Liste les materiaux, optionnellement filtres par categorie.

        Args:
            categorie: Filtre par categorie, ou None pour tout lister.

        Returns:
            Liste de dictionnaires materiaux.
        """
        if categorie:
            rows = self.conn.execute(
                "SELECT * FROM materiaux WHERE categorie = ? ORDER BY nom",
                (categorie,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM materiaux ORDER BY categorie, nom"
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["couleur_rgb"] = json.loads(d["couleur_rgb"])
            result.append(d)
        return result
