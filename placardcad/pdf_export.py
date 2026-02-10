"""
Export PDF pour PlacardCAD.

- exporter_pdf : une seule page paysage A4 pour un amenagement
- exporter_pdf_projet : une page par amenagement pour tout le projet

Chaque page contient:
- A gauche : Vue de face filaire avec cotations
- A droite : Fiche de debit + quincaillerie + chants + resume materiaux
- Cartouche en haut
- References panneaux pour etiquettes (format P{projet}/A{amenagement}/N{piece})
"""

import re
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .placard_builder import Rect as PlacardRect, FicheFabrication
from .optimisation_debit import (
    ParametresDebit, PlanDecoupe, Placement,
    optimiser_debit, pieces_depuis_fiche,
)


# =========================================================================
#  COULEURS
# =========================================================================

COULEURS_TYPE = {
    "mur": (colors.Color(0.9, 0.9, 0.88), colors.Color(0.7, 0.7, 0.68)),
    "sol": (colors.Color(0.33, 0.33, 0.33), colors.Color(0.27, 0.27, 0.27)),
    "separation": (colors.Color(0.82, 0.71, 0.55), colors.Color(0.55, 0.45, 0.33)),
    "rayon_haut": (colors.Color(0.87, 0.74, 0.53), colors.Color(0.55, 0.45, 0.33)),
    "rayon": (colors.Color(0.82, 0.71, 0.55), colors.Color(0.55, 0.45, 0.33)),
    "cremaillere_encastree": (colors.Color(0.63, 0.63, 0.63), colors.Color(0.44, 0.5, 0.56)),
    "cremaillere_applique": (colors.Color(0.8, 0.0, 0.0), colors.Color(0.6, 0.0, 0.0)),
    "panneau_mur": (colors.Color(0.82, 0.71, 0.55), colors.Color(0.55, 0.45, 0.33)),
    "tasseau": (colors.Color(0.85, 0.65, 0.13), colors.Color(0.55, 0.41, 0.08)),
}


# =========================================================================
#  HELPERS
# =========================================================================

def _attribuer_references(fiche: FicheFabrication, projet_id: int = 0,
                          amenagement_id: int = 0):
    """Attribue une reference unique a chaque piece : P{projet}/A{amenag}/N{numero}."""
    p_id = projet_id or 0
    a_id = amenagement_id or 0
    for i, piece in enumerate(fiche.pieces, 1):
        piece.reference = f"P{p_id}/A{a_id}/N{i:02d}"


def _calculer_chants(fiche: FicheFabrication) -> dict:
    """Calcule le metrage lineaire de chant par (couleur, epaisseur).

    Retourne {(couleur, ep_chant_mm): longueur_totale_mm}.
    """
    chants: dict[tuple, float] = {}
    for p in fiche.pieces:
        if not p.chant_desc:
            continue
        m = re.search(r'(\d+)', p.chant_desc)
        if not m:
            continue
        ep_chant = int(m.group(1))
        couleur = p.couleur_fab or "Standard"
        key = (couleur, ep_chant)
        chants.setdefault(key, 0.0)
        chants[key] += p.longueur * p.quantite
    return chants


# =========================================================================
#  DESSIN VUE DE FACE (directement sur le canvas)
# =========================================================================

