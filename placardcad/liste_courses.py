"""Liste de courses -- synthese des fournitures necessaires pour un projet.

Agrege les fiches de fabrication de tous les amenagements d'un projet
pour produire un recapitulatif complet des fournitures a acheter:
panneaux bruts, cremailleres, tasseaux, chants, quincaillerie diverse
et visserie estimee.

Fonctions principales:
    - generer_liste_courses: calcule la synthese a partir des amenagements.
    - exporter_liste_courses: genere le PDF A4 de la liste de courses.
"""

from __future__ import annotations

import re

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from .placard_builder import FicheFabrication, PieceInfo
from .optimisation_debit import pieces_depuis_fiche, ParametresDebit
from guillotine_packing import optimiser_debit


def generer_liste_courses(
    amenagements_data: list[dict],
    params_debit: ParametresDebit | None = None,
    projet_id: int = 0,
    pieces_manuelles: list | None = None,
) -> dict:
    """Agrege les fiches de fabrication de tous les amenagements et retourne une synthese.

    Collecte toutes les pieces et la quincaillerie de chaque amenagement,
    lance l'optimisation de debit pour determiner le nombre de panneaux bruts,
    puis agrege cremailleres, tasseaux, chants, quincaillerie diverse et
    estime la visserie necessaire.

    Args:
        amenagements_data: Liste de dictionnaires, chacun avec les cles:
            - fiche: FicheFabrication - fiche de fabrication de l'amenagement.
            - nom: str - nom de l'amenagement.
            - amenagement_id: int - identifiant de l'amenagement.
        params_debit: Parametres de debit ou None pour les valeurs par defaut.
        projet_id: Identifiant du projet pour les references.
        pieces_manuelles: Liste optionnelle de PieceDebit complementaires
            a inclure dans le debit.

    Returns:
        Dictionnaire de synthese avec les cles:
            - panneaux_bruts: list[dict] - {epaisseur, couleur, quantite, dim}.
            - resume_pieces: list[dict] - {epaisseur, couleur, materiau, nb_pieces, surface_m2}.
            - cremailleres: list[dict] - {type, longueur_mm, quantite}.
            - taquets: int - nombre total de taquets de cremaillere.
            - tasseaux: list[dict] - {longueur_mm, section, quantite}.
            - chants: list[dict] - {couleur, epaisseur_mm, longueur_m}.
            - quincaillerie: list[dict] - {nom, quantite, description}.
            - visserie: list[dict] - {nom, quantite, description}.
    """
    if params_debit is None:
        params_debit = ParametresDebit()

    # --- Collecter toutes les pieces et quincaillerie ---
    all_fiches: list[FicheFabrication] = []
    all_pieces_debit = []

    for am in amenagements_data:
        fiche = am["fiche"]
        all_fiches.append(fiche)
        am_pieces = pieces_depuis_fiche(
            fiche, projet_id, am.get("amenagement_id", 0)
        )
        all_pieces_debit.extend(am_pieces)

    if pieces_manuelles:
        all_pieces_debit.extend(pieces_manuelles)

    # --- 1. Panneaux bruts (via optimisation debit) ---
    panneaux_bruts = []
    if all_pieces_debit:
        plans, non_places = optimiser_debit(all_pieces_debit, params_debit)
        # Compter par (epaisseur, couleur)
        panneaux_par_type: dict[tuple, int] = {}
        for plan in plans:
            key = (plan.epaisseur, plan.couleur)
            panneaux_par_type[key] = panneaux_par_type.get(key, 0) + 1

        for (ep, couleur), qte in sorted(panneaux_par_type.items()):
            panneaux_bruts.append({
                "epaisseur": ep,
                "couleur": couleur,
                "quantite": qte,
                "dim": f"{params_debit.panneau_longueur:.0f} x {params_debit.panneau_largeur:.0f}",
            })

    # --- 2. Resume pieces par materiau ---
    resume_pieces: dict[tuple, dict] = {}
    for fiche in all_fiches:
        for p in fiche.pieces:
            key = (p.epaisseur, p.couleur_fab or "Standard", p.materiau)
            if key not in resume_pieces:
                resume_pieces[key] = {"nb": 0, "surface": 0.0}
            resume_pieces[key]["nb"] += p.quantite
            resume_pieces[key]["surface"] += p.longueur * p.largeur * p.quantite / 1e6

    resume_list = []
    for (ep, couleur, mat), info in sorted(resume_pieces.items()):
        resume_list.append({
            "epaisseur": ep,
            "couleur": couleur,
            "materiau": mat,
            "nb_pieces": info["nb"],
            "surface_m2": round(info["surface"], 2),
        })

    # --- 3. Cremailleres ---
    crem_agg: dict[tuple, dict] = {}
    taquets_total = 0
    for fiche in all_fiches:
        for q in fiche.quincaillerie:
            nom = q["nom"].lower()
            # Taquets de cremaillere = categorie a part
            if "taquet" in nom:
                taquets_total += q["quantite"]
                continue
            if "cremaillere" not in nom:
                continue
            # Extraire le type
            if "encastree" in nom:
                crem_type = "Encastree"
            elif "applique" in nom:
                crem_type = "Applique"
            else:
                crem_type = "Autre"
            # Extraire la longueur
            m = re.search(r'L=(\d+)', q["description"])
            longueur_mm = int(m.group(1)) if m else 0
            key = (crem_type, longueur_mm)
            if key not in crem_agg:
                crem_agg[key] = 0
            crem_agg[key] += q["quantite"]

    cremailleres = []
    for (ctype, longueur), qte in sorted(crem_agg.items()):
        cremailleres.append({
            "type": ctype,
            "longueur_mm": longueur,
            "quantite": qte,
        })

    # --- 4. Tasseaux ---
    tass_agg: dict[tuple, int] = {}
    for fiche in all_fiches:
        for p in fiche.pieces:
            if p.materiau and "tasseau" in p.materiau.lower():
                key = (round(p.longueur), f"{p.largeur:.0f}x{p.epaisseur:.0f}")
                tass_agg[key] = tass_agg.get(key, 0) + p.quantite

    tasseaux = []
    for (longueur, section), qte in sorted(tass_agg.items()):
        tasseaux.append({
            "longueur_mm": longueur,
            "section": section,
            "quantite": qte,
        })

    # --- 5. Chants ---
    chants_agg: dict[tuple, float] = {}
    for fiche in all_fiches:
        for p in fiche.pieces:
            if not p.chant_desc:
                continue
            m = re.search(r'(\d+)', p.chant_desc)
            if not m:
                continue
            ep_chant = int(m.group(1))
            couleur = p.couleur_fab or "Standard"
            key = (couleur, ep_chant)
            chants_agg.setdefault(key, 0.0)
            chants_agg[key] += p.longueur * p.quantite

    chants = []
    for (couleur, ep), longueur_mm in sorted(chants_agg.items()):
        chants.append({
            "couleur": couleur,
            "epaisseur_mm": ep,
            "longueur_m": round(longueur_mm / 1000, 1),
        })

    # --- 6. Quincaillerie diverse (hors cremailleres et taquets) ---
    quinc_agg: dict[str, dict] = {}
    for fiche in all_fiches:
        for q in fiche.quincaillerie:
            nom_lower = q["nom"].lower()
            if "cremaillere" in nom_lower or "taquet" in nom_lower:
                continue
            nom = q["nom"]
            if nom not in quinc_agg:
                quinc_agg[nom] = {"quantite": 0, "description": q["description"]}
            quinc_agg[nom]["quantite"] += q["quantite"]

    quincaillerie = []
    for nom, info in sorted(quinc_agg.items()):
        quincaillerie.append({
            "nom": nom,
            "quantite": info["quantite"],
            "description": info["description"],
        })

    # --- 7. Visserie estimee ---
    # Estimation: vis pour panneaux mur, separations, rayon haut
    nb_panneaux_mur = 0
    nb_separations = 0
    nb_rayons_haut = 0
    nb_tasseaux_total = 0
    nb_cremailleres_total = sum(c["quantite"] for c in cremailleres)

    for fiche in all_fiches:
        for p in fiche.pieces:
            nom_lower = p.nom.lower()
            if "panneau mur" in nom_lower:
                nb_panneaux_mur += p.quantite
            elif "separation" in nom_lower:
                nb_separations += p.quantite
            elif "rayon haut" in nom_lower and "tasseau" not in nom_lower:
                nb_rayons_haut += p.quantite
            if p.materiau and "tasseau" in p.materiau.lower():
                nb_tasseaux_total += p.quantite

    visserie = []
    # Vis 4x40 pour fixation tasseaux au mur / separations
    nb_vis_tasseau = nb_tasseaux_total * 3
    if nb_vis_tasseau > 0:
        visserie.append({
            "nom": "Vis 4x40 (fixation tasseaux)",
            "quantite": nb_vis_tasseau,
            "description": f"3 vis par tasseau ({nb_tasseaux_total} tasseaux)",
        })
    # Vis 4x30 pour fixation cremailleres
    nb_vis_crem = nb_cremailleres_total * 5
    if nb_vis_crem > 0:
        visserie.append({
            "nom": "Vis 4x30 (fixation cremailleres)",
            "quantite": nb_vis_crem,
            "description": f"5 vis par cremaillere ({nb_cremailleres_total} crems)",
        })
    # Chevilles 8mm pour fixation panneaux mur
    nb_chevilles = nb_panneaux_mur * 6
    if nb_chevilles > 0:
        visserie.append({
            "nom": "Chevilles 8mm + vis 5x50 (panneaux mur)",
            "quantite": nb_chevilles,
            "description": f"6 par panneau mur ({nb_panneaux_mur} panneaux)",
        })

    return {
        "panneaux_bruts": panneaux_bruts,
        "resume_pieces": resume_list,
        "cremailleres": cremailleres,
        "taquets": taquets_total,
        "tasseaux": tasseaux,
        "chants": chants,
        "quincaillerie": quincaillerie,
        "visserie": visserie,
    }


