"""Gestion des materiaux pour le rendu photoréaliste (Render Workbench).

Ce module definit le catalogue de materiaux avec leurs proprietes physiques
(couleur diffuse, rugosite, reflexion, metallic) et leurs textures (images).
Les materiaux sont utilisables par le Render Workbench de FreeCAD pour
generer des rendus photoréalistes.

Chaque materiau est un dictionnaire avec les cles suivantes:
    - nom: str — Nom affiche dans l'interface.
    - categorie: str — 'bois', 'metal', 'plastique', etc.
    - couleur_rgb: list[float] — Couleur diffuse [R, G, B] en 0.0-1.0.
    - texture_diffuse: str — Chemin relatif vers l'image de texture diffuse.
    - texture_bump: str — Chemin relatif vers l'image de bump/normal map.
    - texture_roughness: str — Chemin relatif vers la roughness map.
    - rugosite: float — Rugosite de surface (0.0 = miroir, 1.0 = mat).
    - metallic: float — Metallicite (0.0 = dielectrique, 1.0 = metal).
    - specular: float — Intensite speculaire (0.0 - 1.0).
    - ior: float — Indice de refraction (1.5 typique pour bois/plastique).
    - transparence: float — Transparence (0.0 = opaque, 1.0 = transparent).
"""

from pathlib import Path
from typing import Optional
import json
import copy


# Repertoire par defaut pour les textures
TEXTURES_DIR = Path(__file__).parent / "resources" / "textures"


def _chemin_texture(filename: str) -> str:
    """Retourne le chemin relatif d'une texture dans le repertoire textures.

    Args:
        filename: Nom du fichier image (ex. 'chene_clair.jpg').

    Returns:
        Chemin relatif sous la forme 'textures/filename'.
    """
    if not filename:
        return ""
    return f"textures/{filename}"


# =====================================================================
#  Definition d'un materiau
# =====================================================================

def creer_materiau(
    nom: str,
    categorie: str = "bois",
    couleur_rgb: list[float] | None = None,
    texture_diffuse: str = "",
    texture_bump: str = "",
    texture_roughness: str = "",
    rugosite: float = 0.5,
    metallic: float = 0.0,
    specular: float = 0.5,
    ior: float = 1.5,
    transparence: float = 0.0,
) -> dict:
    """Cree un dictionnaire de materiau avec les proprietes de rendu.

    Args:
        nom: Nom du materiau (ex. 'Chene clair').
        categorie: Categorie du materiau ('bois', 'metal', 'plastique', 'verre').
        couleur_rgb: Couleur diffuse [R, G, B] 0.0-1.0. Defaut blanc.
        texture_diffuse: Chemin vers l'image de texture diffuse.
        texture_bump: Chemin vers l'image de bump/normal map.
        texture_roughness: Chemin vers la roughness map.
        rugosite: Rugosite de surface (0.0 miroir - 1.0 mat).
        metallic: Metallicite (0.0 dielectrique - 1.0 metal).
        specular: Intensite speculaire (0.0 - 1.0).
        ior: Indice de refraction.
        transparence: Transparence (0.0 opaque - 1.0 transparent).

    Returns:
        Dictionnaire de materiau serialisable en JSON.
    """
    if couleur_rgb is None:
        couleur_rgb = [0.8, 0.8, 0.8]
    return {
        "nom": nom,
        "categorie": categorie,
        "couleur_rgb": list(couleur_rgb),
        "texture_diffuse": texture_diffuse,
        "texture_bump": texture_bump,
        "texture_roughness": texture_roughness,
        "rugosite": rugosite,
        "metallic": metallic,
        "specular": specular,
        "ior": ior,
        "transparence": transparence,
    }


# =====================================================================
#  Catalogue de materiaux par defaut
# =====================================================================

