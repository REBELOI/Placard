"""
Export PDF pour PlacardCAD.

Genere un document PDF multi-pages contenant:
- Page 1 : Vue de face filaire avec cotations
- Page 2 : Fiche de debit (nomenclature panneaux)
- Page 3 : Fiche quincaillerie
"""

import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect, Line, String, Group
from reportlab.graphics import renderPDF
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


# =========================================================================
#  VUE DE FACE (DRAWING REPORTLAB)
# =========================================================================

def _creer_vue_face(rects: list[PlacardRect], largeur_placard: float,
                    hauteur_placard: float, drawing_width: float = 700,
                    drawing_height: float = 450) -> Drawing:
    """Cree le dessin ReportLab de la vue de face."""
    d = Drawing(drawing_width, drawing_height)

    if not rects or largeur_placard <= 0 or hauteur_placard <= 0:
        d.add(String(drawing_width / 2, drawing_height / 2,
                     "Aucune geometrie", textAnchor="middle",
                     fontSize=14, fillColor=colors.gray))
        return d

    marge = 60
    mur_ep = 50
    total_w = largeur_placard + 2 * mur_ep
    total_h = hauteur_placard + 2 * mur_ep

    view_w = drawing_width - 2 * marge
    view_h = drawing_height - 2 * marge

    scale = min(view_w / total_w, view_h / total_h)
    ox = marge + (view_w - total_w * scale) / 2 + mur_ep * scale
    oy = marge + (view_h - total_h * scale) / 2 + mur_ep * scale

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

            d.add(Rect(sx, sy, sw, sh,
                       fillColor=fill_color,
                       strokeColor=stroke_color,
                       strokeWidth=0.5))

    # --- Cotations ---
    # Largeur totale (en bas)
    y_cot = oy - 20
    x_left = ox
    x_right = ox + largeur_placard * scale
    d.add(Line(x_left, y_cot, x_right, y_cot,
               strokeColor=colors.black, strokeWidth=0.5))
    d.add(Line(x_left, oy, x_left, y_cot - 5,
               strokeColor=colors.grey, strokeWidth=0.3))
    d.add(Line(x_right, oy, x_right, y_cot - 5,
               strokeColor=colors.grey, strokeWidth=0.3))
    d.add(String((x_left + x_right) / 2, y_cot - 12,
                 f"{largeur_placard:.0f} mm",
                 textAnchor="middle", fontSize=8))

    # Hauteur (a gauche)
    x_cot = ox - 20
    y_bottom = oy
    y_top = oy + hauteur_placard * scale
    d.add(Line(x_cot, y_bottom, x_cot, y_top,
               strokeColor=colors.black, strokeWidth=0.5))
    d.add(Line(ox, y_bottom, x_cot - 5, y_bottom,
               strokeColor=colors.grey, strokeWidth=0.3))
    d.add(Line(ox, y_top, x_cot - 5, y_top,
               strokeColor=colors.grey, strokeWidth=0.3))

    # Texte hauteur (vertical)
    g = Group()
    g.add(String(0, 0, f"{hauteur_placard:.0f} mm",
                 textAnchor="middle", fontSize=8))
    g.transform = (0, 1, -1, 0, x_cot - 12, (y_bottom + y_top) / 2)
    d.add(g)

    return d


# =========================================================================
#  GENERATION PDF
# =========================================================================