def _dessiner_vue_face(c: canvas.Canvas, rects: list[PlacardRect],
                       largeur_placard: float, hauteur_placard: float,
                       x_orig: float, y_orig: float,
                       draw_w: float, draw_h: float):
    """Dessine la vue de face du placard sur le canvas a la position donnee."""
    if not rects or largeur_placard <= 0 or hauteur_placard <= 0:
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.grey)
        c.drawCentredString(x_orig + draw_w / 2, y_orig + draw_h / 2, "Aucune geometrie")
        return

    marge = 30
    padding = 100  # espace murs + cotations doublees
    total_w = largeur_placard + 2 * padding
    total_h = hauteur_placard + 2 * padding

    view_w = draw_w - 2 * marge
    view_h = draw_h - 2 * marge

    scale = min(view_w / total_w, view_h / total_h)
    ox = x_orig + marge + (view_w - total_w * scale) / 2 + padding * scale
    oy = y_orig + marge + (view_h - total_h * scale) / 2 + padding * scale

    # Dessiner les rectangles
    ordre = ["sol", "mur", "panneau_mur", "separation", "rayon_haut", "rayon", "cremaillere_encastree", "cremaillere_applique", "tasseau"]
    rects_par_type = {}
    for r in rects:
        rects_par_type.setdefault(r.type_elem, []).append(r)

    for type_elem in ordre:
        if type_elem not in rects_par_type:
            continue
        fill_color, stroke_color = COULEURS_TYPE.get(
            type_elem, (colors.lightgrey, colors.grey)
        )

        for r in rects_par_type[type_elem]:
            sx = ox + r.x * scale
            sy = oy + r.y * scale
            sw = r.w * scale
            sh = r.h * scale

            c.setStrokeColor(stroke_color)
            lw = 0.2 if type_elem.startswith("cremaillere") else 0.5
            c.setLineWidth(lw)

            if type_elem == "sol":
                # Fond gris fonce + hachures diagonales
                c.setFillColor(colors.Color(0.85, 0.85, 0.85))
                c.rect(sx, sy, sw, sh, fill=1)
                c.saveState()
                p = c.beginPath()
                p.rect(sx, sy, sw, sh)
                c.clipPath(p, stroke=0)
                c.setStrokeColor(colors.Color(0.33, 0.33, 0.33))
                c.setLineWidth(0.4)
                pas_h = 4
                for d in range(int((sw + sh) / pas_h) + 1):
                    x0 = sx + d * pas_h
                    c.line(x0, sy + sh, x0 - sh, sy)
                c.restoreState()
                # Contour
                c.setStrokeColor(stroke_color)
                c.setLineWidth(lw)
                c.rect(sx, sy, sw, sh, fill=0)
            else:
                c.setFillColor(fill_color)
                c.rect(sx, sy, sw, sh, fill=1)

    # --- Helper fleche PDF ---
    fl = 4  # taille fleche en points

    def _fleche_h(tip_x, tip_y, vers_droite):
        d = 1.0 if vers_droite else -1.0
        p = c.beginPath()
        p.moveTo(tip_x, tip_y)
        p.lineTo(tip_x - d * fl, tip_y - fl * 0.35)
        p.lineTo(tip_x - d * fl, tip_y + fl * 0.35)
        p.close()
        c.drawPath(p, fill=1, stroke=0)

    def _fleche_v(tip_x, tip_y, vers_haut):
        d = 1.0 if vers_haut else -1.0
        p = c.beginPath()
        p.moveTo(tip_x, tip_y)
        p.lineTo(tip_x - fl * 0.35, tip_y - d * fl)
        p.lineTo(tip_x + fl * 0.35, tip_y - d * fl)
        p.close()
        c.drawPath(p, fill=1, stroke=0)

    # --- Cotations globales ---
    c.setStrokeColor(colors.black)
    c.setFillColor(colors.black)
    c.setLineWidth(0.5)
    c.setFont("Helvetica", 7)

    # Largeur totale (en bas)
    y_cot = oy - 50
    x_left = ox
    x_right = ox + largeur_placard * scale
    c.line(x_left, y_cot, x_right, y_cot)
    c.setFillColor(colors.black)
    _fleche_h(x_left, y_cot, False)
    _fleche_h(x_right, y_cot, True)
    c.setStrokeColor(colors.grey)
    c.setLineWidth(0.3)
    c.line(x_left, oy, x_left, y_cot - 3)
    c.line(x_right, oy, x_right, y_cot - 3)
    c.setFillColor(colors.black)
    c.drawCentredString((x_left + x_right) / 2, y_cot - 10, f"{largeur_placard:.0f} mm")

    # Hauteur totale (a gauche)
    x_cot = ox - 30
    y_bottom = oy
    y_top = oy + hauteur_placard * scale
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.5)
    c.line(x_cot, y_bottom, x_cot, y_top)
    c.setFillColor(colors.black)
    _fleche_v(x_cot, y_bottom, False)
    _fleche_v(x_cot, y_top, True)
    c.setStrokeColor(colors.grey)
    c.setLineWidth(0.3)
    c.line(ox, y_bottom, x_cot - 3, y_bottom)
    c.line(ox, y_top, x_cot - 3, y_top)

    c.saveState()
    c.translate(x_cot - 8, (y_bottom + y_top) / 2)
    c.rotate(90)
    c.setFillColor(colors.black)
    c.drawCentredString(0, 0, f"{hauteur_placard:.0f} mm")
    c.restoreState()

    # --- Cotations compartiments et separations ---
    seps = sorted(
        [r for r in rects if r.type_elem == "separation"],
        key=lambda r: r.x
    )
    if seps:
        c.setFont("Helvetica", 5.5)

        # Largeurs compartiments (en bas, au-dessus de la largeur totale)
        edges = [0.0]
        for s in seps:
            edges.append(s.x)
            edges.append(s.x + s.w)
        edges.append(largeur_placard)

        # Decaler sous le sol
        sol_r = next((r for r in rects if r.type_elem == "sol"), None)
        sol_bas_pdf = oy + sol_r.y * scale if sol_r else oy
        y_cot_comp = sol_bas_pdf - 6

        for i in range(0, len(edges), 2):
            x_l = edges[i]
            x_r = edges[i + 1]
            w = x_r - x_l
            if w <= 1:
                continue

            xl_pdf = ox + x_l * scale
            xr_pdf = ox + x_r * scale

            # Traits de rappel
            c.setStrokeColor(colors.Color(0.67, 0.83, 1.0))
            c.setLineWidth(0.3)
            c.line(xl_pdf, oy, xl_pdf, y_cot_comp - 2)
            c.line(xr_pdf, oy, xr_pdf, y_cot_comp - 2)

            # Ligne de cote + fleches
            c.setStrokeColor(colors.Color(0.0, 0.4, 0.8))
            c.setFillColor(colors.Color(0.0, 0.4, 0.8))
            c.setLineWidth(0.5)
            c.line(xl_pdf, y_cot_comp, xr_pdf, y_cot_comp)
            _fleche_h(xl_pdf, y_cot_comp, False)
            _fleche_h(xr_pdf, y_cot_comp, True)

            # Texte
            c.drawCentredString((xl_pdf + xr_pdf) / 2, y_cot_comp + 2, f"{w:.0f}")

        # Hauteurs separations (a droite)
        hauteurs = sorted(set(round(s.h) for s in seps), reverse=True)

        x_base_pdf = ox + largeur_placard * scale + 20
        for idx, h_val in enumerate(hauteurs):
            x_cot_pdf = x_base_pdf + idx * 28

            yb = oy
            yt = oy + h_val * scale

            # Traits de rappel
            c.setStrokeColor(colors.Color(1.0, 0.83, 0.67))
            c.setLineWidth(0.3)
            c.line(ox + largeur_placard * scale, yb, x_cot_pdf + 2, yb)
            c.line(ox + largeur_placard * scale, yt, x_cot_pdf + 2, yt)

            # Ligne de cote + fleches
            c.setStrokeColor(colors.Color(0.8, 0.4, 0.0))
            c.setFillColor(colors.Color(0.8, 0.4, 0.0))
            c.setLineWidth(0.5)
            c.line(x_cot_pdf, yb, x_cot_pdf, yt)
            _fleche_v(x_cot_pdf, yb, False)
            _fleche_v(x_cot_pdf, yt, True)

            # Texte
            c.saveState()
            c.translate(x_cot_pdf + 6, (yb + yt) / 2)
            c.rotate(90)
            c.drawCentredString(0, 0, f"Sep. {h_val:.0f}")
            c.restoreState()

    # --- Cotations hauteurs entre rayons par compartiment ---
    rayons_par_comp: dict[int, list[float]] = {}
    for r in rects:
        if r.type_elem == "rayon":
            m_rayon = re.match(r'Rayon C(\d+)', r.label)
            if m_rayon:
                cn = int(m_rayon.group(1))
                rayons_par_comp.setdefault(cn, []).append(r.y)

    if rayons_par_comp:
        # Limite haute : dessous du rayon haut ou plafond
        rh = next((r for r in rects if r.type_elem == "rayon_haut"), None)
        z_plafond = rh.y if rh else hauteur_placard

        # Bords des compartiments
        edges_comp = [0.0]
        for s in seps:
            edges_comp.append(s.x)
            edges_comp.append(s.x + s.w)
        edges_comp.append(largeur_placard)

        coul_vert = colors.Color(0.0, 0.55, 0.27)
        c.setFont("Helvetica", 5)

        for comp_n, z_list in sorted(rayons_par_comp.items()):
            z_sorted = sorted(z_list)
            ci = comp_n - 1
            if ci * 2 + 1 >= len(edges_comp):
                continue

            x_l = edges_comp[ci * 2]
            x_r = edges_comp[ci * 2 + 1]
            x_mid = (x_l + x_r) / 2
            x_cot = ox + x_mid * scale

            niveaux = [0.0] + z_sorted + [z_plafond]

            c.setStrokeColor(coul_vert)
            c.setFillColor(coul_vert)
            c.setLineWidth(0.4)

            for i in range(len(niveaux) - 1):
                z_bas = niveaux[i]
                z_haut = niveaux[i + 1]
                h_val = z_haut - z_bas

                yb = oy + z_bas * scale
                yh = oy + z_haut * scale

                # Ligne verticale + fleches
                c.line(x_cot, yb, x_cot, yh)
                _fleche_v(x_cot, yb, False)
                _fleche_v(x_cot, yh, True)

                # Texte a droite de la ligne
                y_mid = (yb + yh) / 2
                c.drawString(x_cot + 5, y_mid - 2, f"{h_val:.0f}")