CATALOGUE_MATERIAUX: dict[str, dict] = {
    # =================================================================
    #  EGGER — Unis / Solid colors
    # =================================================================
    "EGGER W1000 ST9 Blanc Premium": creer_materiau(
        nom="EGGER W1000 ST9 Blanc Premium",
        categorie="egger_uni",
        couleur_rgb=[0.94, 0.94, 0.92],
        texture_diffuse=_chemin_texture("egger/W1000_ST9.jpg"),
        rugosite=0.35,
        specular=0.4,
    ),
    "EGGER W1100 ST9 Blanc Alpin": creer_materiau(
        nom="EGGER W1100 ST9 Blanc Alpin",
        categorie="egger_uni",
        couleur_rgb=[0.96, 0.96, 0.95],
        texture_diffuse=_chemin_texture("egger/W1100_ST9.jpg"),
        rugosite=0.35,
        specular=0.4,
    ),
    "EGGER W1200 ST9 Blanc Porcelaine": creer_materiau(
        nom="EGGER W1200 ST9 Blanc Porcelaine",
        categorie="egger_uni",
        couleur_rgb=[0.95, 0.95, 0.93],
        texture_diffuse=_chemin_texture("egger/W1200_ST9.jpg"),
        rugosite=0.35,
        specular=0.4,
    ),
    "EGGER W908 SM Blanc Craie": creer_materiau(
        nom="EGGER W908 SM Blanc Craie",
        categorie="egger_uni",
        couleur_rgb=[0.93, 0.92, 0.88],
        texture_diffuse=_chemin_texture("egger/W908_SM.jpg"),
        rugosite=0.50,
        specular=0.25,
    ),
    "EGGER W980 SM Blanc Kaolin": creer_materiau(
        nom="EGGER W980 SM Blanc Kaolin",
        categorie="egger_uni",
        couleur_rgb=[0.92, 0.91, 0.87],
        texture_diffuse=_chemin_texture("egger/W980_SM.jpg"),
        rugosite=0.50,
        specular=0.25,
    ),
    "EGGER U104 ST9 Blanc Albatre": creer_materiau(
        nom="EGGER U104 ST9 Blanc Albatre",
        categorie="egger_uni",
        couleur_rgb=[0.93, 0.91, 0.86],
        texture_diffuse=_chemin_texture("egger/U104_ST9.jpg"),
        rugosite=0.35,
        specular=0.35,
    ),
    "EGGER U216 ST9 Blanc Casse": creer_materiau(
        nom="EGGER U216 ST9 Blanc Casse",
        categorie="egger_uni",
        couleur_rgb=[0.93, 0.90, 0.84],
        texture_diffuse=_chemin_texture("egger/U216_ST9.jpg"),
        rugosite=0.35,
        specular=0.35,
    ),
    "EGGER U222 ST9 Blanc Ecru": creer_materiau(
        nom="EGGER U222 ST9 Blanc Ecru",
        categorie="egger_uni",
        couleur_rgb=[0.91, 0.88, 0.82],
        texture_diffuse=_chemin_texture("egger/U222_ST9.jpg"),
        rugosite=0.35,
        specular=0.35,
    ),
    "EGGER U113 ST9 Beige Sable": creer_materiau(
        nom="EGGER U113 ST9 Beige Sable",
        categorie="egger_uni",
        couleur_rgb=[0.85, 0.80, 0.70],
        texture_diffuse=_chemin_texture("egger/U113_ST9.jpg"),
        rugosite=0.35,
        specular=0.35,
    ),
    "EGGER U156 ST9 Beige Rose": creer_materiau(
        nom="EGGER U156 ST9 Beige Rose",
        categorie="egger_uni",
        couleur_rgb=[0.87, 0.78, 0.72],
        texture_diffuse=_chemin_texture("egger/U156_ST9.jpg"),
        rugosite=0.35,
        specular=0.35,
    ),
    "EGGER U211 ST9 Beige Amande": creer_materiau(
        nom="EGGER U211 ST9 Beige Amande",
        categorie="egger_uni",
        couleur_rgb=[0.88, 0.83, 0.73],
        texture_diffuse=_chemin_texture("egger/U211_ST9.jpg"),
        rugosite=0.35,
        specular=0.35,
    ),
    "EGGER U201 ST9 Gris Galet": creer_materiau(
        nom="EGGER U201 ST9 Gris Galet",
        categorie="egger_uni",
        couleur_rgb=[0.76, 0.74, 0.70],
        texture_diffuse=_chemin_texture("egger/U201_ST9.jpg"),
        rugosite=0.35,
        specular=0.35,
    ),
    "EGGER U708 ST9 Gris Clair": creer_materiau(
        nom="EGGER U708 ST9 Gris Clair",
        categorie="egger_uni",
        couleur_rgb=[0.72, 0.72, 0.70],
        texture_diffuse=_chemin_texture("egger/U708_ST9.jpg"),
        rugosite=0.35,
        specular=0.35,
    ),
    "EGGER U707 ST9 Soie Grise": creer_materiau(
        nom="EGGER U707 ST9 Soie Grise",
        categorie="egger_uni",
        couleur_rgb=[0.68, 0.68, 0.66],
        texture_diffuse=_chemin_texture("egger/U707_ST9.jpg"),
        rugosite=0.35,
        specular=0.35,
    ),
    "EGGER U727 ST9 Gris Argile": creer_materiau(
        nom="EGGER U727 ST9 Gris Argile",
        categorie="egger_uni",
        couleur_rgb=[0.60, 0.58, 0.55],
        texture_diffuse=_chemin_texture("egger/U727_ST9.jpg"),
        rugosite=0.35,
        specular=0.35,
    ),
    "EGGER U732 ST9 Gris Macadam": creer_materiau(
        nom="EGGER U732 ST9 Gris Macadam",
        categorie="egger_uni",
        couleur_rgb=[0.52, 0.52, 0.50],
        texture_diffuse=_chemin_texture("egger/U732_ST9.jpg"),
        rugosite=0.35,
        specular=0.35,
    ),
    "EGGER U750 ST9 Gris Souris": creer_materiau(
        nom="EGGER U750 ST9 Gris Souris",
        categorie="egger_uni",
        couleur_rgb=[0.45, 0.45, 0.44],
        texture_diffuse=_chemin_texture("egger/U750_ST9.jpg"),
        rugosite=0.35,
        specular=0.35,
    ),
    "EGGER U763 ST9 Gris Perle": creer_materiau(
        nom="EGGER U763 ST9 Gris Perle",
        categorie="egger_uni",
        couleur_rgb=[0.65, 0.64, 0.62],
        texture_diffuse=_chemin_texture("egger/U763_ST9.jpg"),
        rugosite=0.35,
        specular=0.35,
    ),
    "EGGER U767 ST9 Gris Cubanite": creer_materiau(
        nom="EGGER U767 ST9 Gris Cubanite",
        categorie="egger_uni",
        couleur_rgb=[0.40, 0.40, 0.40],
        texture_diffuse=_chemin_texture("egger/U767_ST9.jpg"),
        rugosite=0.35,
        specular=0.35,
    ),
    "EGGER U775 ST9 Gris Brume": creer_materiau(
        nom="EGGER U775 ST9 Gris Brume",
        categorie="egger_uni",
        couleur_rgb=[0.55, 0.55, 0.54],
        texture_diffuse=_chemin_texture("egger/U775_ST9.jpg"),
        rugosite=0.35,
        specular=0.35,
    ),
    "EGGER U963 ST9 Gris Ombre": creer_materiau(
        nom="EGGER U963 ST9 Gris Ombre",
        categorie="egger_uni",
        couleur_rgb=[0.35, 0.35, 0.35],
        texture_diffuse=_chemin_texture("egger/U963_ST9.jpg"),
        rugosite=0.35,
        specular=0.35,
    ),
    "EGGER U741 ST9 Brun Taupe": creer_materiau(
        nom="EGGER U741 ST9 Brun Taupe",
        categorie="egger_uni",
        couleur_rgb=[0.45, 0.40, 0.35],
        texture_diffuse=_chemin_texture("egger/U741_ST9.jpg"),
        rugosite=0.35,
        specular=0.35,
    ),
    "EGGER U899 ST9 Soft Black": creer_materiau(
        nom="EGGER U899 ST9 Soft Black",
        categorie="egger_uni",
        couleur_rgb=[0.15, 0.15, 0.15],
        texture_diffuse=_chemin_texture("egger/U899_ST9.jpg"),
        rugosite=0.40,
        specular=0.30,
    ),
    "EGGER U999 ST12 Noir": creer_materiau(
        nom="EGGER U999 ST12 Noir",
        categorie="egger_uni",
        couleur_rgb=[0.07, 0.07, 0.07],
        texture_diffuse=_chemin_texture("egger/U999_ST12.jpg"),
        rugosite=0.35,
        specular=0.35,
    ),
    "EGGER U505 ST9 Bleu Nordique": creer_materiau(
        nom="EGGER U505 ST9 Bleu Nordique",
        categorie="egger_uni",
        couleur_rgb=[0.22, 0.32, 0.42],
        texture_diffuse=_chemin_texture("egger/U505_ST9.jpg"),
        rugosite=0.35,
        specular=0.35,
    ),
    "EGGER U608 ST9 Vert Opale": creer_materiau(
        nom="EGGER U608 ST9 Vert Opale",
        categorie="egger_uni",
        couleur_rgb=[0.55, 0.68, 0.62],
        texture_diffuse=_chemin_texture("egger/U608_ST9.jpg"),
        rugosite=0.35,
        specular=0.35,
    ),
    "EGGER U626 ST9 Vert Kiwi": creer_materiau(
        nom="EGGER U626 ST9 Vert Kiwi",
        categorie="egger_uni",
        couleur_rgb=[0.55, 0.62, 0.30],
        texture_diffuse=_chemin_texture("egger/U626_ST9.jpg"),
        rugosite=0.35,
        specular=0.35,
    ),
    "EGGER U645 ST9 Vert Agave": creer_materiau(
        nom="EGGER U645 ST9 Vert Agave",
        categorie="egger_uni",
        couleur_rgb=[0.38, 0.50, 0.42],
        texture_diffuse=_chemin_texture("egger/U645_ST9.jpg"),
        rugosite=0.35,
        specular=0.35,
    ),
    "EGGER U114 ST9 Jaune Tournesol": creer_materiau(
        nom="EGGER U114 ST9 Jaune Tournesol",
        categorie="egger_uni",
        couleur_rgb=[0.92, 0.80, 0.25],
        texture_diffuse=_chemin_texture("egger/U114_ST9.jpg"),
        rugosite=0.35,
        specular=0.35,
    ),

    # =================================================================
    #  EGGER — Bois / Woodgrain decors
    # =================================================================
    "EGGER H1334 ST9 Chene Sorano Clair": creer_materiau(
        nom="EGGER H1334 ST9 Chene Sorano Clair",
        categorie="egger_bois",
        couleur_rgb=[0.78, 0.65, 0.45],
        texture_diffuse=_chemin_texture("egger/H1334_ST9.jpg"),
        texture_bump=_chemin_texture("egger/H1334_ST9_bump.jpg"),
        rugosite=0.40,
        specular=0.30,
    ),
    "EGGER H1145 ST10 Chene Bardolino Naturel": creer_materiau(
        nom="EGGER H1145 ST10 Chene Bardolino Naturel",
        categorie="egger_bois",
        couleur_rgb=[0.75, 0.60, 0.40],
        texture_diffuse=_chemin_texture("egger/H1145_ST10.jpg"),
        texture_bump=_chemin_texture("egger/H1145_ST10_bump.jpg"),
        rugosite=0.42,
        specular=0.28,
    ),
    "EGGER H1180 ST37 Chene Halifax Naturel": creer_materiau(
        nom="EGGER H1180 ST37 Chene Halifax Naturel",
        categorie="egger_bois",
        couleur_rgb=[0.72, 0.58, 0.38],
        texture_diffuse=_chemin_texture("egger/H1180_ST37.jpg"),
        texture_bump=_chemin_texture("egger/H1180_ST37_bump.jpg"),
        rugosite=0.50,
        specular=0.25,
    ),
    "EGGER H3303 ST10 Chene Hamilton Naturel": creer_materiau(
        nom="EGGER H3303 ST10 Chene Hamilton Naturel",
        categorie="egger_bois",
        couleur_rgb=[0.68, 0.52, 0.32],
        texture_diffuse=_chemin_texture("egger/H3303_ST10.jpg"),
        texture_bump=_chemin_texture("egger/H3303_ST10_bump.jpg"),
        rugosite=0.45,
        specular=0.28,
    ),
    "EGGER H3309 ST28 Chene Gladstone Sable": creer_materiau(
        nom="EGGER H3309 ST28 Chene Gladstone Sable",
        categorie="egger_bois",
        couleur_rgb=[0.72, 0.60, 0.42],
        texture_diffuse=_chemin_texture("egger/H3309_ST28.jpg"),
        texture_bump=_chemin_texture("egger/H3309_ST28_bump.jpg"),
        rugosite=0.48,
        specular=0.25,
    ),
    "EGGER H3349 ST19 Chene Kaisersberg": creer_materiau(
        nom="EGGER H3349 ST19 Chene Kaisersberg",
        categorie="egger_bois",
        couleur_rgb=[0.62, 0.48, 0.30],
        texture_diffuse=_chemin_texture("egger/H3349_ST19.jpg"),
        texture_bump=_chemin_texture("egger/H3349_ST19_bump.jpg"),
        rugosite=0.45,
        specular=0.28,
    ),
    "EGGER H3157 ST12 Chene Vicenza": creer_materiau(
        nom="EGGER H3157 ST12 Chene Vicenza",
        categorie="egger_bois",
        couleur_rgb=[0.58, 0.48, 0.35],
        texture_diffuse=_chemin_texture("egger/H3157_ST12.jpg"),
        texture_bump=_chemin_texture("egger/H3157_ST12_bump.jpg"),
        rugosite=0.42,
        specular=0.28,
    ),
    "EGGER H3158 ST19 Chene Vicenza Gris": creer_materiau(
        nom="EGGER H3158 ST19 Chene Vicenza Gris",
        categorie="egger_bois",
        couleur_rgb=[0.55, 0.50, 0.42],
        texture_diffuse=_chemin_texture("egger/H3158_ST19.jpg"),
        texture_bump=_chemin_texture("egger/H3158_ST19_bump.jpg"),
        rugosite=0.45,
        specular=0.28,
    ),
    "EGGER H3368 ST9 Chene Lancaster Naturel": creer_materiau(
        nom="EGGER H3368 ST9 Chene Lancaster Naturel",
        categorie="egger_bois",
        couleur_rgb=[0.70, 0.55, 0.35],
        texture_diffuse=_chemin_texture("egger/H3368_ST9.jpg"),
        texture_bump=_chemin_texture("egger/H3368_ST9_bump.jpg"),
        rugosite=0.40,
        specular=0.30,
    ),
    "EGGER H3395 ST12 Chene Corbridge Naturel": creer_materiau(
        nom="EGGER H3395 ST12 Chene Corbridge Naturel",
        categorie="egger_bois",
        couleur_rgb=[0.65, 0.50, 0.32],
        texture_diffuse=_chemin_texture("egger/H3395_ST12.jpg"),
        texture_bump=_chemin_texture("egger/H3395_ST12_bump.jpg"),
        rugosite=0.42,
        specular=0.28,
    ),
    "EGGER H1344 ST32 Chene Sherman Cognac": creer_materiau(
        nom="EGGER H1344 ST32 Chene Sherman Cognac",
        categorie="egger_bois",
        couleur_rgb=[0.55, 0.38, 0.22],
        texture_diffuse=_chemin_texture("egger/H1344_ST32.jpg"),
        texture_bump=_chemin_texture("egger/H1344_ST32_bump.jpg"),
        rugosite=0.48,
        specular=0.25,
    ),
    "EGGER H3003 ST19 Chene Norwich": creer_materiau(
        nom="EGGER H3003 ST19 Chene Norwich",
        categorie="egger_bois",
        couleur_rgb=[0.50, 0.38, 0.25],
        texture_diffuse=_chemin_texture("egger/H3003_ST19.jpg"),
        texture_bump=_chemin_texture("egger/H3003_ST19_bump.jpg"),
        rugosite=0.45,
        specular=0.28,
    ),
    "EGGER H3430 ST22 Pin Aland Blanc": creer_materiau(
        nom="EGGER H3430 ST22 Pin Aland Blanc",
        categorie="egger_bois",
        couleur_rgb=[0.85, 0.78, 0.65],
        texture_diffuse=_chemin_texture("egger/H3430_ST22.jpg"),
        texture_bump=_chemin_texture("egger/H3430_ST22_bump.jpg"),
        rugosite=0.48,
        specular=0.25,
    ),
    "EGGER H3450 ST22 Fleetwood Blanc": creer_materiau(
        nom="EGGER H3450 ST22 Fleetwood Blanc",
        categorie="egger_bois",
        couleur_rgb=[0.82, 0.75, 0.62],
        texture_diffuse=_chemin_texture("egger/H3450_ST22.jpg"),
        texture_bump=_chemin_texture("egger/H3450_ST22_bump.jpg"),
        rugosite=0.48,
        specular=0.25,
    ),
    "EGGER H3840 ST9 Erable Mandal Naturel": creer_materiau(
        nom="EGGER H3840 ST9 Erable Mandal Naturel",
        categorie="egger_bois",
        couleur_rgb=[0.85, 0.75, 0.58],
        texture_diffuse=_chemin_texture("egger/H3840_ST9.jpg"),
        texture_bump=_chemin_texture("egger/H3840_ST9_bump.jpg"),
        rugosite=0.40,
        specular=0.30,
    ),
    "EGGER H1277 ST9 Acacia Lakeland Creme": creer_materiau(
        nom="EGGER H1277 ST9 Acacia Lakeland Creme",
        categorie="egger_bois",
        couleur_rgb=[0.82, 0.72, 0.55],
        texture_diffuse=_chemin_texture("egger/H1277_ST9.jpg"),
        texture_bump=_chemin_texture("egger/H1277_ST9_bump.jpg"),
        rugosite=0.40,
        specular=0.30,
    ),
    "EGGER H3734 ST9 Noyer Bourgogne Naturel": creer_materiau(
        nom="EGGER H3734 ST9 Noyer Bourgogne Naturel",
        categorie="egger_bois",
        couleur_rgb=[0.45, 0.30, 0.18],
        texture_diffuse=_chemin_texture("egger/H3734_ST9.jpg"),
        texture_bump=_chemin_texture("egger/H3734_ST9_bump.jpg"),
        rugosite=0.40,
        specular=0.35,
    ),
    "EGGER H3702 ST10 Noyer Pacifique Tabac": creer_materiau(
        nom="EGGER H3702 ST10 Noyer Pacifique Tabac",
        categorie="egger_bois",
        couleur_rgb=[0.40, 0.28, 0.15],
        texture_diffuse=_chemin_texture("egger/H3702_ST10.jpg"),
        texture_bump=_chemin_texture("egger/H3702_ST10_bump.jpg"),
        rugosite=0.42,
        specular=0.32,
    ),
    "EGGER H1715 ST12 Noyer Parona": creer_materiau(
        nom="EGGER H1715 ST12 Noyer Parona",
        categorie="egger_bois",
        couleur_rgb=[0.42, 0.30, 0.18],
        texture_diffuse=_chemin_texture("egger/H1715_ST12.jpg"),
        texture_bump=_chemin_texture("egger/H1715_ST12_bump.jpg"),
        rugosite=0.42,
        specular=0.32,
    ),
    "EGGER H1227 TM12 Frene Abano Marron": creer_materiau(
        nom="EGGER H1227 TM12 Frene Abano Marron",
        categorie="egger_bois",
        couleur_rgb=[0.48, 0.35, 0.22],
        texture_diffuse=_chemin_texture("egger/H1227_TM12.jpg"),
        texture_bump=_chemin_texture("egger/H1227_TM12_bump.jpg"),
        rugosite=0.38,
        specular=0.30,
    ),

    # =================================================================
    #  EGGER — Matieres / Material decors
    # =================================================================
    "EGGER F243 ST76 Marbre Candela Gris Clair": creer_materiau(
        nom="EGGER F243 ST76 Marbre Candela Gris Clair",
        categorie="egger_matiere",
        couleur_rgb=[0.82, 0.80, 0.78],
        texture_diffuse=_chemin_texture("egger/F243_ST76.jpg"),
        texture_bump=_chemin_texture("egger/F243_ST76_bump.jpg"),
        rugosite=0.20,
        specular=0.55,
    ),
    "EGGER F685 ST10 Acapulco": creer_materiau(
        nom="EGGER F685 ST10 Acapulco",
        categorie="egger_matiere",
        couleur_rgb=[0.72, 0.70, 0.65],
        texture_diffuse=_chemin_texture("egger/F685_ST10.jpg"),
        texture_bump=_chemin_texture("egger/F685_ST10_bump.jpg"),
        rugosite=0.45,
        specular=0.30,
    ),

    # =================================================================
    #  Generiques (bois massif non EGGER)
    # =================================================================
    "Chene clair": creer_materiau(
        nom="Chene clair",
        categorie="bois",
        couleur_rgb=[0.82, 0.71, 0.55],
        texture_diffuse=_chemin_texture("chene_clair_diffuse.jpg"),
        texture_bump=_chemin_texture("chene_clair_bump.jpg"),
        rugosite=0.45,
        specular=0.3,
    ),
    "Chene fonce": creer_materiau(
        nom="Chene fonce",
        categorie="bois",
        couleur_rgb=[0.55, 0.38, 0.22],
        texture_diffuse=_chemin_texture("chene_fonce_diffuse.jpg"),
        texture_bump=_chemin_texture("chene_fonce_bump.jpg"),
        rugosite=0.45,
        specular=0.3,
    ),
    "Noyer": creer_materiau(
        nom="Noyer",
        categorie="bois",
        couleur_rgb=[0.40, 0.26, 0.15],
        texture_diffuse=_chemin_texture("noyer_diffuse.jpg"),
        texture_bump=_chemin_texture("noyer_bump.jpg"),
        rugosite=0.40,
        specular=0.35,
    ),
    "Hetre": creer_materiau(
        nom="Hetre",
        categorie="bois",
        couleur_rgb=[0.87, 0.74, 0.53],
        texture_diffuse=_chemin_texture("hetre_diffuse.jpg"),
        texture_bump=_chemin_texture("hetre_bump.jpg"),
        rugosite=0.45,
        specular=0.3,
    ),
    "Erable": creer_materiau(
        nom="Erable",
        categorie="bois",
        couleur_rgb=[0.90, 0.82, 0.68],
        texture_diffuse=_chemin_texture("erable_diffuse.jpg"),
        texture_bump=_chemin_texture("erable_bump.jpg"),
        rugosite=0.40,
        specular=0.35,
    ),
    "Pin": creer_materiau(
        nom="Pin",
        categorie="bois",
        couleur_rgb=[0.88, 0.78, 0.58],
        texture_diffuse=_chemin_texture("pin_diffuse.jpg"),
        texture_bump=_chemin_texture("pin_bump.jpg"),
        rugosite=0.50,
        specular=0.25,
    ),

    # =================================================================
    #  Generiques — Melamine / Stratifie
    # =================================================================
    "Blanc brillant": creer_materiau(
        nom="Blanc brillant",
        categorie="melamine",
        couleur_rgb=[0.95, 0.95, 0.95],
        texture_diffuse=_chemin_texture("blanc_brillant_diffuse.jpg"),
        rugosite=0.15,
        specular=0.7,
    ),
    "Blanc mat": creer_materiau(
        nom="Blanc mat",
        categorie="melamine",
        couleur_rgb=[0.92, 0.92, 0.92],
        texture_diffuse=_chemin_texture("blanc_mat_diffuse.jpg"),
        rugosite=0.60,
        specular=0.2,
    ),
    "Gris anthracite": creer_materiau(
        nom="Gris anthracite",
        categorie="melamine",
        couleur_rgb=[0.25, 0.25, 0.28],
        texture_diffuse=_chemin_texture("gris_anthracite_diffuse.jpg"),
        rugosite=0.50,
        specular=0.4,
    ),
    "Noir mat": creer_materiau(
        nom="Noir mat",
        categorie="melamine",
        couleur_rgb=[0.10, 0.10, 0.10],
        texture_diffuse=_chemin_texture("noir_mat_diffuse.jpg"),
        rugosite=0.65,
        specular=0.15,
    ),

    # =================================================================
    #  Metal
    # =================================================================
    "Acier inox": creer_materiau(
        nom="Acier inox",
        categorie="metal",
        couleur_rgb=[0.75, 0.75, 0.78],
        texture_diffuse=_chemin_texture("inox_diffuse.jpg"),
        texture_bump=_chemin_texture("inox_bump.jpg"),
        rugosite=0.25,
        metallic=0.9,
        specular=0.8,
    ),
    "Aluminium brosse": creer_materiau(
        nom="Aluminium brosse",
        categorie="metal",
        couleur_rgb=[0.80, 0.80, 0.82],
        texture_diffuse=_chemin_texture("alu_brosse_diffuse.jpg"),
        texture_bump=_chemin_texture("alu_brosse_bump.jpg"),
        rugosite=0.35,
        metallic=0.85,
        specular=0.7,
    ),
    "Acier galvanise": creer_materiau(
        nom="Acier galvanise",
        categorie="metal",
        couleur_rgb=[0.63, 0.63, 0.63],
        texture_diffuse=_chemin_texture("acier_galvanise_diffuse.jpg"),
        rugosite=0.50,
        metallic=0.7,
        specular=0.5,
    ),

    # =================================================================
    #  Mur / Sol (contexte)
    # =================================================================
    "Mur blanc": creer_materiau(
        nom="Mur blanc",
        categorie="mur",
        couleur_rgb=[0.90, 0.90, 0.88],
        texture_diffuse=_chemin_texture("mur_blanc_diffuse.jpg"),
        texture_bump=_chemin_texture("mur_blanc_bump.jpg"),
        rugosite=0.80,
        specular=0.1,
    ),
    "Sol parquet": creer_materiau(
        nom="Sol parquet",
        categorie="sol",
        couleur_rgb=[0.65, 0.50, 0.32],
        texture_diffuse=_chemin_texture("parquet_diffuse.jpg"),
        texture_bump=_chemin_texture("parquet_bump.jpg"),
        rugosite=0.35,
        specular=0.45,
    ),
    "Sol carrelage": creer_materiau(
        nom="Sol carrelage",
        categorie="sol",
        couleur_rgb=[0.85, 0.85, 0.82],
        texture_diffuse=_chemin_texture("carrelage_diffuse.jpg"),
        texture_bump=_chemin_texture("carrelage_bump.jpg"),
        rugosite=0.20,
        specular=0.6,
    ),
}


