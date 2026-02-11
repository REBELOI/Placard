"""Export PDF d'etiquettes de pieces pour PlacardCAD.

Genere des planches A4 portrait d'etiquettes a coller sur chaque piece debitee.
Format standard: 7 lignes x 2 colonnes = 14 etiquettes par page (95x37mm).

Chaque etiquette contient:
    - Reference (P{projet}/A{amenagement}/N{numero}).
    - Nom de la piece.
    - Dimensions L x l x ep.
    - Couleur / finition.
    - Chants a plaquer.
    - Sens du fil (fleche directionnelle).
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from .placard_builder import PieceInfo, FicheFabrication


# Format etiquettes : 2 colonnes x 7 lignes sur A4 portrait
ETIQ_COLS = 2
ETIQ_ROWS = 7
ETIQ_W = 95 * mm
ETIQ_H = 37 * mm
MARGE_GAUCHE = 10 * mm
MARGE_HAUT = 15 * mm


def _dessiner_etiquette(c: canvas.Canvas, x: float, y: float,
                        piece: PieceInfo, index: int):
    """Dessine une etiquette individuelle a la position donnee sur le canvas.

    L'etiquette comporte un cadre pointille et affiche la reference, le nom,
    les dimensions, la couleur, les chants, le sens du fil (fleche) et la
    quantite si superieure a 1.

    Args:
        c: Canvas ReportLab sur lequel dessiner.
        x: Position X du coin bas-gauche de l'etiquette en points PDF.
        y: Position Y du coin bas-gauche de l'etiquette en points PDF.
        piece: Informations sur la piece (reference, nom, dimensions, etc.).
        index: Numero d'ordre de l'etiquette, utilise comme reference par
            defaut si la piece n'a pas de reference attribuee.
    """
    w = ETIQ_W
    h = ETIQ_H
    pad = 3 * mm

    # Cadre pointille
    c.setStrokeColor(colors.Color(0.7, 0.7, 0.7))
    c.setLineWidth(0.3)
    c.setDash(2, 2)
    c.rect(x, y, w, h)
    c.setDash()

    # --- Reference (gros, en haut a gauche) ---
    ref = piece.reference or f"N{index:02d}"
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.black)
    c.drawString(x + pad, y + h - pad - 10, ref)

    # --- Nom de la piece ---
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x + pad, y + h - pad - 22, piece.nom[:40])

    # --- Dimensions ---
    dims = f"{piece.longueur:.0f} x {piece.largeur:.0f} x {piece.epaisseur:.0f} mm"
    c.setFont("Helvetica", 8)
    c.drawString(x + pad, y + h - pad - 33, dims)

    # --- Couleur ---
    if piece.couleur_fab:
        c.setFont("Helvetica", 7)
        c.drawString(x + pad, y + h - pad - 43, piece.couleur_fab[:30])

    # --- Chants ---
    if piece.chant_desc:
        c.setFont("Helvetica", 6.5)
        c.setFillColor(colors.Color(0.3, 0.3, 0.3))
        c.drawString(x + pad, y + pad + 12, f"Chant: {piece.chant_desc[:35]}")

    # --- Sens du fil (fleche a droite) ---
    c.setFillColor(colors.black)
    if piece.sens_fil:
        # Fleche verticale (sens du fil = longueur)
        fx = x + w - pad - 12
        fy = y + h / 2
        c.setStrokeColor(colors.black)
        c.setLineWidth(1.2)
        c.line(fx + 5, fy - 10, fx + 5, fy + 10)
        # Pointe
        c.line(fx + 5, fy + 10, fx + 1, fy + 5)
        c.line(fx + 5, fy + 10, fx + 9, fy + 5)
        c.setFont("Helvetica", 5)
        c.drawCentredString(fx + 5, fy - 16, "fil")

    # --- Quantite si > 1 ---
    if piece.quantite > 1:
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(colors.Color(0.8, 0.0, 0.0))
        c.drawRightString(x + w - pad - 20, y + h - pad - 10,
                          f"x{piece.quantite}")

    c.setFillColor(colors.black)
    c.setStrokeColor(colors.black)


def exporter_etiquettes(filepath: str, fiche: FicheFabrication,
                        projet_id: int = 0, amenagement_id: int = 0,
                        projet_info: dict | None = None):
    """Exporte les etiquettes d'un amenagement en PDF A4 portrait.

    Chaque piece genere autant d'etiquettes que sa quantite. Les etiquettes
    sont disposees en grille de 2 colonnes x 7 lignes (14 par page) et la
    pagination est geree automatiquement.

    Args:
        filepath: Chemin du fichier PDF a generer.
        fiche: Fiche de fabrication contenant les pieces a etiqueter.
        projet_id: Identifiant du projet pour les references.
        amenagement_id: Identifiant de l'amenagement pour les references.
        projet_info: Dictionnaire avec les informations du projet (nom, client)
            ou None. Affiche dans l'en-tete de chaque page.
    """
    page_w, page_h = A4  # portrait

    c = canvas.Canvas(filepath, pagesize=A4)
    c.setTitle("Etiquettes pieces - REB & ELOI")

    # Attribuer les references si pas deja fait
    for i, piece in enumerate(fiche.pieces, 1):
        if not piece.reference:
            piece.reference = f"P{projet_id}/A{amenagement_id}/N{i:02d}"

    # Construire la liste des etiquettes (une par piece * quantite)
    etiquettes = []
    for piece in fiche.pieces:
        for _ in range(piece.quantite):
            etiquettes.append(piece)

    # Generer les pages
    idx = 0
    total = len(etiquettes)

    while idx < total:
        # En-tete de page
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.Color(0.5, 0.5, 0.5))
        titre = "REB & ELOI - Etiquettes pieces"
        if projet_info:
            titre += f" | {projet_info.get('nom', '')} - {projet_info.get('client', '')}"
        c.drawString(MARGE_GAUCHE, page_h - 10 * mm, titre)
        c.setFillColor(colors.black)

        for row in range(ETIQ_ROWS):
            for col in range(ETIQ_COLS):
                if idx >= total:
                    break

                x = MARGE_GAUCHE + col * ETIQ_W
                y = page_h - MARGE_HAUT - (row + 1) * ETIQ_H

                piece = etiquettes[idx]
                _dessiner_etiquette(c, x, y, piece, idx + 1)
                idx += 1

        if idx < total:
            c.showPage()

    c.save()


def exporter_etiquettes_projet(filepath: str, amenagements_data: list,
                               projet_info: dict | None = None,
                               projet_id: int = 0):
    """Exporte les etiquettes de tout un projet en PDF A4 portrait.

    Regroupe les pieces de tous les amenagements du projet en une seule
    serie d'etiquettes paginee. Chaque piece genere autant d'etiquettes
    que sa quantite.

    Args:
        filepath: Chemin du fichier PDF a generer.
        amenagements_data: Liste de dictionnaires, chacun avec les cles:
            - fiche: FicheFabrication - fiche de fabrication de l'amenagement.
            - amenagement_id: int - identifiant de l'amenagement.
        projet_info: Dictionnaire avec les informations du projet (nom, client)
            ou None. Affiche dans l'en-tete de chaque page.
        projet_id: Identifiant du projet pour les references.
    """
    page_w, page_h = A4

    c = canvas.Canvas(filepath, pagesize=A4)
    c.setTitle("Etiquettes pieces - REB & ELOI")

    # Construire la liste complete des etiquettes
    etiquettes = []
    for am_data in amenagements_data:
        fiche = am_data["fiche"]
        am_id = am_data.get("amenagement_id", 0)
        for i, piece in enumerate(fiche.pieces, 1):
            if not piece.reference:
                piece.reference = f"P{projet_id}/A{am_id}/N{i:02d}"
            for _ in range(piece.quantite):
                etiquettes.append(piece)

    idx = 0
    total = len(etiquettes)

    while idx < total:
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.Color(0.5, 0.5, 0.5))
        titre = "REB & ELOI - Etiquettes pieces"
        if projet_info:
            titre += f" | {projet_info.get('nom', '')} - {projet_info.get('client', '')}"
        c.drawString(MARGE_GAUCHE, page_h - 10 * mm, titre)
        c.setFillColor(colors.black)

        for row in range(ETIQ_ROWS):
            for col in range(ETIQ_COLS):
                if idx >= total:
                    break

                x = MARGE_GAUCHE + col * ETIQ_W
                y = page_h - MARGE_HAUT - (row + 1) * ETIQ_H

                piece = etiquettes[idx]
                _dessiner_etiquette(c, x, y, piece, idx + 1)
                idx += 1

        if idx < total:
            c.showPage()

    c.save()