# =========================================================================
#  TABLEAU GENERIQUE
# =========================================================================

def _dessiner_tableau(c: canvas.Canvas, tab_x: float, tab_w: float,
                      y_start: float, row_h: float, font_size: float,
                      cols: list[tuple[str, int]],
                      rows_data: list[list[str]]) -> float:
    """Dessine un tableau avec en-tete et lignes. Retourne y apres le tableau."""
    y = y_start

    # En-tete
    c.setFillColor(colors.Color(0.2, 0.2, 0.2))
    c.rect(tab_x, y - row_h, tab_w, row_h, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", font_size)
    c.setFillColor(colors.white)
    cx = tab_x + 2
    for col_name, col_w in cols:
        c.drawString(cx, y - row_h + 2, col_name)
        cx += col_w
    y -= row_h

    # Lignes de donnees
    c.setFont("Helvetica", font_size)
    nb_drawn = 0
    for i, row in enumerate(rows_data):
        if i % 2 == 1:
            c.setFillColor(colors.Color(0.95, 0.95, 0.95))
            c.rect(tab_x, y - row_h, tab_w, row_h, fill=1, stroke=0)
        c.setFillColor(colors.black)
        cx = tab_x + 2
        for j, (_, col_w) in enumerate(cols):
            c.drawString(cx, y - row_h + 2, row[j])
            cx += col_w
        y -= row_h
        nb_drawn += 1

    # Grille
    table_top = y_start
    table_bottom = y
    c.setStrokeColor(colors.grey)
    c.setLineWidth(0.3)
    for r_idx in range(nb_drawn + 2):
        y_line = table_top - r_idx * row_h
        c.line(tab_x, y_line, tab_x + tab_w, y_line)
    cx = tab_x
    for _, col_w in cols:
        c.line(cx, table_top, cx, table_bottom)
        cx += col_w
    c.line(tab_x + tab_w, table_top, tab_x + tab_w, table_bottom)

    return y


# =========================================================================
#  CALCUL TAILLES ADAPTATIVES
# =========================================================================

def _calculer_tailles(nb_pieces: int, nb_quinc: int, nb_materiaux: int,
                      nb_chants: int, hauteur_dispo: float) -> tuple[float, float]:
    """Calcule row_h et font_size pour faire tenir tout le contenu."""
    espace_fixe = (
        12      # titre fiche
        + 4     # gap apres pieces
        + 10    # ligne surface
        + 14    # gap avant quincaillerie
    )
    if nb_quinc > 0:
        espace_fixe += 12  # titre quincaillerie
    if nb_materiaux > 0:
        espace_fixe += 20  # titre resume + gap
        espace_fixe += nb_materiaux * 9
    if nb_chants > 0:
        espace_fixe += 20  # titre chants + gap
        espace_fixe += nb_chants * 9
    espace_fixe += 16  # note etiquettes

    nb_lignes = (1 + nb_pieces)
    if nb_quinc > 0:
        nb_lignes += (1 + nb_quinc)

    espace_tableau = hauteur_dispo - espace_fixe
    if nb_lignes <= 0:
        return 10, 6.5

    row_h = espace_tableau / nb_lignes
    row_h = max(6, min(11, row_h))
    font_size = max(4.5, min(6.5, row_h * 0.65))

    return row_h, font_size


# =========================================================================
#  DESSIN D'UNE PAGE COMPLETE
# =========================================================================

def _dessiner_page(c: canvas.Canvas, rects: list[PlacardRect], config: dict,
                   fiche: FicheFabrication, projet_info: dict | None,
                   amenagement_nom: str | None,
                   projet_id: int, amenagement_id: int):
    """Dessine une page complete (cartouche + vue de face + fiche de debit)."""
    page_w, page_h = landscape(A4)
    marge = 10 * mm

    # Attribuer les references
    _attribuer_references(fiche, projet_id, amenagement_id)

    # =================================================================
    #  CARTOUCHE (en haut)
    # =================================================================
    y_cartouche = page_h - marge
    nom_projet = projet_info.get("nom", "Projet") if projet_info else "Projet"
    client = projet_info.get("client", "") if projet_info else ""
    adresse = projet_info.get("adresse", "") if projet_info else ""

    titre = f"PlacardCAD - {nom_projet}"
    if amenagement_nom:
        titre += f" - {amenagement_nom}"

    c.setFont("Helvetica-Bold", 12)
    c.drawString(marge, y_cartouche, titre)

    c.setFont("Helvetica", 8)
    info_parts = []
    if client:
        info_parts.append(f"Client: {client}")
    if adresse:
        info_parts.append(f"Adresse: {adresse}")
    info_parts.append(f"Date: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    info_parts.append(f"Dim: {config['largeur']:.0f}x{config['hauteur']:.0f}x{config['profondeur']:.0f}mm")
    c.drawString(marge, y_cartouche - 14, "  |  ".join(info_parts))

    # Trait de separation
    y_sep = y_cartouche - 20
    c.setStrokeColor(colors.grey)
    c.setLineWidth(0.5)
    c.line(marge, y_sep, page_w - marge, y_sep)

    # =================================================================
    #  VUE DE FACE (moitie gauche)
    # =================================================================
    vue_w = (page_w - 3 * marge) * 0.48
    vue_h = y_sep - marge - 5
    vue_x = marge
    vue_y = marge

    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.black)
    c.drawString(vue_x, y_sep - 12, "Vue de face")

    _dessiner_vue_face(c, rects, config["largeur"], config["hauteur"],
                       vue_x, vue_y, vue_w, vue_h - 15)

    # =================================================================
    #  FICHE DE DEBIT + QUINCAILLERIE (moitie droite)
    # =================================================================
    tab_x = marge + vue_w + marge
    tab_w = page_w - tab_x - marge

    # Pre-calculer resume materiaux et chants
    materiaux = {}
    for p in fiche.pieces:
        key = (p.epaisseur, p.couleur_fab, p.materiau)
        if key not in materiaux:
            materiaux[key] = {"surface": 0, "nb": 0}
        materiaux[key]["surface"] += p.longueur * p.largeur * p.quantite / 1e6
        materiaux[key]["nb"] += p.quantite

    chants = _calculer_chants(fiche)

    # Tailles adaptees
    hauteur_dispo = y_sep - 12 - marge
    row_h, font_size = _calculer_tailles(
        len(fiche.pieces), len(fiche.quincaillerie),
        len(materiaux), len(chants), hauteur_dispo
    )

    y_cursor = y_sep - 12

    # --- Titre fiche ---
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.black)
    c.drawString(tab_x, y_cursor, "Fiche de debit")
    y_cursor -= 12

    # --- Tableau pieces ---
    p_cols = [
        ("Ref.", 52),
        ("Designation", 115),
        ("Long.", 36),
        ("Larg.", 36),
        ("Ep.", 26),
        ("Qte", 22),
        ("Chant", 65),
    ]
    p_rows = []
    for p in fiche.pieces:
        p_rows.append([
            p.reference,
            p.nom[:28],
            f"{p.longueur:.0f}",
            f"{p.largeur:.0f}",
            f"{p.epaisseur:.0f}",
            str(p.quantite),
            p.chant_desc[:16],
        ])

    y_cursor = _dessiner_tableau(c, tab_x, tab_w, y_cursor, row_h, font_size,
                                 p_cols, p_rows)

    # --- Surface totale ---
    y_cursor -= 4
    surface = sum(p.longueur * p.largeur * p.quantite / 1e6 for p in fiche.pieces)
    c.setFont("Helvetica-Bold", font_size)
    c.setFillColor(colors.black)
    c.drawString(tab_x, y_cursor, f"Surface totale : {surface:.2f} m2")
    y_cursor -= 14

    # --- Quincaillerie ---
    if fiche.quincaillerie:
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(colors.black)
        c.drawString(tab_x, y_cursor, "Quincaillerie")
        y_cursor -= 12

        q_cols = [("Designation", 170), ("Qte", 30), ("Description", 152)]
        q_rows = []
        for q in fiche.quincaillerie:
            q_rows.append([q["nom"][:42], str(q["quantite"]), q["description"][:38]])

        y_cursor = _dessiner_tableau(c, tab_x, tab_w, y_cursor, row_h, font_size,
                                     q_cols, q_rows)

    # --- Chants ---
    if chants and y_cursor > marge + 30:
        y_cursor -= 10
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(colors.black)
        c.drawString(tab_x, y_cursor, "Chants (metrage total)")
        y_cursor -= 10

        c.setFont("Helvetica", font_size)
        for (couleur, ep_chant), longueur_mm in chants.items():
            if y_cursor < marge:
                break
            ml = longueur_mm / 1000
            c.drawString(tab_x, y_cursor,
                         f"{couleur} ep.{ep_chant}mm : {ml:.1f} ml")
            y_cursor -= 9

    # --- Resume materiaux ---
    if materiaux and y_cursor > marge + 20:
        y_cursor -= 10
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(colors.black)
        c.drawString(tab_x, y_cursor, "Resume materiaux")
        y_cursor -= 10

        c.setFont("Helvetica", font_size)
        for (ep, coul, mat), info in materiaux.items():
            if y_cursor < marge:
                break
            c.drawString(tab_x, y_cursor,
                         f"{mat} {ep:.0f}mm {coul}: {info['surface']:.2f}m2 ({info['nb']} pcs)")
            y_cursor -= 9

    # --- Note etiquettes ---
    y_cursor -= 6
    if y_cursor > marge + 5:
        c.setFont("Helvetica-Oblique", 6)
        c.setFillColor(colors.grey)
        c.drawString(tab_x, y_cursor,
                     "Ref. format: P{projet}/A{amenagement}/N{piece} - a reporter sur etiquettes panneaux")