# =====================================================================
#  Mapping type d'element -> materiau par defaut
# =====================================================================

MATERIAUX_DEFAUT_PLACARD: dict[str, str] = {
    "panneau_separation": "Chene clair",
    "panneau_rayon": "Chene clair",
    "panneau_rayon_haut": "Chene clair",
    "panneau_mur": "Chene clair",
    "cremaillere_encastree": "Acier galvanise",
    "cremaillere_applique": "Acier galvanise",
    "tasseau": "Chene clair",
    "mur": "Mur blanc",
    "sol": "Sol carrelage",
}

MATERIAUX_DEFAUT_MEUBLE: dict[str, str] = {
    "flanc": "Chene clair",
    "dessus": "Chene clair",
    "dessous": "Chene clair",
    "traverse": "Chene clair",
    "separation": "Chene clair",
    "fond": "Chene clair",
    "etagere": "Chene clair",
    "plinthe": "Noir mat",
    "cremaillere": "Aluminium brosse",
    "porte": "Blanc brillant",
    "tiroir": "Blanc brillant",
    "poignee": "Acier inox",
}


# =====================================================================
#  Fonctions utilitaires
# =====================================================================

def get_materiau(nom: str) -> Optional[dict]:
    """Retourne un materiau du catalogue par son nom.

    Args:
        nom: Nom du materiau recherche.

    Returns:
        Copie du dictionnaire materiau, ou None si non trouve.
    """
    mat = CATALOGUE_MATERIAUX.get(nom)
    if mat:
        return copy.deepcopy(mat)
    return None


