"""
Export PDF pour PlacardCAD.

Genere un document PDF sur UNE SEULE PAGE (paysage A4) contenant:
- A gauche : Vue de face filaire avec cotations
- A droite : Fiche de debit + quincaillerie
- Cartouche en haut
- References panneaux pour etiquettes (format P{projet}/A{amenagement}/N{piece})
"""

from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect, Line, String, Group
from reportlab.pdfgen import canvas

from .placard_builder import Rect as PlacardRect, FicheFabrication


# =========================================================================
#  COULEURS
# =========================================================================

COULEURS_TYPE = {
    "mur": (colors.Color(0.9, 0.9, 0.88), colors.Color(0.7, 0.7, 0.68)),
    "separation": (colors.Color(0.82, 0.71, 0.55), colors.Color(0.55, 0.45, 0.33)),
    "rayon_haut": (colors.Color(0.87, 0.74, 0.53), colors.Color(0.55, 0.45, 0.33)),
    "rayon": (colors.Color(0.82, 0.71, 0.55), colors.Color(0.55, 0.45, 0.33)),
    "cremaillere": (colors.Color(0.63, 0.63, 0.63), colors.Color(0.44, 0.5, 0.56)),
    "panneau_mur": (colors.Color(0.82, 0.71, 0.55), colors.Color(0.55, 0.45, 0.33)),
    "tasseau": (colors.Color(0.85, 0.65, 0.13), colors.Color(0.55, 0.41, 0.08)),
}


def _attribuer_references(fiche: FicheFabrication, projet_id: int = 0,
                          amenagement_id: int = 0):
    """Attribue une reference unique a chaque piece : P{projet}/A{amenag}/N{numero}."""
    p_id = projet_id or 0
    a_id = amenagement_id or 0
    for i, piece in enumerate(fiche.pieces, 1):
        piece.reference = f"P{p_id}/A{a_id}/N{i:02d}"


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
    mur_ep = 50
    total_w = largeur_placard + 2 * mur_ep
    total_h = hauteur_placard + 2 * mur_ep

    view_w = draw_w - 2 * marge
    view_h = draw_h - 2 * marge

    scale = min(view_w / total_w, view_h / total_h)
    ox = x_orig + marge + (view_w - total_w * scale) / 2 + mur_ep * scale
    oy = y_orig + marge + (view_h - total_h * scale) / 2 + mur_ep * scale

    # Dessiner les rectangles
    ordre = ["mur", "panneau_mur", "separation", "rayon_haut", "rayon", "cremaillere", "tasseau"]
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

            c.setFillColor(fill_color)
            c.setStrokeColor(stroke_color)
            c.setLineWidth(0.5)
            c.rect(sx, sy, sw, sh, fill=1)

    # --- Cotations ---
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.5)
    c.setFont("Helvetica", 7)
    c.setFillColor(colors.black)

    # Largeur (en bas)
    y_cot = oy - 15
    x_left = ox
    x_right = ox + largeur_placard * scale
    c.line(x_left, y_cot, x_right, y_cot)
    c.setStrokeColor(colors.grey)
    c.setLineWidth(0.3)
    c.line(x_left, oy, x_left, y_cot - 3)
    c.line(x_right, oy, x_right, y_cot - 3)
    c.setFillColor(colors.black)
    c.drawCentredString((x_left + x_right) / 2, y_cot - 10, f"{largeur_placard:.0f} mm")

    # Hauteur (a gauche)
    x_cot = ox - 15
    y_bottom = oy
    y_top = oy + hauteur_placard * scale
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.5)
    c.line(x_cot, y_bottom, x_cot, y_top)
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


# =========================================================================
#  GENERATION PDF - TOUT SUR UNE PAGE
# =========================================================================