# =====================================================================
#  Export PDF — Liste de courses
# =====================================================================

_MARGE = 40
_COL_GAP = 15


def _titre_section(c: canvas.Canvas, x: float, y: float,
                   titre: str, w: float) -> float:
    """Dessine un titre de section avec un fond colore fonce et texte blanc.

    Args:
        c: Canvas ReportLab sur lequel dessiner.
        x: Position X du bord gauche en points PDF.
        y: Position Y du haut de la zone en points PDF.
        titre: Texte du titre de section a afficher.
        w: Largeur du bandeau de titre en points PDF.

    Returns:
        Nouvelle position Y apres le titre (en dessous), en points PDF.
    """
    h_titre = 16
    c.setFillColor(colors.HexColor("#2C3E50"))
    c.rect(x, y - h_titre, w, h_titre, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x + 5, y - h_titre + 4, titre)
    c.setFillColor(colors.black)
    return y - h_titre - 4


def _tableau(c: canvas.Canvas, x: float, y: float, w: float,
             colonnes: list[tuple[str, float]], lignes: list[list[str]],
             font_size: float = 8) -> float:
    """Dessine un tableau simple avec en-tete gris clair et lignes alternees.

    Args:
        c: Canvas ReportLab sur lequel dessiner.
        x: Position X du bord gauche du tableau en points PDF.
        y: Position Y du haut du tableau en points PDF.
        w: Largeur totale du tableau en points PDF.
        colonnes: Liste de tuples (nom_colonne, largeur_colonne) definissant
            les colonnes du tableau.
        lignes: Liste de lignes de donnees, chaque ligne etant une liste de
            chaines correspondant aux valeurs des colonnes.
        font_size: Taille de police en points.

    Returns:
        Nouvelle position Y apres le tableau (en dessous), en points PDF.
    """
    row_h = font_size + 5
    # En-tete
    c.setFillColor(colors.HexColor("#ECF0F1"))
    c.rect(x, y - row_h, w, row_h, fill=1, stroke=0)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", font_size)
    cx = x + 3
    for nom_col, col_w in colonnes:
        c.drawString(cx, y - row_h + 3, nom_col)
        cx += col_w
    y -= row_h

    # Lignes
    c.setFont("Helvetica", font_size)
    for i, ligne in enumerate(lignes):
        y -= row_h
        if i % 2 == 0:
            c.setFillColor(colors.HexColor("#F8F9FA"))
            c.rect(x, y, w, row_h, fill=1, stroke=0)
            c.setFillColor(colors.black)
        cx = x + 3
        for j, (_, col_w) in enumerate(colonnes):
            val = ligne[j] if j < len(ligne) else ""
            c.drawString(cx, y + 3, str(val)[:40])
            cx += col_w

    # Bordure tableau
    c.setStrokeColor(colors.HexColor("#BDC3C7"))
    total_h = row_h * (len(lignes) + 1)
    c.rect(x, y, w, total_h, fill=0, stroke=1)
    return y - 6