def lister_materiaux_par_categorie(categorie: str | None = None) -> list[dict]:
    """Liste les materiaux du catalogue, optionnellement filtres par categorie.

    Args:
        categorie: Categorie a filtrer ('bois', 'metal', 'melamine', etc.)
            ou None pour tout lister.

    Returns:
        Liste de dictionnaires materiaux tries par nom.
    """
    result = []
    for mat in CATALOGUE_MATERIAUX.values():
        if categorie is None or mat["categorie"] == categorie:
            result.append(copy.deepcopy(mat))
    result.sort(key=lambda m: m["nom"])
    return result


def lister_categories() -> list[str]:
    """Retourne la liste des categories de materiaux disponibles.

    Returns:
        Liste triee des categories uniques.
    """
    cats = set()
    for mat in CATALOGUE_MATERIAUX.values():
        cats.add(mat["categorie"])
    return sorted(cats)


def get_couleur_rgb(nom_materiau: str) -> list[float]:
    """Retourne la couleur RGB d'un materiau ou une couleur par defaut.

    Args:
        nom_materiau: Nom du materiau.

    Returns:
        Liste [R, G, B] en 0.0-1.0.
    """
    mat = CATALOGUE_MATERIAUX.get(nom_materiau)
    if mat:
        return list(mat["couleur_rgb"])
    return [0.8, 0.8, 0.8]


