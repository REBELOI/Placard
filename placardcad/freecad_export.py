"""
Export FreeCAD pour PlacardCAD.

Genere un fichier .FCStd (format natif FreeCAD) contenant le placard en 3D.
Le fichier FCStd est une archive ZIP contenant Document.xml et GuiDocument.xml
avec des objets Part::Box parametriques.

A l'ouverture dans FreeCAD, selectionner tout (Ctrl+A) puis
Edit > Refresh (Ctrl+Shift+R) pour recalculer les formes.

Convention d'axes FreeCAD:
  X = largeur (gauche -> droite)
  Y = profondeur (face avant -> mur du fond)
  Z = hauteur (sol -> plafond)
"""

import uuid
import zipfile
from datetime import datetime
from xml.sax.saxutils import escape as xml_escape

from .placard_builder import generer_geometrie_2d


# Couleurs RGB par type d'element (valeurs 0.0 - 1.0)
COULEURS_3D = {
    "separation": (0.82, 0.71, 0.55),
    "rayon_haut": (0.87, 0.74, 0.53),
    "rayon": (0.82, 0.71, 0.55),
    "panneau_mur": (0.82, 0.71, 0.55),
    "cremaillere_encastree": (0.63, 0.63, 0.63),
    "cremaillere_applique": (0.80, 0.00, 0.00),
    "tasseau": (0.85, 0.65, 0.13),
}


def _profondeur_element(type_elem: str, config: dict) -> tuple[float, float]:
    """Retourne (profondeur_mm, y_offset_mm) pour un type d'element.

    Y=0 est la face avant visible du placard, Y=P le mur du fond.
    """
    P = config["profondeur"]

    if type_elem == "mur":
        return 0, 0

    elif type_elem == "separation":
        chant = config["panneau_separation"].get("chant_epaisseur", 0)
        return P - chant, 0

    elif type_elem == "rayon_haut":
        retrait_av = config["panneau_rayon_haut"].get("retrait_avant", 0)
        retrait_ar = config["panneau_rayon_haut"].get("retrait_arriere", 0)
        chant = config["panneau_rayon_haut"].get("chant_epaisseur", 0)
        depth = P - chant - retrait_av - retrait_ar
        return depth, retrait_av

    elif type_elem == "rayon":
        retrait_av = config["panneau_rayon"].get("retrait_avant", 0)
        retrait_ar = config["panneau_rayon"].get("retrait_arriere", 0)
        chant = config["panneau_rayon"].get("chant_epaisseur", 0)
        depth = P - chant - retrait_av - retrait_ar
        return depth, retrait_av

    elif type_elem == "panneau_mur":
        chant = config["panneau_mur"].get("chant_epaisseur", 0)
        return P - chant, 0

    elif type_elem == "cremaillere_encastree":
        retrait_av = config["crem_encastree"].get("retrait_avant", 80)
        retrait_ar = config["crem_encastree"].get("retrait_arriere", 80)
        depth = P - retrait_av - retrait_ar
        return depth, retrait_av

    elif type_elem == "cremaillere_applique":
        retrait_av = config["crem_applique"].get("retrait_avant", 80)
        retrait_ar = config["crem_applique"].get("retrait_arriere", 80)
        depth = P - retrait_av - retrait_ar
        return depth, retrait_av

    elif type_elem == "tasseau":
        retrait_av = config["tasseau"].get("retrait_avant", 20)
        chant_rayon = config["panneau_rayon"].get("chant_epaisseur", 0)
        longueur = P - chant_rayon - retrait_av
        return longueur, retrait_av

    else:
        return P * 0.5, P * 0.25


def _nom_freecad(label: str, idx: int, type_elem: str) -> str:
    """Nettoie un label pour en faire un nom FreeCAD valide."""
    nom = label or f"{type_elem}_{idx + 1}"
    # Remplacer les caracteres non valides
    for ch in " /.-()+'\"":
        nom = nom.replace(ch, "_")
    return nom


def _nom_unique(nom: str, noms_utilises: set[str]) -> str:
    """Assure l'unicite du nom en ajoutant un suffixe numerique si necessaire."""
    if nom not in noms_utilises:
        noms_utilises.add(nom)
        return nom
    i = 2
    while f"{nom}_{i}" in noms_utilises:
        i += 1
    nom_u = f"{nom}_{i}"
    noms_utilises.add(nom_u)
    return nom_u