# =========================================================================
#  COULEURS PLAN DE DEBIT
# =========================================================================

COULEURS_PIECES_DEBIT = [
    colors.Color(0.78, 0.88, 1.0),
    colors.Color(0.88, 1.0, 0.78),
    colors.Color(1.0, 0.88, 0.78),
    colors.Color(1.0, 0.78, 0.88),
    colors.Color(0.88, 0.78, 1.0),
    colors.Color(0.78, 1.0, 0.88),
    colors.Color(1.0, 1.0, 0.78),
    colors.Color(0.90, 0.90, 0.90),
]


# =========================================================================
#  DESSIN PAGE PLAN DE DEBIT
# =========================================================================

def _dessiner_page_debit(c: canvas.Canvas, plan: PlanDecoupe,
                         params: ParametresDebit,
                         numero: int, total: int,
                         projet_info: dict | None,
                         amenagement_nom: str | None):
    """Dessine une page de plan de debit pour un panneau."""
    page_w, page_h = landscape(A4)
    marge = 10 * mm

    # --- Cartouche ---
    y_top = page_h - marge
    nom_projet = projet_info.get("nom", "Projet") if projet_info else "Projet"
    titre = f"Plan de debit - Panneau {numero}/{total}"
    if amenagement_nom:
        titre += f" - {amenagement_nom}"

    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.black)
    c.drawString(marge, y_top, titre)

    c.setFont("Helvetica", 8)
    info = f"{nom_projet}  |  {plan.couleur} ep.{plan.epaisseur:.0f}mm"
    info += f"  |  Panneau brut: {params.panneau_longueur:.0f}x{params.panneau_largeur:.0f}mm"
    info += f"  |  Trait scie: {params.trait_scie:.0f}mm  Surcote: {params.surcote:.0f}mm  Delig.: {params.delignage:.0f}mm"
    c.drawString(marge, y_top - 13, info)

    y_sep = y_top - 20
    c.setStrokeColor(colors.grey)
    c.setLineWidth(0.5)
    c.line(marge, y_sep, page_w - marge, y_sep)

    # --- Zone de dessin du panneau ---
    draw_x = marge
    draw_y = marge + 60  # place pour legende en bas
    draw_w = page_w - 2 * marge
    draw_h = y_sep - draw_y - 15

    pl = plan.panneau_l
    pw = plan.panneau_w

    scale = min(draw_w / pl, draw_h / pw) * 0.92
    ox = draw_x + (draw_w - pl * scale) / 2
    oy = draw_y + (draw_h - pw * scale) / 2

    # --- Dessiner le panneau ---
    c.setFillColor(colors.Color(0.96, 0.94, 0.90))
    c.setStrokeColor(colors.Color(0.4, 0.35, 0.3))
    c.setLineWidth(1)
    c.rect(ox, oy, pl * scale, pw * scale, fill=1)

    # Dimensions du panneau
    c.setFont("Helvetica", 6)
    c.setFillColor(colors.Color(0.4, 0.35, 0.3))
    c.drawCentredString(ox + pl * scale / 2, oy - 8, f"{pl:.0f} mm")
    c.saveState()
    c.translate(ox - 6, oy + pw * scale / 2)
    c.rotate(90)
    c.drawCentredString(0, 0, f"{pw:.0f} mm")
    c.restoreState()

    # --- Dessiner les pieces ---
    nb_couleurs = len(COULEURS_PIECES_DEBIT)
    legende = []

    for idx, plc in enumerate(plan.placements):
        couleur_fill = COULEURS_PIECES_DEBIT[idx % nb_couleurs]

        if plc.rotation:
            pw_piece = plc.largeur_debit * scale
            ph_piece = plc.longueur_debit * scale
        else:
            pw_piece = plc.longueur_debit * scale
            ph_piece = plc.largeur_debit * scale

        px = ox + plc.x * scale
        py = oy + plc.y * scale

        # Rectangle piece
        c.setFillColor(couleur_fill)
        c.setStrokeColor(colors.Color(0.3, 0.3, 0.3))
        c.setLineWidth(0.5)
        c.rect(px, py, pw_piece, ph_piece, fill=1)

        # Texte dans la piece
        cx_piece = px + pw_piece / 2
        cy_piece = py + ph_piece / 2

        ref = plc.piece.reference
        dim_txt = f"{plc.piece.longueur:.0f}x{plc.piece.largeur:.0f}"

        # Adapter la taille du texte a la piece
        font_sz = min(7, pw_piece / 8, ph_piece / 4)
        font_sz = max(3.5, font_sz)

        c.setFont("Helvetica-Bold", font_sz)
        c.setFillColor(colors.Color(0.15, 0.15, 0.15))
        c.drawCentredString(cx_piece, cy_piece + font_sz * 0.3, ref)
        c.setFont("Helvetica", font_sz * 0.85)
        c.drawCentredString(cx_piece, cy_piece - font_sz * 0.7, dim_txt)

        if plc.rotation:
            c.setFont("Helvetica-Oblique", font_sz * 0.7)
            c.setFillColor(colors.red)
            c.drawCentredString(cx_piece, cy_piece - font_sz * 1.5, "R")

        legende.append((ref, plc.piece.nom))

    # --- Resume en bas ---
    y_res = marge + 48
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.black)
    nb = len(plan.placements)
    c.drawString(marge, y_res,
                 f"Pieces: {nb}  |  Chute: {plan.pct_chute:.1f}%"
                 f"  |  Surface utile: {plan.surface_pieces:.3f} m2"
                 f"  /  {plan.surface_panneau:.3f} m2")

    # Legende
    y_leg = y_res - 12
    c.setFont("Helvetica", 5.5)
    c.setFillColor(colors.Color(0.3, 0.3, 0.3))
    x_leg = marge
    for ref, nom in legende:
        txt = f"{ref}={nom[:25]}"
        tw = c.stringWidth(txt, "Helvetica", 5.5)
        if x_leg + tw + 12 > page_w - marge:
            y_leg -= 8
            x_leg = marge
        if y_leg < marge:
            break
        c.drawString(x_leg, y_leg, txt)
        x_leg += tw + 12

    # --- Filigrane couleur/epaisseur par-dessus (semi-transparent) ---
    filigrane = f"{plan.couleur} - ep.{plan.epaisseur:.0f}mm"
    c.saveState()
    c.setFillColor(colors.Color(0.35, 0.33, 0.30, alpha=0.25))
    fil_size = min(18, pl * scale / max(len(filigrane), 1) * 1.2)
    fil_size = max(10, fil_size)
    c.setFont("Helvetica-Bold", fil_size)
    for fx, fy in [(0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)]:
        c.drawCentredString(
            ox + pl * scale * fx,
            oy + pw * scale * fy,
            filigrane
        )
    c.restoreState()


