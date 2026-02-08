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
from xml.etree.ElementTree import Element, SubElement, tostring, indent

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
    """Genere le contenu Document.xml du fichier FCStd."""
    root = Element("Document")
    root.set("SchemaVersion", "4")
    root.set("ProgramVersion", "0.21.0")
    root.set("FileVersion", "1")

    # --- Proprietes du document ---
    doc_props = SubElement(root, "Properties")
    doc_props.set("Count", "4")

    p = SubElement(doc_props, "Property")
    p.set("name", "CreatedBy")
    p.set("type", "App::PropertyString")
    SubElement(p, "String").set("value", "PlacardCAD")

    p = SubElement(doc_props, "Property")
    p.set("name", "Label")
    p.set("type", "App::PropertyString")
    SubElement(p, "String").set("value", "Placard")

    p = SubElement(doc_props, "Property")
    p.set("name", "CreationDate")
    p.set("type", "App::PropertyString")
    SubElement(p, "String").set("value", datetime.now().isoformat())

    p = SubElement(doc_props, "Property")
    p.set("name", "Uid")
    p.set("type", "App::PropertyUUID")
    SubElement(p, "Uuid").set("value", str(uuid.uuid4()))

    # --- Liste des objets ---
    objects_elem = SubElement(root, "Objects")
    objects_elem.set("Count", str(len(objets)))

    for i, obj in enumerate(objets):
        o = SubElement(objects_elem, "Object")
        o.set("type", "Part::Box")
        o.set("name", obj["nom"])
        o.set("id", str(i))

    # --- Donnees des objets ---
    objdata = SubElement(root, "ObjectData")
    objdata.set("Count", str(len(objets)))

    for obj in objets:
        o = SubElement(objdata, "Object")
        o.set("name", obj["nom"])

        props = SubElement(o, "Properties")
        props.set("Count", "5")

        # Label (nom affiche)
        p = SubElement(props, "Property")
        p.set("name", "Label")
        p.set("type", "App::PropertyString")
        SubElement(p, "String").set("value", obj["label"])

        # Length (X)
        p = SubElement(props, "Property")
        p.set("name", "Length")
        p.set("type", "App::PropertyLength")
        SubElement(p, "Float").set("value", f"{obj['length']:.2f}")

        # Width (Y)
        p = SubElement(props, "Property")
        p.set("name", "Width")
        p.set("type", "App::PropertyLength")
        SubElement(p, "Float").set("value", f"{obj['width']:.2f}")

        # Height (Z)
        p = SubElement(props, "Property")
        p.set("name", "Height")
        p.set("type", "App::PropertyLength")
        SubElement(p, "Float").set("value", f"{obj['height']:.2f}")

        # Placement (position + rotation identite)
        p = SubElement(props, "Property")
        p.set("name", "Placement")
        p.set("type", "App::PropertyPlacement")
        pl = SubElement(p, "PropertyPlacement")
        pl.set("Px", f"{obj['px']:.15e}")
        pl.set("Py", f"{obj['py']:.15e}")
        pl.set("Pz", f"{obj['pz']:.15e}")
        pl.set("Q0", "0.000000000000000e+0")
        pl.set("Q1", "0.000000000000000e+0")
        pl.set("Q2", "0.000000000000000e+0")
        pl.set("Q3", "1.000000000000000e+0")
        pl.set("A", "0.000000000000000e+0")
        pl.set("Ox", "0.000000000000000e+0")
        pl.set("Oy", "0.000000000000000e+0")
        pl.set("Oz", "1.000000000000000e+0")

    indent(root)
    xml_str = tostring(root, encoding="unicode")
    return ('<?xml version="1.0" encoding="utf-8"?>\n' + xml_str).encode("utf-8")


def _generer_guidocument_xml(objets: list[dict]) -> bytes:
    """Genere le contenu GuiDocument.xml du fichier FCStd."""
    root = Element("Document")
    root.set("SchemaVersion", "1")

    vpdata = SubElement(root, "ViewProviderData")
    vpdata.set("Count", str(len(objets)))

    for obj in objets:
        vp = SubElement(vpdata, "ViewProvider")
        vp.set("name", obj["nom"])

        props = SubElement(vp, "Properties")
        props.set("Count", "3")

        # ShapeColor (uint32 RGBA)
        p = SubElement(props, "Property")
        p.set("name", "ShapeColor")
        p.set("type", "App::PropertyColor")
        SubElement(p, "PropertyColor").set(
            "value", str(_couleur_packed(obj["couleur"]))
        )

        # Transparency (0-100)
        p = SubElement(props, "Property")
        p.set("name", "Transparency")
        p.set("type", "App::PropertyPercent")
        SubElement(p, "Integer").set("value", str(obj["transparence"]))

        # Visibility
        p = SubElement(props, "Property")
        p.set("name", "Visibility")
        p.set("type", "App::PropertyBool")
        SubElement(p, "Bool").set("value", "true")

    indent(root)
    xml_str = tostring(root, encoding="unicode")
    return ('<?xml version="1.0" encoding="utf-8"?>\n' + xml_str).encode("utf-8")


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