def _couleur_packed(rgb: tuple[float, float, float]) -> int:
    """Encode une couleur RGB (0.0-1.0) en uint32 RGBA pour FreeCAD.

    Format: (R<<24) | (G<<16) | (B<<8) | A
    Alpha=0 signifie opaque dans FreeCAD.
    """
    r = min(255, max(0, int(round(rgb[0] * 255))))
    g = min(255, max(0, int(round(rgb[1] * 255))))
    b = min(255, max(0, int(round(rgb[2] * 255))))
    return (r << 24) | (g << 16) | (b << 8)


def _collecter_objets_3d(config: dict) -> list[dict]:
    """Collecte tous les objets 3D a partir de la configuration du placard.

    Retourne une liste de dicts avec: nom, label, length, width, height,
    px, py, pz, couleur, transparence.
    """
    rects, _fiche = generer_geometrie_2d(config)

    H = config["hauteur"]
    L = config["largeur"]
    P = config["profondeur"]

    objets = []
    noms_utilises: set[str] = set()

    # Elements du placard (hors murs)
    elements = [r for r in rects if r.type_elem != "mur"]
    grouped: dict[str, list] = {}
    for r in elements:
        grouped.setdefault(r.type_elem, []).append(r)

    ordre = [
        "panneau_mur", "separation", "rayon_haut", "rayon",
        "cremaillere_encastree", "cremaillere_applique", "tasseau",
    ]

    for type_elem in ordre:
        if type_elem not in grouped:
            continue

        group_rects = grouped[type_elem]
        couleur = COULEURS_3D.get(type_elem, (0.8, 0.7, 0.55))
        profondeur, y_offset = _profondeur_element(type_elem, config)

        if profondeur <= 0:
            continue

        transparence = 40 if type_elem.startswith("cremaillere") else 0

        for i, r in enumerate(group_rects):
            nom_base = _nom_freecad(r.label, i, type_elem)
            nom = _nom_unique(nom_base, noms_utilises)
            # 2D rect: x=X pos, y=Z pos, w=X size, h=Z size
            # 3D box: Length=X, Width=Y (depth), Height=Z
            objets.append({
                "nom": nom,
                "label": r.label or nom,
                "length": r.w,
                "width": profondeur,
                "height": r.h,
                "px": r.x,
                "py": y_offset,
                "pz": r.y,
                "couleur": couleur,
                "transparence": transparence,
            })

    # Murs (contexte transparent)
    mur_ep = config.get("mur_epaisseur", 50)
    mur_couleur = (0.90, 0.90, 0.88)
    sol_couleur = (0.85, 0.85, 0.82)

    for nom, dims, pos, couleur in [
        ("Mur_gauche", (mur_ep, P, H), (-mur_ep, 0, 0), mur_couleur),
        ("Mur_droit", (mur_ep, P, H), (L, 0, 0), mur_couleur),
        ("Mur_fond", (L + 2 * mur_ep, mur_ep, H), (-mur_ep, P, 0), mur_couleur),
        ("Sol", (L + 2 * mur_ep, P + mur_ep, mur_ep),
         (-mur_ep, 0, -mur_ep), sol_couleur),
    ]:
        objets.append({
            "nom": _nom_unique(nom, noms_utilises),
            "label": nom.replace("_", " "),
            "length": dims[0],
            "width": dims[1],
            "height": dims[2],
            "px": pos[0],
            "py": pos[1],
            "pz": pos[2],
            "couleur": couleur,
            "transparence": 70,
        })

    return objets


# =====================================================================
#  Generation XML
# =====================================================================