def _generer_et_dessiner_debit(c: canvas.Canvas, fiche: FicheFabrication,
                                projet_info: dict | None,
                                amenagement_nom: str | None,
                                projet_id: int, amenagement_id: int,
                                params_debit: ParametresDebit | None = None):
    """Genere les plans de debit et dessine les pages correspondantes."""
    if params_debit is None:
        params_debit = ParametresDebit()

    pieces = pieces_depuis_fiche(fiche, projet_id, amenagement_id)
    if not pieces:
        return

    plans, hors_gabarit = optimiser_debit(pieces, params_debit)

    total = len(plans)
    for i, plan in enumerate(plans):
        c.showPage()
        _dessiner_page_debit(c, plan, params_debit, i + 1, total,
                             projet_info, amenagement_nom)

    # Page d'alerte si pieces hors gabarit
    if hors_gabarit:
        c.showPage()
        page_w, page_h = landscape(A4)
        m = 10 * mm
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.red)
        c.drawString(m, page_h - m, "Pieces hors gabarit (ne rentrent pas dans un panneau)")
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.black)
        y = page_h - m - 25
        for p in hors_gabarit:
            c.drawString(m, y,
                         f"{p.reference} - {p.nom}: {p.longueur:.0f}x{p.largeur:.0f}mm "
                         f"(x{p.quantite})")
            y -= 14
            if y < m:
                break