def exporter_pdf(filepath: str, rects: list[PlacardRect], config: dict,
                 fiche: FicheFabrication, projet_info: dict | None = None):
    """
    Exporte un PDF multi-pages.

    Args:
        filepath: chemin du fichier PDF
        rects: liste des rectangles 2D (vue de face)
        config: configuration du placard
        fiche: fiche de fabrication
        projet_info: dict optionnel avec nom, client, adresse
    """
    page_size = landscape(A4)
    doc = SimpleDocTemplate(
        filepath,
        pagesize=page_size,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    style_titre = ParagraphStyle(
        "TitrePlacard",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=6,
    )
    style_sous_titre = ParagraphStyle(
        "SousTitrePlacard",
        parent=styles["Heading2"],
        fontSize=12,
        spaceAfter=4,
    )
    style_info = ParagraphStyle(
        "InfoPlacard",
        parent=styles["Normal"],
        fontSize=9,
        spaceAfter=2,
    )

    elements = []

    # --- Cartouche ---
    nom_projet = projet_info.get("nom", "Projet") if projet_info else "Projet"
    client = projet_info.get("client", "") if projet_info else ""
    adresse = projet_info.get("adresse", "") if projet_info else ""

    elements.append(Paragraph(f"PlacardCAD - {nom_projet}", style_titre))
    if client:
        elements.append(Paragraph(f"Client : {client}", style_info))
    if adresse:
        elements.append(Paragraph(f"Adresse : {adresse}", style_info))
    elements.append(Paragraph(
        f"Date : {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  "
        f"Dimensions : {config['largeur']:.0f} x {config['hauteur']:.0f} x {config['profondeur']:.0f} mm",
        style_info
    ))
    elements.append(Spacer(1, 8))

    # =====================================================================
    #  PAGE 1 : VUE DE FACE
    # =====================================================================
    elements.append(Paragraph("Vue de face", style_sous_titre))

    drawing = _creer_vue_face(
        rects, config["largeur"], config["hauteur"],
        drawing_width=page_size[0] - 30 * mm,
        drawing_height=page_size[1] - 80 * mm,
    )
    elements.append(drawing)
    elements.append(PageBreak())

    # =====================================================================
    #  PAGE 2 : FICHE DE DEBIT
    # =====================================================================
    elements.append(Paragraph(f"PlacardCAD - {nom_projet}", style_titre))
    elements.append(Paragraph("Fiche de debit - Nomenclature panneaux", style_sous_titre))
    elements.append(Spacer(1, 6))

    # Tableau des pieces
    header = ["No", "Designation", "Long. (mm)", "Larg. (mm)", "Ep. (mm)",
              "Qte", "Chant", "Notes"]
    data = [header]
    for i, p in enumerate(fiche.pieces, 1):
        data.append([
            str(i),
            p.nom,
            f"{p.longueur:.0f}",
            f"{p.largeur:.0f}",
            f"{p.epaisseur:.0f}",
            str(p.quantite),
            p.chant_desc,
            p.notes,
        ])

    # Surface totale
    surface = sum(p.longueur * p.largeur * p.quantite / 1e6 for p in fiche.pieces)
    data.append(["", "", "", "", "", "", "", f"Surface totale : {surface:.2f} m2"])

    col_widths = [25, 160, 55, 55, 40, 30, 90, 160]
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.2, 0.2, 0.2)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 0), (5, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 12))

    # --- Resume materiaux ---
    elements.append(Paragraph("Resume materiaux", style_sous_titre))
    materiaux = {}
    for p in fiche.pieces:
        key = (p.epaisseur, p.couleur_fab, p.materiau)
        if key not in materiaux:
            materiaux[key] = {"surface": 0, "nb_pieces": 0}
        materiaux[key]["surface"] += p.longueur * p.largeur * p.quantite / 1e6
        materiaux[key]["nb_pieces"] += p.quantite

    mat_data = [["Materiau", "Epaisseur", "Couleur", "Surface (m2)", "Nb pieces"]]
    for (ep, coul, mat), info in materiaux.items():
        mat_data.append([mat, f"{ep:.0f} mm", coul,
                         f"{info['surface']:.2f}", str(info['nb_pieces'])])

    t_mat = Table(mat_data, colWidths=[150, 70, 100, 80, 70], repeatRows=1)
    t_mat.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.2, 0.2, 0.2)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_mat)

    # =====================================================================
    #  PAGE 3 : QUINCAILLERIE (si presente)
    # =====================================================================
    if fiche.quincaillerie:
        elements.append(PageBreak())
        elements.append(Paragraph(f"PlacardCAD - {nom_projet}", style_titre))
        elements.append(Paragraph("Quincaillerie", style_sous_titre))
        elements.append(Spacer(1, 6))

        q_data = [["Designation", "Quantite", "Description"]]
        for q in fiche.quincaillerie:
            q_data.append([q["nom"], str(q["quantite"]), q["description"]])

        t_q = Table(q_data, colWidths=[200, 60, 350], repeatRows=1)
        t_q.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.2, 0.2, 0.2)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(t_q)

    # --- Build PDF ---
    doc.build(elements)
    return filepath
