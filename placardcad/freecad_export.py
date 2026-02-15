"""Export FreeCAD pour PlacardCAD.

Genere un fichier .FCStd (format natif FreeCAD) contenant le placard ou
meuble en 3D. Le fichier FCStd est une archive ZIP contenant Document.xml
et GuiDocument.xml avec des objets Part::Box parametriques.

A l'ouverture dans FreeCAD, selectionner tout (Ctrl+A) puis
Edit > Refresh (Ctrl+Shift+R) pour recalculer les formes.

Convention d'axes FreeCAD:
    - X = largeur (gauche vers droite).
    - Y = profondeur (face avant vers mur du fond).
    - Z = hauteur (sol vers plafond).

Fonctions:
    - exporter_freecad: export placard en .FCStd.
    - exporter_freecad_meuble: export meuble en .FCStd.
"""

import math
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
    """Calcule la profondeur et le decalage Y pour un type d'element du placard.

    Chaque type d'element (separation, rayon, cremaillere, etc.) a une
    profondeur et un positionnement en Y specifiques, determines par les
    parametres de configuration (retraits, chants, etc.).

    Y=0 est la face avant visible du placard, Y=P le mur du fond.

    Args:
        type_elem: Type de l'element ('separation', 'rayon', 'rayon_haut',
            'panneau_mur', 'cremaillere_encastree', 'cremaillere_applique',
            'tasseau', 'mur').
        config: Dictionnaire de configuration du placard contenant les
            parametres de profondeur, retraits et chants par type d'element.

    Returns:
        Tuple (profondeur_mm, y_offset_mm) ou profondeur_mm est la dimension
        de l'element selon l'axe Y et y_offset_mm le decalage depuis la
        face avant.
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
    """Nettoie un label pour en faire un nom d'objet FreeCAD valide.

    Remplace les caracteres non autorises (espaces, slashs, points, etc.)
    par des underscores. Si le label est vide, genere un nom a partir
    du type d'element et de l'index.

    Args:
        label: Label d'origine de l'element.
        idx: Index de l'element dans sa liste (utilise si label est vide).
        type_elem: Type de l'element (utilise si label est vide).

    Returns:
        Nom nettoye utilisable comme identifiant d'objet FreeCAD.
    """
    nom = label or f"{type_elem}_{idx + 1}"
    # Remplacer les caracteres non valides
    for ch in " /.-()+'\"":
        nom = nom.replace(ch, "_")
    return nom


def _nom_unique(nom: str, noms_utilises: set[str]) -> str:
    """Assure l'unicite du nom en ajoutant un suffixe numerique si necessaire.

    Si le nom existe deja dans l'ensemble, ajoute un suffixe _2, _3, etc.
    jusqu'a trouver un nom disponible. Le nom retourne est ajoute a
    l'ensemble des noms utilises.

    Args:
        nom: Nom de base a rendre unique.
        noms_utilises: Ensemble mutable des noms deja attribues.

    Returns:
        Nom garanti unique, identique a nom si disponible, sinon avec
        suffixe numerique.
    """
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
    """Encode une couleur RGB en entier uint32 RGBA pour FreeCAD.

    Le format est (R<<24) | (G<<16) | (B<<8) | A, ou Alpha=0 signifie
    opaque dans la convention FreeCAD.

    Args:
        rgb: Tuple de 3 flottants (R, G, B) dans l'intervalle [0.0, 1.0].

    Returns:
        Entier uint32 representant la couleur au format RGBA FreeCAD.
    """
    r = min(255, max(0, int(round(rgb[0] * 255))))
    g = min(255, max(0, int(round(rgb[1] * 255))))
    b = min(255, max(0, int(round(rgb[2] * 255))))
    return (r << 24) | (g << 16) | (b << 8)


def _collecter_objets_3d(config: dict) -> list[dict]:
    """Collecte tous les objets 3D a partir de la configuration du placard.

    Genere la geometrie 2D via le builder, puis convertit chaque rectangle
    en objet 3D en calculant la profondeur selon le type d'element.
    Ajoute egalement les murs et le sol comme elements de contexte
    transparents.

    Args:
        config: Dictionnaire de configuration complet du placard (schema
            parse + parametres physiques).

    Returns:
        Liste de dictionnaires, chacun representant un objet 3D avec les cles:
            - nom: str - nom unique de l'objet FreeCAD.
            - label: str - label affiche dans FreeCAD.
            - length: float - dimension selon X en mm.
            - width: float - dimension selon Y (profondeur) en mm.
            - height: float - dimension selon Z en mm.
            - px, py, pz: float - position du coin d'origine en mm.
            - couleur: tuple[float, float, float] - couleur RGB [0-1].
            - transparence: int - pourcentage de transparence (0=opaque).
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
    au format attendu par le parser Xerces-C de FreeCAD. Chaque objet est
    declare comme Part::Box avec ses proprietes Label, Length, Width,
    Height et Placement.

    Args:
        objets: Liste de dictionnaires representant les objets 3D, tels que
            retournes par _collecter_objets_3d.

    Returns:
        Contenu XML du Document.xml encode en UTF-8.
    """
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<Document SchemaVersion="4" ProgramVersion="0.21.0" FileVersion="1">',
        '<Properties Count="4">',
        '<Property name="CreatedBy" type="App::PropertyString">',
        '<String value="PlacardCAD"/>',
        '</Property>',
        '<Property name="Label" type="App::PropertyString">',
        '<String value="Placard"/>',
        '</Property>',
        '<Property name="CreationDate" type="App::PropertyString">',
        f'<String value="{datetime.now().isoformat()}"/>',
        '</Property>',
        '<Property name="Uid" type="App::PropertyUUID">',
        f'<Uuid value="{uuid.uuid4()}"/>',
        '</Property>',
        '</Properties>',
    ]

    # Liste des objets (status="1" = Touched → force recalcul a l'ouverture)
    lines.append(f'<Objects Count="{len(objets)}">')
    for i, obj in enumerate(objets):
        lines.append(
            f'<Object type="Part::Box" name="{xml_escape(obj["nom"])}" '
            f'id="{i}" status="1"/>'
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
        lines.append(f'<String value="{label}"/>')
        lines.append('</Property>')

        # Length
        lines.append('<Property name="Length" type="App::PropertyLength">')
        lines.append(f'<Float value="{obj["length"]:.6f}"/>')
        lines.append('</Property>')

        # Width
        lines.append('<Property name="Width" type="App::PropertyLength">')
        lines.append(f'<Float value="{obj["width"]:.6f}"/>')
        lines.append('</Property>')

        # Height
        lines.append('<Property name="Height" type="App::PropertyLength">')
        lines.append(f'<Float value="{obj["height"]:.6f}"/>')
        lines.append('</Property>')

        # Placement
        lines.append('<Property name="Placement" type="App::PropertyPlacement">')
        lines.append(
            f'<PropertyPlacement '
            f'Px="{obj["px"]:.15e}" Py="{obj["py"]:.15e}" Pz="{obj["pz"]:.15e}" '
            f'Q0="0.000000000000000e+0" Q1="0.000000000000000e+0" '
            f'Q2="0.000000000000000e+0" Q3="1.000000000000000e+0" '
            f'A="0.000000000000000e+0" '
            f'Ox="0.000000000000000e+0" Oy="0.000000000000000e+0" '
            f'Oz="1.000000000000000e+0"/>')
        lines.append('</Property>')

        lines.append('</Properties>')
        lines.append('</Object>')

    lines.append('</ObjectData>')
    lines.append('</Document>')

    return '\n'.join(lines).encode("utf-8")


def _generer_guidocument_xml(objets: list[dict]) -> bytes:
    """Genere le contenu GuiDocument.xml du fichier FCStd.

    Construit le XML par formatage de chaines pour correspondre exactement
    au format attendu par le parser Xerces-C de FreeCAD. Definit les
    proprietes visuelles (couleur, transparence, visibilite) de chaque
    objet et configure la camera par defaut en vue isometrique.

    Structure: Document > ViewProviderData > ViewProvider* + Camera.

    Args:
        objets: Liste de dictionnaires representant les objets 3D, tels que
            retournes par _collecter_objets_3d.

    Returns:
        Contenu XML du GuiDocument.xml encode en UTF-8.
    """
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<Document SchemaVersion="1">',
        f'<ViewProviderData Count="{len(objets)}">',
    ]

    for obj in objets:
        nom = xml_escape(obj["nom"])
        couleur = _couleur_packed(obj["couleur"])

        lines.append(f'<ViewProvider name="{nom}" expanded="0">')
        lines.append('<Properties Count="3">')

        # ShapeColor
        lines.append('<Property name="ShapeColor" type="App::PropertyColor">')
        lines.append(f'<PropertyColor value="{couleur}"/>')
        lines.append('</Property>')

        # Transparency
        lines.append('<Property name="Transparency" type="App::PropertyPercent">')
        lines.append(f'<Integer value="{obj["transparence"]}"/>')
        lines.append('</Property>')

        # Visibility
        lines.append('<Property name="Visibility" type="App::PropertyBool">')
        lines.append('<Bool value="true"/>')
        lines.append('</Property>')

        lines.append('</Properties>')
        lines.append('</ViewProvider>')

    lines.append('</ViewProviderData>')

    # Camera obligatoire — vue isometrique par defaut (format Open Inventor)
    cam = (
        '#Inventor V2.1 ascii&#10;'
        'OrthographicCamera {&#10;'
        '  viewportMapping ADJUST_CAMERA&#10;'
        '  position 0 -1 0&#10;'
        '  orientation 1 0 0  1.5707963&#10;'
        '  nearDistance -10000&#10;'
        '  farDistance 10000&#10;'
        '  aspectRatio 1&#10;'
        '  focalDistance 0&#10;'
        '  height 3000&#10;'
        '}&#10;'
    )
    lines.append(f'<Camera settings="{cam}"/>')

    lines.append('</Document>')

    return '\n'.join(lines).encode("utf-8")


# =====================================================================
#  Export
# =====================================================================

def exporter_freecad(filepath: str, config: dict) -> str:
    """Exporte le placard en fichier FreeCAD natif (.FCStd).

    Le fichier FCStd est une archive ZIP contenant Document.xml (modele
    parametrique) et GuiDocument.xml (proprietes visuelles). A l'ouverture
    dans FreeCAD, les formes seront recalculees automatiquement ou via
    Edit > Refresh (Ctrl+Shift+R).

    Args:
        filepath: Chemin du fichier .FCStd a generer.
        config: Dictionnaire de configuration complet du placard (schema
            parse + parametres physiques).

    Returns:
        Chemin du fichier FCStd genere (identique a filepath).
    """
    objets = _collecter_objets_3d(config)

    doc_xml = _generer_document_xml(objets)
    gui_xml = _generer_guidocument_xml(objets)

    with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Document.xml", doc_xml)
        zf.writestr("GuiDocument.xml", gui_xml)

    return filepath


def generer_script_freecad(config: dict, is_meuble: bool = False) -> str:
    """Genere un script Python executable dans la console FreeCAD.

    Ce script recree tous les objets Part::Box avec les bonnes dimensions,
    positions, couleurs et labels. Il suffit de le copier-coller dans la
    console Python de FreeCAD ou de l'executer via Macro > Executer.

    Args:
        config: Configuration complete du placard ou meuble.
        is_meuble: True pour un meuble, False pour un placard.

    Returns:
        Code source Python du script FreeCAD.
    """
    if is_meuble:
        objets = _collecter_objets_3d_meuble(config)
    else:
        objets = _collecter_objets_3d(config)

    lines = [
        "import FreeCAD",
        "import Part",
        "",
        "doc = FreeCAD.newDocument('PlacardCAD')",
        "",
    ]

    for obj in objets:
        nom = obj["nom"]
        label = obj["label"].replace("'", "\\'")
        r, g, b = obj["couleur"]
        lines.append(f"obj = doc.addObject('Part::Box', '{nom}')")
        lines.append(f"obj.Label = '{label}'")
        lines.append(f"obj.Length = {obj['length']:.2f}")
        lines.append(f"obj.Width = {obj['width']:.2f}")
        lines.append(f"obj.Height = {obj['height']:.2f}")
        lines.append(
            f"obj.Placement = FreeCAD.Placement("
            f"FreeCAD.Vector({obj['px']:.2f}, {obj['py']:.2f}, {obj['pz']:.2f}), "
            f"FreeCAD.Rotation(0, 0, 0, 1))"
        )
        lines.append(
            f"obj.ViewObject.ShapeColor = ({r:.3f}, {g:.3f}, {b:.3f})"
        )
        if obj["transparence"] > 0:
            lines.append(
                f"obj.ViewObject.Transparency = {obj['transparence']}"
            )
        lines.append("")

    lines.append("doc.recompute()")
    lines.append("FreeCADGui.activeDocument().activeView().viewIsometric()")
    lines.append("FreeCADGui.SendMsgToActiveView('ViewFit')")

    return "\n".join(lines)


def _nom_groupe_freecad(nom: str) -> str:
    """Convertit un nom d'amenagement en nom valide pour un groupe FreeCAD.

    Remplace les caracteres non alphanumeriques par des underscores.

    Args:
        nom: Nom de l'amenagement.

    Returns:
        Nom valide pour un objet FreeCAD.
    """
    import re
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", nom)
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean or "Meuble"


_PIVOT_FRACTIONS = {
    "avant_gauche": (0.0, 0.0),
    "avant_centre": (0.5, 0.0),
    "avant_droit": (1.0, 0.0),
    "milieu_gauche": (0.0, 0.5),
    "centre": (0.5, 0.5),
    "milieu_droit": (1.0, 0.5),
    "arriere_gauche": (0.0, 1.0),
    "arriere_centre": (0.5, 1.0),
    "arriere_droit": (1.0, 1.0),
}


def _pivot_offset(pivot_key: str, largeur: float, profondeur: float
                  ) -> tuple[float, float]:
    """Retourne l'offset local (mm) du pivot depuis l'origine du meuble."""
    fx, fy = _PIVOT_FRACTIONS.get(pivot_key, (0.0, 0.0))
    return fx * largeur, fy * profondeur


def generer_script_meuble_groupe(
    config: dict,
    nom_groupe: str,
    nom_projet: str = "Projet",
) -> str:
    """Genere un script Python FreeCAD qui cree/met a jour un meuble dans un App::Part.

    Le script est concu pour etre execute dans un document FreeCAD existant.
    Si le conteneur existe deja, il est supprime puis recree. Chaque element
    du meuble est un Part::Box ajoute au App::Part. Le conteneur peut ensuite
    etre deplace dans FreeCAD via sa propriete Placement (onglet Donnees).

    Args:
        config: Configuration complete du meuble.
        nom_groupe: Nom du conteneur FreeCAD (issu du nom d'amenagement).
        nom_projet: Nom du projet (utilise pour creer le document si aucun n'est ouvert).

    Returns:
        Code source Python du script FreeCAD.
    """
    objets = _collecter_objets_3d_meuble(config)
    grp_name = _nom_groupe_freecad(nom_groupe)

    # Placement du meuble sur le plan (position + rotation + pivot)
    placement = config.get("placement", {})
    pivot_x = placement.get("x", 0.0)
    pivot_y = placement.get("y", 0.0)
    place_rot = placement.get("rotation", 0.0)
    pivot_key = placement.get("pivot", "avant_gauche")

    # Calculer la position de l'origine (avant-gauche) du meuble
    # a partir de la position du pivot
    import math as _math
    L = config.get("largeur", 600)
    P = config.get("profondeur", 600)
    pvx, pvy = _pivot_offset(pivot_key, L, P)
    angle_rad = _math.radians(place_rot)
    cos_a = _math.cos(angle_rad)
    sin_a = _math.sin(angle_rad)
    # origin = pivot_world - rotate(pivot_local)
    place_x = pivot_x - (pvx * cos_a - pvy * sin_a)
    place_y = pivot_y - (pvx * sin_a + pvy * cos_a)

    lines = [
        f"# Script PlacardCAD — {nom_groupe}",
        f"# Execute dans FreeCAD: Macro > Executer une macro",
        f"# Cree ou met a jour le groupe '{grp_name}' dans le document actif.",
        "",
        "import FreeCAD",
        "import Part",
        "",
        "doc = FreeCAD.activeDocument()",
        "if doc is None:",
        f"    doc = FreeCAD.newDocument('{_nom_groupe_freecad(nom_projet)}')",
        "",
        f"GRP_NAME = '{grp_name}'",
        "",
        "# --- Supprimer le groupe existant s'il existe ---",
        "old_grp = doc.getObject(GRP_NAME)",
        "if old_grp is not None:",
        "    for child in old_grp.Group:",
        "        doc.removeObject(child.Name)",
        "    doc.removeObject(GRP_NAME)",
        "",
        "# --- Creer le conteneur (App::Part = deplacable via Placement) ---",
        "grp = doc.addObject('App::Part', GRP_NAME)",
        f"grp.Label = '{nom_groupe.replace(chr(39), chr(39) + chr(39))}'",
        f"grp.Placement = FreeCAD.Placement(",
        f"    FreeCAD.Vector({place_x:.2f}, {place_y:.2f}, 0),",
        f"    FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), {place_rot:.2f}))",
        "",
    ]

    for obj in objets:
        nom = obj["nom"]
        label = obj["label"].replace("'", "\\'")
        r, g, b = obj["couleur"]
        px, py, pz = obj["px"], obj["py"], obj["pz"]

        lines.append(f"obj = doc.addObject('Part::Box', '{nom}')")
        lines.append(f"obj.Label = '{label}'")
        lines.append(f"obj.Length = {obj['length']:.2f}")
        lines.append(f"obj.Width = {obj['width']:.2f}")
        lines.append(f"obj.Height = {obj['height']:.2f}")
        lines.append(
            f"obj.Placement = FreeCAD.Placement("
            f"FreeCAD.Vector({px:.2f}, {py:.2f}, {pz:.2f}), "
            f"FreeCAD.Rotation(0, 0, 0, 1))"
        )
        lines.append(
            f"obj.ViewObject.ShapeColor = ({r:.3f}, {g:.3f}, {b:.3f})"
        )
        if obj["transparence"] > 0:
            lines.append(
                f"obj.ViewObject.Transparency = {obj['transparence']}"
            )
        lines.append("grp.addObject(obj)")
        lines.append("")

    lines.append("doc.recompute()")
    lines.append(f"print(f'Groupe {{GRP_NAME}} cree avec {len(objets)} objets.')")
    lines.append("")

    return "\n".join(lines)


# =====================================================================
#  Export FreeCAD Meuble
# =====================================================================

COULEURS_3D_MEUBLE = {
    "flanc": (0.82, 0.71, 0.55),
    "dessus": (0.82, 0.71, 0.55),
    "traverse": (0.82, 0.71, 0.55),
    "dessous": (0.82, 0.71, 0.55),
    "separation": (0.82, 0.71, 0.55),
    "fond": (0.83, 0.77, 0.66),
    "etagere": (0.82, 0.71, 0.55),
    "plinthe": (0.4, 0.4, 0.4),
    "cremaillere": (0.63, 0.63, 0.63),
    "rainure": (0.5, 0.45, 0.35),
    "porte": (0.92, 0.92, 0.92),
    "tiroir": (0.92, 0.92, 0.92),
    "poignee": (0.75, 0.75, 0.78),
}


def _profondeur_element_meuble(type_elem: str, config: dict) -> tuple[float, float]:
    """Calcule la profondeur (Y) et le decalage Y pour un type d'element meuble.

    Pour les meubles parametriques: Y=0 face avant, Y=P mur du fond.

    Args:
        type_elem: Type de l'element ('flanc', 'dessus', 'dessous',
            'separation', 'fond', 'etagere', 'plinthe', 'cremaillere',
            'porte', 'tiroir', 'rainure').
        config: Configuration complete du meuble.

    Returns:
        Tuple (profondeur_mm, y_offset_mm).
    """
    P = config["profondeur"]
    ep = config["epaisseur"]
    ep_f = config["epaisseur_facade"]
    fond_cfg = config.get("fond", {})
    ep_fond = fond_cfg.get("epaisseur", 3)

    if type_elem in ("flanc", "dessus"):
        return P, 0

    elif type_elem == "separation":
        sep_cfg = config.get("separation", {})
        retrait_av = sep_cfg.get("retrait_avant", 0)
        retrait_ar = sep_cfg.get("retrait_arriere", 0)
        return P - retrait_av - retrait_ar, retrait_av

    elif type_elem == "dessous":
        retrait_ar = config.get("dessous", {}).get("retrait_arriere", 50)
        return P - retrait_ar, 0

    elif type_elem == "fond":
        return ep_fond, P - ep_fond

    elif type_elem == "etagere":
        retrait_av = config.get("etagere", {}).get("retrait_avant", 20)
        dist_chant = fond_cfg.get("distance_chant", 10)
        depth = P - retrait_av - dist_chant - ep_fond
        return depth, retrait_av

    elif type_elem == "plinthe":
        retrait = config.get("plinthe", {}).get("retrait", 30)
        ep_plinthe = config.get("plinthe", {}).get("epaisseur", 16)
        return ep_plinthe, retrait

    elif type_elem == "cremaillere":
        crem_cfg = config.get("cremaillere", {})
        dist_av = crem_cfg.get("distance_avant", 37)
        dist_ar = crem_cfg.get("distance_arriere", 37)
        depth = P - dist_av - dist_ar
        return depth, dist_av

    elif type_elem == "rainure":
        # Rainure dans les panneaux: petit volume
        prof_r = fond_cfg.get("profondeur_rainure", 8)
        return prof_r, P - ep_fond - prof_r

    elif type_elem in ("porte", "tiroir"):
        # Facade en avant du caisson
        return ep_f, -ep_f

    elif type_elem == "poignee":
        # Poignee baton: saillie depuis la face avant de la facade
        saillie = config.get("poignee", {}).get("saillie", 36)
        return saillie, -ep_f - saillie

    else:
        return P * 0.5, P * 0.25


def _collecter_objets_3d_meuble(config: dict) -> list[dict]:
    """Collecte tous les objets 3D a partir de la configuration d'un meuble.

    Genere la geometrie 2D de face via le builder meuble, puis convertit
    chaque rectangle en objet 3D en calculant la profondeur selon le type.

    Args:
        config: Configuration complete du meuble.

    Returns:
        Liste de dictionnaires representant les objets 3D.
    """
    from .meuble_builder import generer_geometrie_meuble, calculer_largeurs_meuble

    rects, _fiche = generer_geometrie_meuble(config)

    H = config["hauteur"]
    L = config["largeur"]
    P = config["profondeur"]

    objets = []
    noms_utilises: set[str] = set()

    # Elements du meuble (hors cotation, ouverture, percage, poignee)
    skip_types = ("cotation", "ouverture", "percage", "poignee")
    elements = [r for r in rects if r.type_elem not in skip_types]

    grouped: dict[str, list] = {}
    for r in elements:
        grouped.setdefault(r.type_elem, []).append(r)

    ordre = [
        "plinthe", "flanc", "dessus", "dessous", "separation",
        "fond", "etagere", "rainure", "cremaillere",
        "porte", "tiroir",
    ]

    for type_elem in ordre:
        if type_elem not in grouped:
            continue

        group_rects = grouped[type_elem]
        couleur = COULEURS_3D_MEUBLE.get(type_elem, (0.8, 0.7, 0.55))
        profondeur, y_offset = _profondeur_element_meuble(type_elem, config)

        if profondeur <= 0:
            continue

        transparence = 40 if type_elem in ("cremaillere", "rainure") else 0
        if type_elem in ("porte", "tiroir"):
            transparence = 20

        for i, r in enumerate(group_rects):
            nom_base = _nom_freecad(r.label, i, type_elem)
            nom = _nom_unique(nom_base, noms_utilises)
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

    # Plinthes de cotes (non presentes dans les rects 2D face)
    plinthe_cfg = config.get("plinthe", {})
    h_plinthe = config.get("hauteur_plinthe", 0)
    if plinthe_cfg.get("type") == "trois_cotes" and h_plinthe > 0:
        retrait_p = plinthe_cfg.get("retrait", 30)
        retrait_g = plinthe_cfg.get("retrait_gauche", retrait_p)
        retrait_d = plinthe_cfg.get("retrait_droite", retrait_p)
        ep_plinthe = plinthe_cfg.get("epaisseur", 16)
        couleur_p = COULEURS_3D_MEUBLE.get("plinthe", (0.4, 0.4, 0.4))
        longueur_cote = P - retrait_p - ep_plinthe
        for nom_p, px in [("Plinthe_gauche", retrait_g),
                          ("Plinthe_droite", L - retrait_d - ep_plinthe)]:
            objets.append({
                "nom": _nom_unique(nom_p, noms_utilises),
                "label": nom_p.replace("_", " "),
                "length": ep_plinthe,
                "width": longueur_cote,
                "height": h_plinthe,
                "px": px,
                "py": retrait_p + ep_plinthe,
                "pz": 0,
                "couleur": couleur_p,
                "transparence": 0,
            })

    # ----------------------------------------------------------------
    # Traverses (si dessus.type == "traverses", non gere par la boucle)
    # ----------------------------------------------------------------
    ep = config["epaisseur"]
    h_plinthe = config.get("hauteur_plinthe", 0)
    h_corps = H - h_plinthe
    assemblage = config.get("assemblage", "dessus_sur")

    dessus_cfg = config.get("dessus", {})
    dessus_type_cfg = dessus_cfg.get("type", "traverses")
    if dessus_type_cfg == "traverses":
        larg_trav = dessus_cfg.get("largeur_traverse", 100)
        if assemblage == "dessus_sur":
            trav_x, trav_w = 0.0, float(L)
        else:
            trav_x, trav_w = float(ep), L - 2 * ep
        z_trav = h_plinthe + h_corps - ep
        couleur_trav = COULEURS_3D_MEUBLE.get("traverse", (0.82, 0.71, 0.55))

        # Traverse avant (Y=0, face avant)
        objets.append({
            "nom": _nom_unique("Traverse_Avant", noms_utilises),
            "label": "Traverse avant",
            "length": trav_w,
            "width": larg_trav,
            "height": ep,
            "px": trav_x,
            "py": 0,
            "pz": z_trav,
            "couleur": couleur_trav,
            "transparence": 0,
        })
        # Traverse arriere (Y=P-larg_trav, vers le fond)
        objets.append({
            "nom": _nom_unique("Traverse_Arriere", noms_utilises),
            "label": "Traverse arriere",
            "length": trav_w,
            "width": larg_trav,
            "height": ep,
            "px": trav_x,
            "py": P - larg_trav,
            "pz": z_trav,
            "couleur": couleur_trav,
            "transparence": 0,
        })

    # ----------------------------------------------------------------
    # Fond (panneau arriere, non present dans les rects 2D face)
    # ----------------------------------------------------------------
    fond_cfg = config.get("fond", {})
    ep_fond = fond_cfg.get("epaisseur", 3)
    fond_type = fond_cfg.get("type", "rainure")

    hauteur_fond_imposee = fond_cfg.get("hauteur", 0)
    if fond_type == "rainure":
        prof_r = fond_cfg.get("profondeur_rainure", 8)
        fond_px = ep - prof_r
        fond_pw = L - 2 * ep + 2 * prof_r
        fond_py = P - fond_cfg.get("distance_chant", 10) - ep_fond
        fond_pz = h_plinthe + ep - prof_r
        if hauteur_fond_imposee > 0:
            fond_ph = hauteur_fond_imposee + 2 * prof_r
        else:
            fond_ph = h_corps - 2 * ep + 2 * prof_r
    elif fond_type == "applique":
        fond_px = 0.0
        fond_pw = L
        fond_py = P - ep_fond
        fond_pz = h_plinthe + ep
        fond_ph = hauteur_fond_imposee if hauteur_fond_imposee > 0 else h_corps - 2 * ep
    else:  # vissage
        fond_px = ep
        fond_pw = L - 2 * ep
        fond_py = P - ep_fond
        fond_pz = h_plinthe + ep
        fond_ph = hauteur_fond_imposee if hauteur_fond_imposee > 0 else h_corps - 2 * ep

    couleur_fond = COULEURS_3D_MEUBLE.get("fond", (0.83, 0.77, 0.66))
    objets.append({
        "nom": _nom_unique("Fond", noms_utilises),
        "label": "Fond",
        "length": fond_pw,
        "width": ep_fond,
        "height": fond_ph,
        "px": fond_px,
        "py": fond_py,
        "pz": fond_pz,
        "couleur": couleur_fond,
        "transparence": 0,
    })

    # ----------------------------------------------------------------
    # Rainures fond (entailles dans flancs, dessus et dessous)
    # ----------------------------------------------------------------
    couleur_rainure = (0.42, 0.36, 0.23)
    if fond_type == "rainure":
        h_int_corps = h_corps - 2 * ep
        if hauteur_fond_imposee > 0:
            h_rainure_flanc = hauteur_fond_imposee
        else:
            h_rainure_flanc = h_int_corps
        z_rainure_flanc = h_plinthe + ep
        if assemblage == "dessus_sur":
            dessus_x, dessus_w = 0.0, float(L)
        else:
            dessus_x, dessus_w = float(ep), L - 2 * ep

        # Rainure fond dans flanc gauche
        objets.append({
            "nom": _nom_unique("Rainure_fond_flanc_G", noms_utilises),
            "label": "Rainure fond flanc G",
            "length": prof_r,
            "width": ep_fond,
            "height": h_rainure_flanc,
            "px": ep - prof_r,
            "py": fond_py,
            "pz": z_rainure_flanc,
            "couleur": couleur_rainure,
            "transparence": 40,
        })
        # Rainure fond dans flanc droit
        objets.append({
            "nom": _nom_unique("Rainure_fond_flanc_D", noms_utilises),
            "label": "Rainure fond flanc D",
            "length": prof_r,
            "width": ep_fond,
            "height": h_rainure_flanc,
            "px": L - ep,
            "py": fond_py,
            "pz": z_rainure_flanc,
            "couleur": couleur_rainure,
            "transparence": 40,
        })
        # Rainure fond dans dessus / traverse arriere (seulement si fond pleine hauteur)
        fond_atteint_dessus = (hauteur_fond_imposee <= 0
                               or hauteur_fond_imposee >= h_int_corps)
        if fond_atteint_dessus:
            rain_dessus_label = ("Rainure fond trav. ar."
                                 if dessus_type_cfg == "traverses"
                                 else "Rainure fond dessus")
            objets.append({
                "nom": _nom_unique("Rainure_fond_dessus", noms_utilises),
                "label": rain_dessus_label,
                "length": dessus_w,
                "width": ep_fond,
                "height": prof_r,
                "px": dessus_x,
                "py": fond_py,
                "pz": h_plinthe + h_corps - ep,
                "couleur": couleur_rainure,
                "transparence": 40,
            })
        # Rainure fond dans dessous
        objets.append({
            "nom": _nom_unique("Rainure_fond_dessous", noms_utilises),
            "label": "Rainure fond dessous",
            "length": dessus_w,
            "width": ep_fond,
            "height": prof_r,
            "px": dessus_x,
            "py": fond_py,
            "pz": h_plinthe + ep - prof_r,
            "couleur": couleur_rainure,
            "transparence": 40,
        })

    # ----------------------------------------------------------------
    # Cremailleres et rainures cremailleres dans flancs et separations
    # ----------------------------------------------------------------
    crem_cfg = config.get("cremaillere", {})
    crem_prof = crem_cfg.get("profondeur", 7)
    crem_larg = crem_cfg.get("largeur", 16)
    dist_av = crem_cfg.get("distance_avant", 37)
    dist_ar = crem_cfg.get("distance_arriere", 37)
    nb_comp = config.get("nombre_compartiments", 1)
    ep_sep = config.get("separation", {}).get("epaisseur", 18)

    h_crem = h_corps - 2 * ep
    z_crem = h_plinthe + ep
    y_crem_av = dist_av
    y_crem_ar = fond_py - dist_ar - crem_larg

    couleur_crem = (0.63, 0.63, 0.63)

    comp_has_etag = [config["compartiments"][i]["etageres"] > 0
                     for i in range(nb_comp)]
    largeurs = calculer_largeurs_meuble(config)

    def _ajouter_paire_crem(x_pos: float, label_prefix: str) -> None:
        """Ajoute une paire rainure+cremaillere (avant et arriere) a x_pos."""
        for y_pos, suffixe in [(y_crem_av, "av"), (y_crem_ar, "ar")]:
            # Rainure (entaille dans le panneau)
            objets.append({
                "nom": _nom_unique(
                    f"Rainure_crem_{suffixe}_{label_prefix}", noms_utilises),
                "label": f"Rainure crem {suffixe} {label_prefix}",
                "length": crem_prof,
                "width": crem_larg,
                "height": h_crem,
                "px": x_pos,
                "py": y_pos,
                "pz": z_crem,
                "couleur": couleur_rainure,
                "transparence": 40,
            })
            # Cremaillere (rail metallique dans la rainure)
            objets.append({
                "nom": _nom_unique(
                    f"Cremaillere_{suffixe}_{label_prefix}", noms_utilises),
                "label": f"Cremaillere {suffixe} {label_prefix}",
                "length": crem_prof,
                "width": crem_larg,
                "height": h_crem,
                "px": x_pos,
                "py": y_pos,
                "pz": z_crem,
                "couleur": couleur_crem,
                "transparence": 40,
            })

    # Cremailleres dans flanc gauche (si compartiment 0 a des etageres)
    if comp_has_etag[0]:
        _ajouter_paire_crem(ep - crem_prof, "flanc_G")

    # Cremailleres dans flanc droit (si dernier compartiment a des etageres)
    if comp_has_etag[-1]:
        _ajouter_paire_crem(L - ep, "flanc_D")

    # Cremailleres dans les separations
    x_cursor = ep
    for comp_idx in range(nb_comp):
        larg_c = largeurs[comp_idx]
        if comp_idx < nb_comp - 1:
            x_sep = x_cursor + larg_c
            # Face gauche de la separation
            if comp_has_etag[comp_idx]:
                _ajouter_paire_crem(x_sep, f"sep{comp_idx+1}_G")
            # Face droite de la separation
            if comp_has_etag[comp_idx + 1]:
                _ajouter_paire_crem(
                    x_sep + ep_sep - crem_prof, f"sep{comp_idx+1}_D")
            x_cursor = x_sep + ep_sep
        else:
            x_cursor += larg_c

    # ----------------------------------------------------------------
    # Poignees (barre + 2 montants par poignee)
    # ----------------------------------------------------------------
    poignee_cfg = config.get("poignee", {})
    if poignee_cfg.get("modele", "baton_inox") != "aucune":
        from .meuble_builder import POIGNEE_BATON_CATALOGUE
        ep_f_p = config["epaisseur_facade"]
        entraxe_p = int(poignee_cfg.get("entraxe", 128))
        diametre_p = poignee_cfg.get("diametre", 12)
        saillie_p = poignee_cfg.get("saillie", 36)
        cat_p = POIGNEE_BATON_CATALOGUE.get(entraxe_p)
        longueur_p = cat_p["longueur"] if cat_p else entraxe_p + 58
        couleur_inox = COULEURS_3D_MEUBLE.get("poignee", (0.75, 0.75, 0.78))

        poignee_rects = [r for r in rects if r.type_elem == "poignee"]
        for i, r in enumerate(poignee_rects):
            # r.x = position X du debut de la poignee (vue de face)
            # r.y = position Z du centre de la poignee (vue de face)
            px_bar = r.x
            pz_bar = r.y
            # Y: barre au front, montants vers la facade
            py_bar = -ep_f_p - saillie_p
            profondeur_montant = saillie_p - diametre_p
            py_montant = -ep_f_p - profondeur_montant
            # Positions X des deux montants (centres des trous)
            x_centre = r.x + longueur_p / 2
            x_montant_g = x_centre - entraxe_p / 2 - diametre_p / 2
            x_montant_d = x_centre + entraxe_p / 2 - diametre_p / 2

            label_base = r.label or f"Poignee {i+1}"

            # Barre horizontale
            objets.append({
                "nom": _nom_unique(f"Poignee_barre_{i}", noms_utilises),
                "label": f"{label_base} barre",
                "length": longueur_p,
                "width": diametre_p,
                "height": diametre_p,
                "px": px_bar,
                "py": py_bar,
                "pz": pz_bar,
                "couleur": couleur_inox,
                "transparence": 0,
            })
            # Montant gauche
            objets.append({
                "nom": _nom_unique(f"Poignee_montant_G_{i}", noms_utilises),
                "label": f"{label_base} montant G",
                "length": diametre_p,
                "width": profondeur_montant,
                "height": diametre_p,
                "px": x_montant_g,
                "py": py_montant,
                "pz": pz_bar,
                "couleur": couleur_inox,
                "transparence": 0,
            })
            # Montant droit
            objets.append({
                "nom": _nom_unique(f"Poignee_montant_D_{i}", noms_utilises),
                "label": f"{label_base} montant D",
                "length": diametre_p,
                "width": profondeur_montant,
                "height": diametre_p,
                "px": x_montant_d,
                "py": py_montant,
                "pz": pz_bar,
                "couleur": couleur_inox,
                "transparence": 0,
            })

    # Sol (contexte transparent)
    sol_couleur = (0.85, 0.85, 0.82)
    mur_ep = 20
    objets.append({
        "nom": _nom_unique("Sol", noms_utilises),
        "label": "Sol",
        "length": L + 2 * mur_ep,
        "width": P + mur_ep,
        "height": mur_ep,
        "px": -mur_ep,
        "py": -mur_ep,
        "pz": -mur_ep,
        "couleur": sol_couleur,
        "transparence": 70,
    })

    return objets


def exporter_freecad_meuble(filepath: str, config: dict) -> str:
    """Exporte un meuble parametrique en fichier FreeCAD natif (.FCStd).

    Le fichier FCStd est une archive ZIP contenant Document.xml (modele
    parametrique) et GuiDocument.xml (proprietes visuelles).

    Args:
        filepath: Chemin du fichier .FCStd a generer.
        config: Configuration complete du meuble.

    Returns:
        Chemin du fichier FCStd genere.
    """
    objets = _collecter_objets_3d_meuble(config)

    doc_xml = _generer_document_xml(objets)
    gui_xml = _generer_guidocument_xml(objets)

    with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Document.xml", doc_xml)
        zf.writestr("GuiDocument.xml", gui_xml)

    return filepath


# =====================================================================
#  Export projet complet (plan + meubles) en script Python FreeCAD
# =====================================================================

# Couleurs des elements du plan
_COULEUR_MUR = (0.90, 0.90, 0.88)
_COULEUR_SOL = (0.85, 0.85, 0.82)


def generer_script_projet(
    nom_projet: str,
    contour: list[tuple[float, float]],
    amenagements: list[dict],
    hauteur_piece: float = 2500,
    epaisseur_mur: float = 50,
) -> str:
    """Genere un script Python FreeCAD assemblant le plan de la piece et tous les meubles.

    Le script cree un document FreeCAD contenant :
    - Les murs de la piece (extrusion de chaque segment du contour).
    - Le sol (face extrudee du polygone du contour).
    - Un App::Part par amenagement, positionne avec son placement (x, y, rotation, pivot).

    Args:
        nom_projet: Nom du projet (utilise comme nom du document FreeCAD).
        contour: Liste de points (x, y) en mm formant le polygone ferme de la piece.
        amenagements: Liste de dicts, chacun contenant :
            - "nom": nom de l'amenagement
            - "config": config complete (schema parse + params)
            - "is_meuble": True si meuble, False si placard
        hauteur_piece: Hauteur sous plafond en mm (defaut 2500).
        epaisseur_mur: Epaisseur des murs 3D en mm (defaut 50).

    Returns:
        Code source Python du script FreeCAD.
    """
    doc_name = _nom_groupe_freecad(nom_projet)

    lines = [
        f"# Script PlacardCAD — Projet {nom_projet}",
        f"# Plan complet avec {len(amenagements)} amenagement(s)",
        "# Executer dans FreeCAD: Macro > Executer une macro",
        "",
        "import FreeCAD",
        "import FreeCADGui",
        "import Part",
        "",
        f"doc = FreeCAD.newDocument('{doc_name}')",
        "",
    ]

    # --- Murs : extrusion de chaque segment du contour ---
    if contour and len(contour) >= 3:
        lines.append("# " + "=" * 60)
        lines.append("# Murs de la piece")
        lines.append("# " + "=" * 60)
        lines.append("")
        lines.append("grp_murs = doc.addObject('App::Part', 'Murs')")
        lines.append("grp_murs.Label = 'Murs'")
        lines.append("")

        n = len(contour)
        for i in range(n):
            ax, ay = contour[i]
            bx, by = contour[(i + 1) % n]
            seg_dx = bx - ax
            seg_dy = by - ay
            seg_len = math.hypot(seg_dx, seg_dy)
            if seg_len < 1:
                continue
            seg_angle = math.degrees(math.atan2(seg_dy, seg_dx))
            r, g, b = _COULEUR_MUR

            lines.append(f"obj = doc.addObject('Part::Box', 'Mur_{i}')")
            lines.append(f"obj.Label = 'Mur {i}'")
            lines.append(f"obj.Length = {seg_len:.2f}")
            lines.append(f"obj.Width = {epaisseur_mur:.2f}")
            lines.append(f"obj.Height = {hauteur_piece:.2f}")
            lines.append(
                f"obj.Placement = FreeCAD.Placement("
                f"FreeCAD.Vector({ax:.2f}, {ay:.2f}, 0), "
                f"FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), {seg_angle:.2f}))"
            )
            lines.append(f"obj.ViewObject.ShapeColor = ({r:.3f}, {g:.3f}, {b:.3f})")
            lines.append("obj.ViewObject.Transparency = 70")
            lines.append("grp_murs.addObject(obj)")
            lines.append("")

        # Sol : Part::Box plat couvrant le bounding box du contour
        xs = [p[0] for p in contour]
        ys = [p[1] for p in contour]
        sol_x0, sol_y0 = min(xs), min(ys)
        sol_w = max(xs) - sol_x0
        sol_h = max(ys) - sol_y0
        r, g, b = _COULEUR_SOL
        lines.append("obj = doc.addObject('Part::Box', 'Sol')")
        lines.append("obj.Label = 'Sol'")
        lines.append(f"obj.Length = {sol_w:.2f}")
        lines.append(f"obj.Width = {sol_h:.2f}")
        lines.append(f"obj.Height = {epaisseur_mur:.2f}")
        lines.append(
            f"obj.Placement = FreeCAD.Placement("
            f"FreeCAD.Vector({sol_x0:.2f}, {sol_y0:.2f}, {-epaisseur_mur:.2f}), "
            f"FreeCAD.Rotation(0, 0, 0, 1))"
        )
        lines.append(f"obj.ViewObject.ShapeColor = ({r:.3f}, {g:.3f}, {b:.3f})")
        lines.append("obj.ViewObject.Transparency = 70")
        lines.append("grp_murs.addObject(obj)")
        lines.append("")

    # --- Meubles / Placards ---
    noms_groupes: set[str] = set()
    for idx, am_data in enumerate(amenagements):
        nom = am_data.get("nom", f"Amenagement_{idx}")
        config = am_data["config"]
        is_meuble = am_data.get("is_meuble", False)

        grp_name = _nom_groupe_freecad(nom)
        # Eviter les doublons de noms
        base = grp_name
        suffix = 2
        while grp_name in noms_groupes:
            grp_name = f"{base}_{suffix}"
            suffix += 1
        noms_groupes.add(grp_name)

        if is_meuble:
            objets = _collecter_objets_3d_meuble(config)
        else:
            objets = _collecter_objets_3d(config)

        # Calcul du placement (position + rotation + pivot)
        placement = config.get("placement", {})
        pivot_x = placement.get("x", 0.0)
        pivot_y = placement.get("y", 0.0)
        place_rot = placement.get("rotation", 0.0)
        pivot_key = placement.get("pivot", "avant_gauche")

        L = config.get("largeur", 600)
        P = config.get("profondeur", 600)
        pvx, pvy = _pivot_offset(pivot_key, L, P)
        angle_rad = math.radians(place_rot)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        place_x = pivot_x - (pvx * cos_a - pvy * sin_a)
        place_y = pivot_y - (pvx * sin_a + pvy * cos_a)

        lines.append("# " + "=" * 60)
        lines.append(f"# {nom}")
        lines.append("# " + "=" * 60)
        lines.append("")
        lines.append(f"grp = doc.addObject('App::Part', '{grp_name}')")
        lines.append(f"grp.Label = '{nom.replace(chr(39), chr(39) + chr(39))}'")
        lines.append(
            f"grp.Placement = FreeCAD.Placement("
            f"FreeCAD.Vector({place_x:.2f}, {place_y:.2f}, 0), "
            f"FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), {place_rot:.2f}))"
        )
        lines.append("")

        for obj in objets:
            obj_nom = obj["nom"]
            label = obj["label"].replace("'", "\\'")
            r, g, b = obj["couleur"]
            px, py, pz = obj["px"], obj["py"], obj["pz"]

            lines.append(f"obj = doc.addObject('Part::Box', '{obj_nom}')")
            lines.append(f"obj.Label = '{label}'")
            lines.append(f"obj.Length = {obj['length']:.2f}")
            lines.append(f"obj.Width = {obj['width']:.2f}")
            lines.append(f"obj.Height = {obj['height']:.2f}")
            lines.append(
                f"obj.Placement = FreeCAD.Placement("
                f"FreeCAD.Vector({px:.2f}, {py:.2f}, {pz:.2f}), "
                f"FreeCAD.Rotation(0, 0, 0, 1))"
            )
            lines.append(
                f"obj.ViewObject.ShapeColor = ({r:.3f}, {g:.3f}, {b:.3f})"
            )
            if obj.get("transparence", 0) > 0:
                lines.append(
                    f"obj.ViewObject.Transparency = {obj['transparence']}"
                )
            lines.append("grp.addObject(obj)")
            lines.append("")

    lines.append("doc.recompute()")
    lines.append("FreeCADGui.activeDocument().activeView().viewIsometric()")
    lines.append("FreeCADGui.SendMsgToActiveView('ViewFit')")
    lines.append(
        f"print('Projet {nom_projet} : "
        f"{len(amenagements)} amenagement(s) genere(s).')"
    )
    lines.append("")

    return "\n".join(lines)