# =========================================================================
#  DESSIN DEBIT MIXTE (toutes pieces confondues)
# =========================================================================

def _dessiner_page_pieces_manuelles(c: canvas.Canvas, pieces_manuelles: list,
                                     projet_info: dict | None):
    """Dessine une page fiche de debit dediee aux pieces manuelles (complementaires)."""
    page_w, page_h = landscape(A4)
    marge = 10 * mm

    # --- Cartouche ---
    y_top = page_h - marge
    nom_projet = projet_info.get("nom", "Projet") if projet_info else "Projet"
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(colors.black)
    c.drawString(marge, y_top, f"PlacardCAD - {nom_projet}")

    c.setFont("Helvetica", 8)
    info_parts = []
    if projet_info:
        if projet_info.get("client"):
            info_parts.append(f"Client: {projet_info['client']}")
        if projet_info.get("adresse"):
            info_parts.append(f"Adresse: {projet_info['adresse']}")
    info_parts.append(f"Date: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    c.drawString(marge, y_top - 14, "  |  ".join(info_parts))

    y_sep = y_top - 20
    c.setStrokeColor(colors.grey)
    c.setLineWidth(0.5)
    c.line(marge, y_sep, page_w - marge, y_sep)

    # --- Titre ---
    y_cursor = y_sep - 15
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.black)
    c.drawString(marge, y_cursor, "Fiche de debit \u2014 Pieces complementaires")
    y_cursor -= 16

    # --- Tailles adaptees ---
    nb_pieces = len(pieces_manuelles)
    hauteur_dispo = y_cursor - marge - 60
    row_h = hauteur_dispo / max(nb_pieces + 1, 2)
    row_h = max(8, min(14, row_h))
    font_size = max(5, min(8, row_h * 0.65))

    # --- Tableau ---
    tab_w = page_w - 2 * marge
    cols = [
        ("Ref.", 80),
        ("Designation", 220),
        ("Long.", 55),
        ("Larg.", 55),
        ("Ep.", 40),
        ("Couleur / Decor", 205),
        ("Fil", 40),
        ("Qte", 40),
    ]

    rows = []
    for p in pieces_manuelles:
        rows.append([
            p.reference,
            p.nom[:45],
            f"{p.longueur:.0f}",
            f"{p.largeur:.0f}",
            f"{p.epaisseur:.0f}",
            p.couleur[:40],
            "Oui" if p.sens_fil else "Non",
            str(p.quantite),
        ])

    y_cursor = _dessiner_tableau(c, marge, tab_w, y_cursor, row_h, font_size,
                                 cols, rows)

    # --- Surface totale + comptage ---
    y_cursor -= 8
    surface = sum(p.longueur * p.largeur * p.quantite / 1e6
                  for p in pieces_manuelles)
    nb_total = sum(p.quantite for p in pieces_manuelles)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.black)
    c.drawString(marge, y_cursor,
                 f"Surface totale : {surface:.2f} m\u00b2  |  "
                 f"{nb_pieces} reference(s)  |  {nb_total} piece(s)")
    y_cursor -= 18

    # --- Resume materiaux ---
    materiaux: dict[tuple, dict] = {}
    for p in pieces_manuelles:
        key = (p.epaisseur, p.couleur)
        if key not in materiaux:
            materiaux[key] = {"surface": 0, "nb": 0}
        materiaux[key]["surface"] += p.longueur * p.largeur * p.quantite / 1e6
        materiaux[key]["nb"] += p.quantite

    if materiaux and y_cursor > marge + 20:
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(colors.black)
        c.drawString(marge, y_cursor, "Resume materiaux")
        y_cursor -= 12

        c.setFont("Helvetica", 7)
        for (ep, coul), info in materiaux.items():
            if y_cursor < marge:
                break
            c.drawString(marge + 10, y_cursor,
                         f"{coul} ep.{ep:.0f}mm : {info['surface']:.2f} m\u00b2"
                         f" ({info['nb']} pieces)")
            y_cursor -= 10


def _dessiner_debit_mixte(c: canvas.Canvas, all_pieces: list,
                          params_debit: ParametresDebit,
                          projet_info: dict | None):
    """Dessine les pages de debit pour un ensemble de pieces mixtes."""
    if not all_pieces:
        return

    plans, hors_gabarit = optimiser_debit(all_pieces, params_debit)

    total = len(plans)
    for i, plan in enumerate(plans):
        c.showPage()
        _dessiner_page_debit(c, plan, params_debit, i + 1, total,
                             projet_info, "Tous amenagements")

    if hors_gabarit:
        c.showPage()
        page_w, page_h = landscape(A4)
        m = 10 * mm
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.red)
        c.drawString(m, page_h - m,
                     "Pieces hors gabarit (ne rentrent pas dans un panneau)")
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.black)
        y = page_h - m - 25
        for p in hors_gabarit:
            c.drawString(m, y,
                         f"{p.reference} - {p.nom}: "
                         f"{p.longueur:.0f}x{p.largeur:.0f}mm (x{p.quantite})")
            y -= 14
            if y < m:
                break