def get_chemin_texture_absolu(chemin_relatif: str) -> Path:
    """Convertit un chemin de texture relatif en chemin absolu.

    Args:
        chemin_relatif: Chemin relatif (ex. 'textures/chene_clair_diffuse.jpg').

    Returns:
        Chemin absolu vers le fichier texture.
    """
    return Path(__file__).parent / "resources" / chemin_relatif


def texture_existe(chemin_relatif: str) -> bool:
    """Verifie si un fichier de texture existe sur le disque.

    Args:
        chemin_relatif: Chemin relatif de la texture.

    Returns:
        True si le fichier existe.
    """
    if not chemin_relatif:
        return False
    return get_chemin_texture_absolu(chemin_relatif).exists()


# =====================================================================
#  Generation de fichier materiau FreeCAD (.FCMat)
# =====================================================================

def generer_fcmat(materiau: dict) -> str:
    """Genere le contenu d'un fichier .FCMat pour le Render Workbench.

    Le format .FCMat est un fichier INI avec des sections [General],
    [Rendering] et [Textures] reconnu par FreeCAD.

    Args:
        materiau: Dictionnaire materiau.

    Returns:
        Contenu texte du fichier .FCMat.
    """
    r, g, b = materiau["couleur_rgb"]

    lines = [
        "; FreeCAD material card — genere par PlacardCAD",
        f"; Materiau: {materiau['nom']}",
        "",
        "[General]",
        f"Name = {materiau['nom']}",
        f"Description = Materiau {materiau['categorie']} — {materiau['nom']}",
        "",
        "[Rendering]",
        f"Diffuse.Color = ({r:.4f}, {g:.4f}, {b:.4f})",
        f"Roughness = {materiau['rugosite']:.4f}",
        f"Metallic = {materiau['metallic']:.4f}",
        f"Specular = {materiau['specular']:.4f}",
        f"IOR = {materiau['ior']:.4f}",
        f"Transparency = {materiau['transparence']:.4f}",
    ]

    # Textures
    has_tex = any([
        materiau.get("texture_diffuse"),
        materiau.get("texture_bump"),
        materiau.get("texture_roughness"),
    ])
    if has_tex:
        lines.append("")
        lines.append("[Textures]")
        if materiau.get("texture_diffuse"):
            chemin = get_chemin_texture_absolu(materiau["texture_diffuse"])
            lines.append(f"Diffuse.Texture = {chemin}")
        if materiau.get("texture_bump"):
            chemin = get_chemin_texture_absolu(materiau["texture_bump"])
            lines.append(f"Bump.Texture = {chemin}")
        if materiau.get("texture_roughness"):
            chemin = get_chemin_texture_absolu(materiau["texture_roughness"])
            lines.append(f"Roughness.Texture = {chemin}")

    lines.append("")
    return "\n".join(lines)