def exporter_pdf(filepath: str, rects: list[PlacardRect], config: dict,
                 fiche: FicheFabrication, projet_info: dict | None = None,
                 projet_id: int = 0, amenagement_id: int = 0):
    """
    Exporte un PDF sur une seule page paysage A4.

    Layout:
      - Cartouche en haut (toute largeur)
      - Gauche: vue de face
      - Droite: fiche de debit + quincaillerie
    """
    page_w, page_h = landscape(A4)
    marge = 10 * mm

    # Attribuer les references
    _attribuer_references(fiche, projet_id, amenagement_id)

    c = canvas.Canvas(filepath, pagesize=landscape(A4))

    # =====================================================================
    #  CARTOUCHE (en haut)
    # =====================================================================
    y_cartouche = page_h - marge
    nom_projet = projet_info.get("nom", "Projet") if projet_info else "Projet"
    client = projet_info.get("client", "") if projet_info else ""
    adresse = projet_info.get("adresse", "") if projet_info else ""

    c.setFont("Helvetica-Bold", 12)
    c.drawString(marge, y_cartouche, f"PlacardCAD - {nom_projet}")

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

    # =====================================================================
    #  VUE DE FACE (moitie gauche)
    # =====================================================================
    vue_w = (page_w - 3 * marge) * 0.48
    vue_h = y_sep - marge - 5
    vue_x = marge
    vue_y = marge

    # Titre
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.black)
    c.drawString(vue_x, y_sep - 12, "Vue de face")

    _dessiner_vue_face(c, rects, config["largeur"], config["hauteur"],
                       vue_x, vue_y, vue_w, vue_h - 15)

    # =====================================================================
    #  FICHE DE DEBIT + QUINCAILLERIE (moitie droite)
    # =====================================================================
    tab_x = marge + vue_w + marge
    tab_w = page_w - tab_x - marge
    y_cursor = y_sep - 12

    # --- Titre fiche ---
    c.setFont("Helvetica-Bold", 9)
    c.drawString(tab_x, y_cursor, "Fiche de debit")
    y_cursor -= 12

    # --- Tableau pieces ---
    # En-tete
    cols = [
        ("Ref.", 52),
        ("Designation", 115),
        ("Long.", 36),
        ("Larg.", 36),
        ("Ep.", 26),
        ("Qte", 22),
        ("Chant", 65),
    ]
    row_h = 10
    font_size = 6.5

    # Fond en-tete
    c.setFillColor(colors.Color(0.2, 0.2, 0.2))
    c.rect(tab_x, y_cursor - row_h, tab_w, row_h, fill=1, stroke=0)

    c.setFont("Helvetica-Bold", font_size)
    c.setFillColor(colors.white)
    cx = tab_x + 2
    for col_name, col_w in cols:
        c.drawString(cx, y_cursor - row_h + 3, col_name)
        cx += col_w
    y_cursor -= row_h

    # Lignes de donnees
    c.setFont("Helvetica", font_size)
    for i, p in enumerate(fiche.pieces):
        if y_cursor - row_h < marge + 5:
            break  # securite si trop de pieces

        # Fond alterne
        if i % 2 == 1:
            c.setFillColor(colors.Color(0.95, 0.95, 0.95))
            c.rect(tab_x, y_cursor - row_h, tab_w, row_h, fill=1, stroke=0)

        c.setFillColor(colors.black)
        cx = tab_x + 2
        row_data = [
            p.reference,
            p.nom[:28],
            f"{p.longueur:.0f}",
            f"{p.largeur:.0f}",
            f"{p.epaisseur:.0f}",
            str(p.quantite),
            p.chant_desc[:16],
        ]
        for j, (_, col_w) in enumerate(cols):
            c.drawString(cx, y_cursor - row_h + 3, row_data[j])
            cx += col_w
        y_cursor -= row_h

    # Grille
    c.setStrokeColor(colors.grey)
    c.setLineWidth(0.3)
    nb_rows = len(fiche.pieces) + 1
    table_top = y_sep - 12 - row_h
    table_bottom = table_top - len(fiche.pieces) * row_h
    # Lignes horizontales
    for r_idx in range(nb_rows + 1):
        y_line = table_top - r_idx * row_h + row_h
        c.line(tab_x, y_line, tab_x + tab_w, y_line)
    # Lignes verticales
    cx = tab_x
    for _, col_w in cols:
        c.line(cx, table_top + row_h, cx, table_bottom + row_h)
        cx += col_w
    c.line(tab_x + tab_w, table_top + row_h, tab_x + tab_w, table_bottom + row_h)

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
        c.drawString(tab_x, y_cursor, "Quincaillerie")
        y_cursor -= 12

        # En-tete
        q_cols = [("Designation", 170), ("Qte", 30), ("Description", 152)]
        c.setFillColor(colors.Color(0.2, 0.2, 0.2))
        c.rect(tab_x, y_cursor - row_h, tab_w, row_h, fill=1, stroke=0)

        c.setFont("Helvetica-Bold", font_size)
        c.setFillColor(colors.white)
        cx = tab_x + 2
        for col_name, col_w in q_cols:
            c.drawString(cx, y_cursor - row_h + 3, col_name)
            cx += col_w
        y_cursor -= row_h

        # Lignes
        c.setFont("Helvetica", font_size)
        for i, q in enumerate(fiche.quincaillerie):
            if y_cursor - row_h < marge:
                break

            if i % 2 == 1:
                c.setFillColor(colors.Color(0.95, 0.95, 0.95))
                c.rect(tab_x, y_cursor - row_h, tab_w, row_h, fill=1, stroke=0)

            c.setFillColor(colors.black)
            cx = tab_x + 2
            q_data = [q["nom"][:42], str(q["quantite"]), q["description"][:38]]
            for j, (_, col_w) in enumerate(q_cols):
                c.drawString(cx, y_cursor - row_h + 3, q_data[j])
                cx += col_w
            y_cursor -= row_h

    # --- Resume materiaux ---
    y_cursor -= 10
    if y_cursor > marge + 40:
        c.setFont("Helvetica-Bold", 8)
        c.drawString(tab_x, y_cursor, "Resume materiaux")
        y_cursor -= 10

        materiaux = {}
        for p in fiche.pieces:
            key = (p.epaisseur, p.couleur_fab, p.materiau)
            if key not in materiaux:
                materiaux[key] = {"surface": 0, "nb": 0}
            materiaux[key]["surface"] += p.longueur * p.largeur * p.quantite / 1e6
            materiaux[key]["nb"] += p.quantite

        c.setFont("Helvetica", font_size)
        for (ep, coul, mat), info in materiaux.items():
            if y_cursor < marge:
                break
            c.drawString(tab_x, y_cursor,
                         f"{mat} {ep:.0f}mm {coul}: {info['surface']:.2f}m2 ({info['nb']} pcs)")
            y_cursor -= 9

    # --- Note etiquettes ---
    y_cursor -= 6
    if y_cursor > marge + 10:
        c.setFont("Helvetica-Oblique", 6)
        c.setFillColor(colors.grey)
        c.drawString(tab_x, y_cursor,
                     "Ref. format: P{projet}/A{amenagement}/N{piece} - a reporter sur etiquettes panneaux")

    c.save()
    return filepath