# =========================================================================
#  EXPORT PDF STANDALONE - PLANS DE DEBIT SEULEMENT
# =========================================================================

def _dessiner_pages_liste_pieces(c: canvas.Canvas, all_pieces: list,
                                  projet_info: dict | None,
                                  titre: str = "Optimisation de debit"):
    """Dessine une ou plusieurs pages avec la liste des pieces a decouper.

    Gere la pagination si le nombre de pieces depasse la capacite d'une page.
    Les pieces sont triees par (couleur, epaisseur, nom).
    """
    page_w, page_h = landscape(A4)
    marge = 10 * mm

    # Trier par couleur, epaisseur, nom
    pieces_triees = sorted(all_pieces, key=lambda p: (p.couleur, p.epaisseur, p.nom))

    # Colonnes du tableau
    tab_w = page_w - 2 * marge
    cols = [
        ("Ref.", 80),
        ("Designation", 200),
        ("Long.", 55),
        ("Larg.", 55),
        ("Ep.", 40),
        ("Couleur / Decor", 210),
        ("Fil", 40),
        ("Qte", 40),
    ]

    row_h = 11
    font_size = 7

    # Preparer toutes les lignes
    all_rows = []
    for p in pieces_triees:
        all_rows.append([
            p.reference,
            p.nom[:42],
            f"{p.longueur:.0f}",
            f"{p.largeur:.0f}",
            f"{p.epaisseur:.0f}",
            p.couleur[:40],
            "Oui" if p.sens_fil else "Non",
            str(p.quantite),
        ])

    # Calculer les capacites
    y_top_content = page_h - marge - 20 - 15  # apres cartouche + titre
    y_bottom = marge + 10
    rows_per_page = int((y_top_content - y_bottom) / row_h) - 1  # -1 pour en-tete
    if rows_per_page < 5:
        rows_per_page = 5

    nb_pages = max(1, (len(all_rows) + rows_per_page - 1) // rows_per_page)

    nom_projet = projet_info.get("nom", "Projet") if projet_info else "Projet"

    for page_idx in range(nb_pages):
        if page_idx > 0:
            c.showPage()

        start = page_idx * rows_per_page
        end = min(start + rows_per_page, len(all_rows))
        page_rows = all_rows[start:end]

        # --- Cartouche ---
        y_top = page_h - marge
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.black)
        titre_page = f"Liste des pieces a decouper \u2014 {nom_projet}"
        if nb_pages > 1:
            titre_page += f" ({page_idx + 1}/{nb_pages})"
        c.drawString(marge, y_top, titre_page)

        c.setFont("Helvetica", 8)
        info_parts = []
        if projet_info:
            if projet_info.get("client"):
                info_parts.append(f"Client: {projet_info['client']}")
        info_parts.append(f"Date: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        info_parts.append(f"{len(all_pieces)} references | "
                          f"{sum(p.quantite for p in all_pieces)} pieces au total")
        c.drawString(marge, y_top - 14, "  |  ".join(info_parts))

        y_sep = y_top - 20
        c.setStrokeColor(colors.grey)
        c.setLineWidth(0.5)
        c.line(marge, y_sep, page_w - marge, y_sep)

        # --- Tableau ---
        y_cursor = y_sep - 4
        y_cursor = _dessiner_tableau(c, marge, tab_w, y_cursor, row_h, font_size,
                                     cols, page_rows)

    # --- Resume materiaux + surface (sur la derniere page) ---
    y_cursor -= 10
    surface = sum(p.longueur * p.largeur * p.quantite / 1e6 for p in all_pieces)
    nb_total = sum(p.quantite for p in all_pieces)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.black)
    c.drawString(marge, y_cursor,
                 f"Surface totale : {surface:.2f} m\u00b2  |  "
                 f"{len(all_pieces)} reference(s)  |  {nb_total} piece(s)")
    y_cursor -= 16

    materiaux: dict[tuple, dict] = {}
    for p in all_pieces:
        key = (p.epaisseur, p.couleur)
        if key not in materiaux:
            materiaux[key] = {"surface": 0, "nb": 0}
        materiaux[key]["surface"] += p.longueur * p.largeur * p.quantite / 1e6
        materiaux[key]["nb"] += p.quantite

    if materiaux and y_cursor > marge + 15:
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(colors.black)
        c.drawString(marge, y_cursor, "Resume materiaux")
        y_cursor -= 12

        c.setFont("Helvetica", 7)
        for (ep, coul), info in materiaux.items():
            if y_cursor < marge:
                break
            c.drawString(marge + 10, y_cursor,
                         f"{coul} ep.{ep:.0f}mm : {info['surface']:.2f} m\u00b2"
                         f" ({info['nb']} pieces)")
            y_cursor -= 10


def exporter_pdf_debit(filepath: str, all_pieces: list,
                       params_debit: ParametresDebit,
                       projet_info: dict | None = None,
                       titre: str = "Optimisation de debit") -> str:
    """Exporte un PDF avec liste des pieces + plans de debit + resume."""
    plans, hors_gabarit = optimiser_debit(all_pieces, params_debit)

    c = canvas.Canvas(filepath, pagesize=landscape(A4))

    # Pages de la liste des pieces a decouper
    _dessiner_pages_liste_pieces(c, all_pieces, projet_info, titre)

    # Pages plans de debit
    total = len(plans)
    for i, plan in enumerate(plans):
        c.showPage()
        _dessiner_page_debit(c, plan, params_debit, i + 1, total,
                             projet_info, titre)

    if hors_gabarit:
        c.showPage()
        page_w, page_h = landscape(A4)
        m = 10 * mm
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.red)
        c.drawString(m, page_h - m, "Pieces hors gabarit")
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.black)
        y = page_h - m - 25
        for p in hors_gabarit:
            c.drawString(m, y,
                         f"{p.reference} - {p.nom}: {p.longueur:.0f}x{p.largeur:.0f}mm "
                         f"(x{p.quantite})")
            y -= 14
            if y < m:
                break

    # Page resume
    c.showPage()
    _dessiner_resume_debit(c, plans, hors_gabarit, params_debit, projet_info, titre)

    c.save()
    return filepath