def _generer_document_xml(objets: list[dict]) -> bytes:
    """Genere le contenu Document.xml du fichier FCStd.

    Construit le XML par formatage de chaines pour correspondre exactement
    au format attendu par le parser Xerces-C de FreeCAD.
    """
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<Document SchemaVersion="4" ProgramVersion="0.21.0" FileVersion="1">',
        '<Properties Count="4">',
        '<Property name="CreatedBy" type="App::PropertyString">',
        '<String value="PlacardCAD"/></Property>',
        '<Property name="Label" type="App::PropertyString">',
        '<String value="Placard"/></Property>',
        '<Property name="CreationDate" type="App::PropertyString">',
        f'<String value="{datetime.now().isoformat()}"/></Property>',
        '<Property name="Uid" type="App::PropertyUUID">',
        f'<Uuid value="{uuid.uuid4()}"/></Property>',
        '</Properties>',
    ]

    # Liste des objets
    lines.append(f'<Objects Count="{len(objets)}">')
    for i, obj in enumerate(objets):
        lines.append(
            f'<Object type="Part::Box" name="{xml_escape(obj["nom"])}" id="{i}"/>'
        )
    lines.append('</Objects>')

    # Donnees des objets
    lines.append(f'<ObjectData Count="{len(objets)}">')
    for obj in objets:
        label = xml_escape(obj["label"], {'"': '&quot;'})
        lines.append(f'<Object name="{xml_escape(obj["nom"])}">')
        lines.append('<Properties Count="5">')

        # Label
        lines.append('<Property name="Label" type="App::PropertyString">')
        lines.append(f'<String value="{label}"/></Property>')

        # Length
        lines.append('<Property name="Length" type="App::PropertyLength">')
        lines.append(f'<Float value="{obj["length"]:.6f}"/></Property>')

        # Width
        lines.append('<Property name="Width" type="App::PropertyLength">')
        lines.append(f'<Float value="{obj["width"]:.6f}"/></Property>')

        # Height
        lines.append('<Property name="Height" type="App::PropertyLength">')
        lines.append(f'<Float value="{obj["height"]:.6f}"/></Property>')

        # Placement
        lines.append('<Property name="Placement" type="App::PropertyPlacement">')
        lines.append(
            f'<PropertyPlacement '
            f'Px="{obj["px"]:.15e}" Py="{obj["py"]:.15e}" Pz="{obj["pz"]:.15e}" '
            f'Q0="0.000000000000000e+0" Q1="0.000000000000000e+0" '
            f'Q2="0.000000000000000e+0" Q3="1.000000000000000e+0" '
            f'A="0.000000000000000e+0" '
            f'Ox="0.000000000000000e+0" Oy="0.000000000000000e+0" '
            f'Oz="1.000000000000000e+0"/></Property>')

        lines.append('</Properties>')
        lines.append('</Object>')

    lines.append('</ObjectData>')
    lines.append('</Document>')

    return '\n'.join(lines).encode("utf-8")


def _generer_guidocument_xml(objets: list[dict]) -> bytes:
    """Genere le contenu GuiDocument.xml du fichier FCStd.

    Construit le XML par formatage de chaines pour correspondre exactement
    au format attendu par le parser Xerces-C de FreeCAD.
    """
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<Document SchemaVersion="1" ProgramVersion="0.21.0" FileVersion="1">',
        f'<ViewProviderData Count="{len(objets)}">',
    ]

    for obj in objets:
        nom = xml_escape(obj["nom"])
        couleur = _couleur_packed(obj["couleur"])

        lines.append(f'<ViewProvider name="{nom}">')
        lines.append('<Properties Count="3">')

        # ShapeColor
        lines.append('<Property name="ShapeColor" type="App::PropertyColor">')
        lines.append(f'<PropertyColor value="{couleur}"/></Property>')

        # Transparency
        lines.append('<Property name="Transparency" type="App::PropertyPercent">')
        lines.append(f'<Integer value="{obj["transparence"]}"/></Property>')

        # Visibility
        lines.append('<Property name="Visibility" type="App::PropertyBool">')
        lines.append('<Bool value="true"/></Property>')

        lines.append('</Properties>')
        lines.append('</ViewProvider>')

    lines.append('</ViewProviderData>')
    lines.append('</Document>')

    return '\n'.join(lines).encode("utf-8")


# =====================================================================
#  Export
# =====================================================================

def exporter_freecad(filepath: str, config: dict) -> str:
    """Exporte le placard en fichier FreeCAD natif (.FCStd).

    Le fichier FCStd est une archive ZIP contenant Document.xml (modele
    parametrique) et GuiDocument.xml (proprietes visuelles).

    A l'ouverture dans FreeCAD, les formes seront recalculees
    automatiquement ou via Edit > Refresh (Ctrl+Shift+R).
    """
    objets = _collecter_objets_3d(config)

    doc_xml = _generer_document_xml(objets)
    gui_xml = _generer_guidocument_xml(objets)

    with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Document.xml", doc_xml)
        zf.writestr("GuiDocument.xml", gui_xml)

    return filepath
