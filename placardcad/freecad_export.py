"""
Export FreeCAD pour PlacardCAD.

Genere un script Python (macro FreeCAD) qui recree le placard en 3D.
Le script peut etre execute dans FreeCAD via Macro > Executer la macro.

Convention d'axes FreeCAD:
  X = largeur (gauche -> droite)
  Y = profondeur (face avant -> mur du fond)
  Z = hauteur (sol -> plafond)
"""

from .placard_builder import generer_geometrie_2d


# Couleurs RGB par type d'element
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
    for ch in " /.-()+'":
        nom = nom.replace(ch, "_")
    return nom


def generer_script_freecad(config: dict) -> str:
    """Genere le script Python FreeCAD a partir de la configuration du placard."""
    rects, fiche = generer_geometrie_2d(config)

    H = config["hauteur"]
    L = config["largeur"]
    P = config["profondeur"]

    lines = []
    lines.append("# Script FreeCAD genere par PlacardCAD")
    lines.append("# Ouvrir dans FreeCAD : Macro > Executer la macro")
    lines.append(f"# Dimensions: {L:.0f} x {P:.0f} x {H:.0f} mm (LxPxH)")
    lines.append("")
    lines.append("import FreeCAD")
    lines.append("import Part")
    lines.append("from FreeCAD import Vector")
    lines.append("")
    lines.append('doc = FreeCAD.newDocument("Placard")')
    lines.append("")
    lines.append("")
    lines.append("def creer_boite(nom, lx, ly, lz, px, py, pz,")
    lines.append("                couleur=(0.8, 0.7, 0.55), transparence=0):")
    lines.append('    """Cree une boite Part::Box avec placement et couleur."""')
    lines.append('    obj = doc.addObject("Part::Box", nom)')
    lines.append("    obj.Length = lx")
    lines.append("    obj.Width = ly")
    lines.append("    obj.Height = lz")
    lines.append("    obj.Placement.Base = Vector(px, py, pz)")
    lines.append("    if hasattr(obj, 'ViewObject') and obj.ViewObject:")
    lines.append("        obj.ViewObject.ShapeColor = couleur")
    lines.append("        if transparence > 0:")
    lines.append("            obj.ViewObject.Transparency = transparence")
    lines.append("    return obj")
    lines.append("")

    # Filtrer les murs (traites separement comme contexte)
    elements = [r for r in rects if r.type_elem != "mur"]

    # Regrouper par type
    grouped: dict[str, list] = {}
    for r in elements:
        grouped.setdefault(r.type_elem, []).append(r)

    type_labels = {
        "separation": "Separations",
        "rayon_haut": "Rayon haut",
        "rayon": "Rayons",
        "panneau_mur": "Panneaux mur",
        "cremaillere_encastree": "Cremailleres encastrees",
        "cremaillere_applique": "Cremailleres applique",
        "tasseau": "Tasseaux",
    }

    ordre = [
        "panneau_mur", "separation", "rayon_haut", "rayon",
        "cremaillere_encastree", "cremaillere_applique", "tasseau",
    ]

    for type_elem in ordre:
        if type_elem not in grouped:
            continue

        group_rects = grouped[type_elem]
        label = type_labels.get(type_elem, type_elem)
        couleur = COULEURS_3D.get(type_elem, (0.8, 0.7, 0.55))
        profondeur, y_offset = _profondeur_element(type_elem, config)

        if profondeur <= 0:
            continue

        transparence = 40 if type_elem.startswith("cremaillere") else 0

        lines.append(f"# --- {label} ---")

        for i, r in enumerate(group_rects):
            nom = _nom_freecad(r.label, i, type_elem)
            # 2D rect: x=X pos, y=Z pos, w=X size, h=Z size
            # 3D box: Length=X, Width=Y (depth), Height=Z
            lx = r.w
            ly = profondeur
            lz = r.h
            px = r.x
            py = y_offset
            pz = r.y

            c_str = f"({couleur[0]:.2f}, {couleur[1]:.2f}, {couleur[2]:.2f})"
            lines.append(
                f'creer_boite("{nom}", {lx:.1f}, {ly:.1f}, {lz:.1f}, '
                f'{px:.1f}, {py:.1f}, {pz:.1f}, {c_str}, {transparence})'
            )

        lines.append("")

    # Murs (contexte transparent)
    mur_ep = config.get("mur_epaisseur", 50)
    lines.append("# --- Murs (contexte) ---")
    lines.append(
        f'creer_boite("Mur_gauche", {mur_ep:.1f}, {P:.1f}, {H:.1f}, '
        f'{-mur_ep:.1f}, 0, 0, (0.90, 0.90, 0.88), 70)'
    )
    lines.append(
        f'creer_boite("Mur_droit", {mur_ep:.1f}, {P:.1f}, {H:.1f}, '
        f'{L:.1f}, 0, 0, (0.90, 0.90, 0.88), 70)'
    )
    lines.append(
        f'creer_boite("Mur_fond", {L + 2 * mur_ep:.1f}, {mur_ep:.1f}, {H:.1f}, '
        f'{-mur_ep:.1f}, {P:.1f}, 0, (0.90, 0.90, 0.88), 70)'
    )
    lines.append(
        f'creer_boite("Sol", {L + 2 * mur_ep:.1f}, {P + mur_ep:.1f}, {mur_ep:.1f}, '
        f'{-mur_ep:.1f}, 0, {-mur_ep:.1f}, (0.85, 0.85, 0.82), 70)'
    )
    lines.append("")

    lines.append("doc.recompute()")
    lines.append("")
    lines.append("# Ajuster la vue")
    lines.append("if FreeCAD.GuiUp:")
    lines.append("    FreeCAD.Gui.activeDocument().activeView().viewIsometric()")
    lines.append('    FreeCAD.Gui.SendMsgToActiveView("ViewFit")')
    lines.append("")

    return "\n".join(lines)


def exporter_freecad(filepath: str, config: dict) -> str:
    """Exporte le placard en script FreeCAD (.FCMacro ou .py)."""
    script = generer_script_freecad(config)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(script)
    return filepath