def exporter_liste_courses(
    filepath: str,
    liste: dict,
    projet_info: dict | None = None,
) -> str:
    """Exporte la liste de courses en PDF A4 portrait.

    Genere un document PDF contenant les sections: panneaux bruts a acheter,
    resume des pieces a debiter, cremailleres, tasseaux, bandes de chant,
    quincaillerie et visserie estimee. Gere automatiquement les sauts de
    page si le contenu depasse une page.

    Args:
        filepath: Chemin du fichier PDF a generer.
        liste: Dictionnaire de synthese tel que retourne par
            generer_liste_courses.
        projet_info: Dictionnaire avec les informations du projet (nom, client,
            adresse) ou None. Affiche dans le cartouche en haut de page.

    Returns:
        Chemin du fichier PDF genere (identique a filepath).
    """
    page_w, page_h = A4
    c_pdf = canvas.Canvas(filepath, pagesize=A4)

    # --- Cartouche ---
    y = page_h - _MARGE
    c_pdf.setFont("Helvetica-Bold", 14)
    c_pdf.setFillColor(colors.HexColor("#2C3E50"))
    c_pdf.drawString(_MARGE, y, "LISTE DE COURSES")
    y -= 16

    if projet_info:
        c_pdf.setFont("Helvetica", 9)
        c_pdf.setFillColor(colors.HexColor("#555555"))
        infos = []
        if projet_info.get("nom"):
            infos.append(f"Projet: {projet_info['nom']}")
        if projet_info.get("client"):
            infos.append(f"Client: {projet_info['client']}")
        if projet_info.get("adresse"):
            infos.append(f"Adresse: {projet_info['adresse']}")
        c_pdf.drawString(_MARGE, y, "  |  ".join(infos))
        y -= 6

    c_pdf.setStrokeColor(colors.HexColor("#2C3E50"))
    c_pdf.setLineWidth(1.5)
    c_pdf.line(_MARGE, y, page_w - _MARGE, y)
    y -= 12
    c_pdf.setFillColor(colors.black)

    usable_w = page_w - 2 * _MARGE

    # --- Panneaux bruts ---
    panneaux = liste.get("panneaux_bruts", [])
    if panneaux:
        y = _titre_section(c_pdf, _MARGE, y, "PANNEAUX BRUTS A ACHETER", usable_w)
        cols = [
            ("Epaisseur", 70),
            ("Couleur / Materiau", 180),
            ("Dimensions (mm)", 130),
            ("Quantite", 60),
        ]
        rows = []
        for p in panneaux:
            rows.append([
                f"{p['epaisseur']:.0f} mm",
                p["couleur"],
                p["dim"],
                str(p["quantite"]),
            ])
        # Total
        total = sum(p["quantite"] for p in panneaux)
        rows.append([
            "", "TOTAL", "",
            str(total),
        ])
        y = _tableau(c_pdf, _MARGE, y, usable_w, cols, rows)

    # --- Resume pieces ---
    resume = liste.get("resume_pieces", [])
    if resume:
        y = _titre_section(c_pdf, _MARGE, y, "RESUME PIECES A DEBITER", usable_w)
        cols = [
            ("Epaisseur", 65),
            ("Couleur", 130),
            ("Materiau", 110),
            ("Nb pieces", 55),
            ("Surface m2", 70),
        ]
        rows = []
        for r in resume:
            rows.append([
                f"{r['epaisseur']:.0f} mm",
                r["couleur"],
                r["materiau"],
                str(r["nb_pieces"]),
                f"{r['surface_m2']:.2f}",
            ])
        y = _tableau(c_pdf, _MARGE, y, usable_w, cols, rows)

    # --- Cremailleres ---
    crems = liste.get("cremailleres", [])
    if crems:
        if y < 120:
            c_pdf.showPage()
            y = page_h - _MARGE
        y = _titre_section(c_pdf, _MARGE, y, "CREMAILLERES", usable_w)
        cols = [
            ("Type", 120),
            ("Longueur", 120),
            ("Quantite", 80),
        ]
        rows = []
        total_ml = 0.0
        for cr in crems:
            rows.append([
                cr["type"],
                f"{cr['longueur_mm']} mm",
                str(cr["quantite"]),
            ])
            total_ml += cr["longueur_mm"] * cr["quantite"] / 1000
        rows.append(["", f"Total: {total_ml:.1f} m lineaires", ""])
        y = _tableau(c_pdf, _MARGE, y, usable_w, cols, rows)

    # --- Taquets de cremailleres ---
    taquets = liste.get("taquets", 0)
    if taquets > 0:
        c_pdf.setFont("Helvetica", 9)
        c_pdf.drawString(_MARGE + 5, y,
                         f"Taquets de cremaillere (equerres alu): {taquets} pieces")
        y -= 14

    # --- Tasseaux ---
    tass = liste.get("tasseaux", [])
    if tass:
        if y < 120:
            c_pdf.showPage()
            y = page_h - _MARGE
        y = _titre_section(c_pdf, _MARGE, y, "TASSEAUX", usable_w)
        cols = [
            ("Section", 120),
            ("Longueur", 120),
            ("Quantite", 80),
        ]
        rows = []
        total_ml = 0.0
        for t in tass:
            rows.append([
                t["section"],
                f"{t['longueur_mm']:.0f} mm",
                str(t["quantite"]),
            ])
            total_ml += t["longueur_mm"] * t["quantite"] / 1000
        rows.append(["", f"Total: {total_ml:.1f} m lineaires", ""])
        y = _tableau(c_pdf, _MARGE, y, usable_w, cols, rows)

    # --- Chants ---
    chants = liste.get("chants", [])
    if chants:
        if y < 120:
            c_pdf.showPage()
            y = page_h - _MARGE
        y = _titre_section(c_pdf, _MARGE, y, "BANDES DE CHANT", usable_w)
        cols = [
            ("Couleur", 160),
            ("Epaisseur", 100),
            ("Longueur (m)", 80),
        ]
        rows = []
        for ch in chants:
            rows.append([
                ch["couleur"],
                f"{ch['epaisseur_mm']} mm",
                f"{ch['longueur_m']:.1f}",
            ])
        y = _tableau(c_pdf, _MARGE, y, usable_w, cols, rows)

    # --- Quincaillerie diverse ---
    quinc = liste.get("quincaillerie", [])
    if quinc:
        if y < 120:
            c_pdf.showPage()
            y = page_h - _MARGE
        y = _titre_section(c_pdf, _MARGE, y, "QUINCAILLERIE", usable_w)
        cols = [
            ("Designation", 200),
            ("Quantite", 60),
            ("Description", 170),
        ]
        rows = [[q["nom"], str(q["quantite"]), q["description"]] for q in quinc]
        y = _tableau(c_pdf, _MARGE, y, usable_w, cols, rows)

    # --- Visserie estimee ---
    viss = liste.get("visserie", [])
    if viss:
        if y < 120:
            c_pdf.showPage()
            y = page_h - _MARGE
        y = _titre_section(c_pdf, _MARGE, y, "VISSERIE (estimation)", usable_w)
        cols = [
            ("Designation", 200),
            ("Quantite", 60),
            ("Detail", 170),
        ]
        rows = [[v["nom"], str(v["quantite"]), v["description"]] for v in viss]
        y = _tableau(c_pdf, _MARGE, y, usable_w, cols, rows)

    # Pied de page
    c_pdf.setFont("Helvetica-Oblique", 7)
    c_pdf.setFillColor(colors.HexColor("#999999"))
    c_pdf.drawString(_MARGE, 20,
                     "Liste de courses generee par PlacardCAD — quantites indicatives")

    c_pdf.save()
    return filepath
