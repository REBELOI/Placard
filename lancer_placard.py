"""
Aménagement placard par schéma compact.
Exécuter directement dans FreeCAD.

Modifier le SCHEMA et les PARAMS ci-dessous selon vos besoins.
"""

import importlib
import placard_lib
importlib.reload(placard_lib)
from placard_lib import schema_vers_config, construire_placard

# ===========================================================================
#  SCHÉMA DE L'AMÉNAGEMENT
# ===========================================================================
#
#  Symboles:
#    |  crémaillère encastrée (+ panneau mur si bord extérieur)
#    /  crémaillère en applique
#    *  tasseau sous ce rayon
#    -  rayon haut (1ère ligne)
#    _  rayon (1 ligne = 1 rayon)
#    (espace)  rien / mur brut
#    Dernière ligne: largeurs en mm (vide = répartition auto)
#
#  Exemples:
#
#    3 compartiments égaux, tout encastré, tasseaux rayon haut:
#        *-----------*-----------*-----------*
#        |__________|__________|__________|
#        |__________|__________|__________|
#        |__________|__________|__________|
#        |__________|__________|
#
#    2 compartiments, applique à gauche, largeurs fixées:
#        /-----------*-----------*
#        /__________|__________|
#        /__________|__________|
#        /__________|
#        500         800
#
#    Largeur mixte (C1=300, reste auto):
#        *-----------*-----------*-----------*
#        |__________|__________|__________|
#        |__________|__________|__________|
#        300
#
# ===========================================================================

SCHEMA = """
*-----------*-----------*-----------*
|__________|__________|__________|
|__________|__________|__________|
|__________|__________|__________|
|__________|__________|
"""

# ===========================================================================
#  PARAMÈTRES GÉNÉRAUX
# ===========================================================================

PARAMS = {
    # --- Dimensions globales ---
    "hauteur": 2500,
    "largeur": 3000,
    "profondeur": 600,
    "rayon_haut_position": 300,

    # --- Panneaux ---
    "panneau_separation": {
        "epaisseur": 19,
        "couleur_fab": "Chêne clair",
        "couleur_rgb": (0.82, 0.71, 0.55),
        "chant_epaisseur": 1,
        "chant_couleur_fab": "Chêne clair",
        "chant_couleur_rgb": (0.85, 0.74, 0.58),
    },
    "panneau_rayon": {
        "epaisseur": 19,
        "couleur_fab": "Chêne clair",
        "couleur_rgb": (0.82, 0.71, 0.55),
        "chant_epaisseur": 1,
        "chant_couleur_fab": "Chêne clair",
        "chant_couleur_rgb": (0.85, 0.74, 0.58),
    },
    "panneau_rayon_haut": {
        "epaisseur": 22,
        "couleur_fab": "Chêne clair",
        "couleur_rgb": (0.82, 0.71, 0.55),
        "chant_epaisseur": 1,
        "chant_couleur_fab": "Chêne clair",
        "chant_couleur_rgb": (0.85, 0.74, 0.58),
    },
    "panneau_mur": {
        "epaisseur": 19,
        "couleur_fab": "Chêne clair",
        "couleur_rgb": (0.82, 0.71, 0.55),
        "chant_epaisseur": 1,
        "chant_couleur_fab": "Chêne clair",
        "chant_couleur_rgb": (0.85, 0.74, 0.58),
    },

    # --- Crémaillères ---
    "crem_encastree": {
        "largeur": 16,
        "epaisseur": 5,
        "saillie": 0,
        "jeu_rayon": 2,
        "retrait_avant": 80,
        "retrait_arriere": 80,
        "couleur_rgb": (0.6, 0.6, 0.6),
    },
    "crem_applique": {
        "largeur": 25,
        "epaisseur_saillie": 12,
        "jeu_rayon": 2,
        "retrait_avant": 80,
        "retrait_arriere": 80,
        "couleur_rgb": (0.6, 0.6, 0.6),
    },

    # --- Tasseaux ---
    "tasseau": {
        "section_h": 30,
        "section_l": 30,
        "retrait_avant": 20,
        "couleur_rgb": (0.85, 0.75, 0.55),
        "biseau_longueur": 15,
    },

    # --- Affichage ---
    "afficher_murs": True,
    "mur_epaisseur": 50,
    "mur_couleur_rgb": (0.85, 0.85, 0.82),
    "mur_transparence": 85,

    # --- Export ---
    "export_fiche": True,
    "dossier_export": "",
}

# ===========================================================================
#  CONSTRUCTION
# ===========================================================================

config = schema_vers_config(SCHEMA, PARAMS)
doc, fiche = construire_placard(config)