def generer_script_render_materiaux(
    objets_materiaux: list[tuple[str, str]],
) -> str:
    """Genere un script Python FreeCAD pour appliquer les materiaux Render WB.

    Le script cree les materiaux dans FreeCAD et les assigne aux objets.
    Il est concu pour etre concatene au script de generation 3D existant.

    Args:
        objets_materiaux: Liste de tuples (nom_objet_freecad, nom_materiau).

    Returns:
        Code source Python du script.
    """
    # Grouper par materiau pour eviter les doublons
    materiaux_utilises: dict[str, list[str]] = {}
    for nom_obj, nom_mat in objets_materiaux:
        materiaux_utilises.setdefault(nom_mat, []).append(nom_obj)

    lines = [
        "",
        "# --- Materiaux Render Workbench ---",
        "try:",
        "    import Render",
        "    _RENDER_OK = True",
        "except ImportError:",
        "    _RENDER_OK = False",
        "    print('Render Workbench non installe — materiaux ignores.')",
        "",
        "if _RENDER_OK:",
    ]

    for nom_mat, noms_objs in materiaux_utilises.items():
        mat = CATALOGUE_MATERIAUX.get(nom_mat)
        if not mat:
            continue

        r, g, b = mat["couleur_rgb"]
        mat_var = nom_mat.replace(" ", "_").replace("'", "")

        lines.append(f"    # Materiau: {nom_mat}")
        lines.append(f"    mat_{mat_var} = Render.Material()")
        lines.append(f"    mat_{mat_var}.Label = '{nom_mat}'")
        lines.append(
            f"    mat_{mat_var}.DiffuseColor = ({r:.4f}, {g:.4f}, {b:.4f})"
        )
        lines.append(f"    mat_{mat_var}.Roughness = {mat['rugosite']:.4f}")
        lines.append(f"    mat_{mat_var}.Metallic = {mat['metallic']:.4f}")

        if mat.get("texture_diffuse"):
            chemin = get_chemin_texture_absolu(mat["texture_diffuse"])
            lines.append(f"    mat_{mat_var}.DiffuseTexture = r'{chemin}'")
        if mat.get("texture_bump"):
            chemin = get_chemin_texture_absolu(mat["texture_bump"])
            lines.append(f"    mat_{mat_var}.BumpTexture = r'{chemin}'")

        for nom_obj in noms_objs:
            lines.append(
                f"    Render.assignMaterial(doc.getObject('{nom_obj}'), "
                f"mat_{mat_var})"
            )
        lines.append("")

    lines.append("    doc.recompute()")
    lines.append("")

    return "\n".join(lines)