def _dessiner_resume_debit(c: canvas.Canvas, plans: list[PlanDecoupe],
                           hors_gabarit: list, params: ParametresDebit,
                           projet_info: dict | None, titre: str):
    """Page resume de l'optimisation de debit."""
    page_w, page_h = landscape(A4)
    m = 10 * mm

    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(colors.black)
    c.drawString(m, page_h - m, f"Resume - {titre}")

    nom = projet_info.get("nom", "") if projet_info else ""
    if nom:
        c.setFont("Helvetica", 10)
        c.drawString(m, page_h - m - 18, f"Projet: {nom}")

    y = page_h - m - 45
    c.setFont("Helvetica", 9)

    # Regrouper par (epaisseur, couleur)
    groupes: dict[tuple, list[PlanDecoupe]] = {}
    for plan in plans:
        key = (plan.epaisseur, plan.couleur)
        groupes.setdefault(key, []).append(plan)

    for (ep, coul), plans_g in groupes.items():
        nb_panneaux = len(plans_g)
        surf_totale = sum(p.surface_panneau for p in plans_g)
        surf_pieces = sum(p.surface_pieces for p in plans_g)
        chute_moy = (1 - surf_pieces / surf_totale) * 100 if surf_totale > 0 else 0

        c.setFont("Helvetica-Bold", 9)
        c.drawString(m, y, f"{coul} ep.{ep:.0f}mm")
        y -= 14

        c.setFont("Helvetica", 9)
        c.drawString(m + 10, y,
                     f"Panneaux: {nb_panneaux} x "
                     f"({params.panneau_longueur:.0f}x{params.panneau_largeur:.0f}mm)")
        y -= 13
        c.drawString(m + 10, y,
                     f"Surface pieces: {surf_pieces:.3f} m2  |  "
                     f"Surface panneaux: {surf_totale:.3f} m2  |  "
                     f"Chute moyenne: {chute_moy:.1f}%")
        y -= 20

    if hors_gabarit:
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(colors.red)
        c.drawString(m, y, f"Pieces hors gabarit: {len(hors_gabarit)}")
        y -= 13
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.black)
        for p in hors_gabarit:
            c.drawString(m + 10, y,
                         f"{p.nom}: {p.longueur:.0f}x{p.largeur:.0f}mm (x{p.quantite})")
            y -= 11
            if y < m:
                break


# =========================================================================
#  EXPORT PDF - UN AMENAGEMENT (une page)
# =========================================================================

def exporter_pdf(filepath: str, rects: list[PlacardRect], config: dict,
                 fiche: FicheFabrication, projet_info: dict | None = None,
                 projet_id: int = 0, amenagement_id: int = 0,
                 params_debit: ParametresDebit | None = None,
                 all_pieces_projet: list | None = None,
                 pieces_manuelles: list | None = None):
    """Exporte un PDF: page amenagement + fiche pieces manuelles + plans de debit.

    Si all_pieces_projet est fourni, le debit est mixte (toutes les pieces
    du projet ensemble). Sinon, seul cet amenagement est optimise.
    pieces_manuelles: liste optionnelle de PieceDebit complementaires.
    """
    if params_debit is None:
        params_debit = ParametresDebit()

    c = canvas.Canvas(filepath, pagesize=landscape(A4))
    _dessiner_page(c, rects, config, fiche, projet_info, None,
                   projet_id, amenagement_id)

    # Page fiche de debit pour les pieces manuelles
    if pieces_manuelles:
        c.showPage()
        _dessiner_page_pieces_manuelles(c, pieces_manuelles, projet_info)

    if all_pieces_projet:
        # Debit mixte avec toutes les pieces du projet
        _dessiner_debit_mixte(c, all_pieces_projet, params_debit, projet_info)
    else:
        # Debit pour cet amenagement seul
        _generer_et_dessiner_debit(c, fiche, projet_info, None,
                                    projet_id, amenagement_id, params_debit)
    c.save()
    return filepath


# =========================================================================
#  EXPORT PDF - PROJET COMPLET (une page par amenagement)
# =========================================================================

def exporter_pdf_projet(filepath: str, amenagements_data: list[dict],
                        projet_info: dict | None = None,
                        projet_id: int = 0,
                        params_debit: ParametresDebit | None = None,
                        pieces_manuelles: list | None = None) -> str:
    """
    Exporte un PDF multi-pages avec une page par amenagement + plans de debit mixtes.

    Les pieces de tous les amenagements sont regroupees pour une optimisation
    globale du debit, ce qui reduit les chutes en remplissant mieux les panneaux.

    amenagements_data: liste de dicts avec cles:
        - rects: list[Rect]
        - config: dict
        - fiche: FicheFabrication
        - nom: str (nom de l'amenagement)
        - amenagement_id: int
    pieces_manuelles: liste optionnelle de PieceDebit complementaires.
    """
    if params_debit is None:
        params_debit = ParametresDebit()

    c = canvas.Canvas(filepath, pagesize=landscape(A4))

    # --- Pages fiche par amenagement ---
    all_pieces = []
    for i, am in enumerate(amenagements_data):
        if i > 0:
            c.showPage()
        _dessiner_page(
            c, am["rects"], am["config"], am["fiche"],
            projet_info, am.get("nom"),
            projet_id, am.get("amenagement_id", 0),
        )
        # Collecter les pieces de cet amenagement pour le debit global
        am_pieces = pieces_depuis_fiche(
            am["fiche"], projet_id, am.get("amenagement_id", 0)
        )
        all_pieces.extend(am_pieces)

    # Ajouter les pieces manuelles
    if pieces_manuelles:
        all_pieces.extend(pieces_manuelles)

    # --- Page fiche de debit pour les pieces manuelles ---
    if pieces_manuelles:
        c.showPage()
        _dessiner_page_pieces_manuelles(c, pieces_manuelles, projet_info)

    # --- Plans de debit mixtes (toutes pieces confondues) ---
    _dessiner_debit_mixte(c, all_pieces, params_debit, projet_info)

    c.save()
    return filepath
