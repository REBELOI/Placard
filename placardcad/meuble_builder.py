"""Constructeur 2D de meubles parametriques.

Genere la geometrie 2D (vue de face) et la fiche de fabrication
pour un meuble defini par un schema compact et des parametres.

Le meuble est compose de:
    - Flancs (cotes gauche et droit)
    - Dessus / dessous
    - Fond (rainure, vissage ou applique)
    - Separations verticales
    - Etageres sur cremailleres
    - Facades: portes (charnieres CLIP top) et tiroirs (LEGRABOX)
    - Pieds et plinthes
"""

from __future__ import annotations

from .placard_builder import Rect, PieceInfo, FicheFabrication


# =====================================================================
#  Constantes LEGRABOX (Blum)
# =====================================================================

LEGRABOX_HAUTEURS = {
    "M": 90.5,
    "K": 128.5,
    "C": 193.0,
    "F": 257.0,
}

LEGRABOX_JEU_LATERAL = 12.75  # mm par cote
LEGRABOX_EP_PAROI = 12.5      # mm epaisseur paroi laterale
LEGRABOX_EP_FOND = 8.0        # mm epaisseur fond tiroir

LEGRABOX_LONGUEURS_COULISSES = [
    270, 300, 350, 400, 450, 500, 550, 600, 650,
]

# =====================================================================
#  Constantes charnieres CLIP top (Blum)
# =====================================================================

CLIP_TOP_DIAMETRE_CUVETTE = 35.0
CLIP_TOP_PROFONDEUR_CUVETTE = 13.0
CLIP_TOP_DISTANCE_BORD = 3.0

RECOUVREMENT = {
    "applique": 16.0,
    "semi_applique": 8.0,
    "encloisonnee": 0.0,
}


def _rgb_to_hex(rgb: list | tuple) -> str:
    """Convertit un triplet RGB (0-1) en couleur hexadecimale."""
    r, g, b = rgb
    return f"#{int(r*255):02X}{int(g*255):02X}{int(b*255):02X}"


def _nb_charnieres(hauteur_porte: float) -> int:
    """Calcule le nombre de charnieres selon la hauteur de la porte.

    Args:
        hauteur_porte: Hauteur de la porte en mm.

    Returns:
        Nombre de charnieres (2 a 5).
    """
    if hauteur_porte <= 1000:
        return 2
    elif hauteur_porte <= 1500:
        return 3
    elif hauteur_porte <= 2000:
        return 4
    return 5


def _longueur_coulisse(profondeur_caisson: float,
                       ep_facade: float) -> int:
    """Selectionne la longueur de coulisse LEGRABOX standard.

    Args:
        profondeur_caisson: Profondeur interieure du caisson en mm.
        ep_facade: Epaisseur de la facade en mm.

    Returns:
        Longueur de coulisse standard la plus proche (mm).
    """
    profondeur_utile = profondeur_caisson - ep_facade - 2
    best = LEGRABOX_LONGUEURS_COULISSES[0]
    for lg in LEGRABOX_LONGUEURS_COULISSES:
        if lg <= profondeur_utile:
            best = lg
        else:
            break
    return best


def calculer_largeurs_meuble(config: dict) -> list[float]:
    """Calcule les largeurs de chaque compartiment en mm.

    Args:
        config: Configuration complete du meuble.

    Returns:
        Liste des largeurs interieures par compartiment.
    """
    L = config["largeur"]
    ep = config["epaisseur"]
    nb = config["nombre_compartiments"]
    ep_sep = config["separation"]["epaisseur"]

    # Largeur interieure totale
    larg_int = L - 2 * ep
    # Retirer les separations
    nb_sep = nb - 1
    larg_dispo = larg_int - nb_sep * ep_sep

    mode = config["mode_largeur"]
    largeurs_spec = config.get("largeurs_compartiments", [])

    if mode == "dimensions" and largeurs_spec:
        total_spec = sum(v for v in largeurs_spec if v is not None)
        if total_spec > 0:
            ratio = larg_dispo / total_spec
            return [v * ratio for v in largeurs_spec]

    if mode == "mixte" and largeurs_spec:
        fixees = [(i, v) for i, v in enumerate(largeurs_spec) if v is not None]
        total_fixe = sum(v for _, v in fixees)
        nb_auto = nb - len(fixees)
        reste = max(0, larg_dispo - total_fixe)
        larg_auto = reste / nb_auto if nb_auto > 0 else 0
        result = []
        for i in range(nb):
            val = next((v for idx, v in fixees if idx == i), None)
            result.append(val if val is not None else larg_auto)
        return result

    # Mode egal
    return [larg_dispo / nb] * nb


def generer_geometrie_meuble(config: dict) -> tuple[list[Rect], FicheFabrication]:
    """Genere la geometrie 2D (vue de face) et la fiche de fabrication d'un meuble.

    Args:
        config: Configuration complete issue de ``meuble_schema_vers_config``.

    Returns:
        Tuple (rectangles, fiche_fabrication) ou rectangles est la liste
        des ``Rect`` pour le dessin 2D et fiche_fabrication la nomenclature.
    """
    rects: list[Rect] = []
    fiche = FicheFabrication()

    L = config["largeur"]
    H = config["hauteur"]
    P = config["profondeur"]
    ep = config["epaisseur"]
    ep_f = config["epaisseur_facade"]
    h_plinthe = config["hauteur_plinthe"]
    assemblage = config["assemblage"]
    pose = config["pose"]
    nb_comp = config["nombre_compartiments"]
    ep_sep = config["separation"]["epaisseur"]

    couleur_struct = _rgb_to_hex(config["panneau"]["couleur_rgb"])
    couleur_facade = _rgb_to_hex(config["facade"]["couleur_rgb"])
    couleur_plinthe = "#404040"
    couleur_etagere = _rgb_to_hex(config["panneau"]["couleur_rgb"])
    couleur_fond = "#D4C5A9"

    h_corps = H - h_plinthe

    # Dimensions dessus/dessous selon assemblage
    if assemblage == "dessus_sur":
        flanc_h = h_corps - 2 * ep
        flanc_z = h_plinthe + ep
        dessus_x, dessus_w = 0, L
        dessous_x, dessous_w = 0, L
    else:  # dessus_entre
        flanc_h = h_corps
        flanc_z = h_plinthe
        dessus_x, dessus_w = ep, L - 2 * ep
        dessous_x, dessous_w = ep, L - 2 * ep

    larg_int = L - 2 * ep

    # Recouvrement facade
    rec = RECOUVREMENT.get(pose, 16.0)
    jeu_p = config["porte"]

    # =====================================================================
    #  STRUCTURE
    # =====================================================================

    # --- Plinthe ---
    plinthe_cfg = config["plinthe"]
    if plinthe_cfg["type"] != "aucune":
        retrait_p = plinthe_cfg["retrait"]
        rects.append(Rect(
            retrait_p, 0, L - 2 * retrait_p, h_plinthe,
            couleur_plinthe, "Plinthe avant", "plinthe"
        ))
        fiche.ajouter_piece(PieceInfo(
            "Plinthe avant",
            L - 2 * retrait_p, h_plinthe, plinthe_cfg["epaisseur"],
            couleur_fab=config["panneau"]["couleur_fab"],
        ))
        if plinthe_cfg["type"] == "trois_cotes":
            for cote, nom in [("gauche", "Plinthe gauche"),
                              ("droite", "Plinthe droite")]:
                fiche.ajouter_piece(PieceInfo(
                    nom, P - retrait_p, h_plinthe, plinthe_cfg["epaisseur"],
                    couleur_fab=config["panneau"]["couleur_fab"],
                ))

    # Pieds (quincaillerie)
    nb_pieds_l = 2 if L < 800 else 3
    nb_pieds_p = 2
    fiche.ajouter_quincaillerie(
        "Pieds reglables", nb_pieds_l * nb_pieds_p,
        f"Grille {nb_pieds_p}x{nb_pieds_l}, h={h_plinthe}mm"
    )

    # --- Flancs ---
    rects.append(Rect(0, flanc_z, ep, flanc_h,
                       couleur_struct, "Cote gauche", "flanc"))
    rects.append(Rect(L - ep, flanc_z, ep, flanc_h,
                       couleur_struct, "Cote droit", "flanc"))
    for nom in ["Cote gauche", "Cote droit"]:
        fiche.ajouter_piece(PieceInfo(
            nom, P, flanc_h, ep,
            couleur_fab=config["panneau"]["couleur_fab"],
            chant_desc=f"Avant {config['panneau']['chant_epaisseur']}mm",
        ))

    # --- Dessus ---
    rects.append(Rect(dessus_x, h_plinthe + h_corps - ep, dessus_w, ep,
                       couleur_struct, "Dessus", "dessus"))
    fiche.ajouter_piece(PieceInfo(
        "Dessus", dessus_w, P, ep,
        couleur_fab=config["panneau"]["couleur_fab"],
        chant_desc=f"Avant {config['panneau']['chant_epaisseur']}mm",
    ))

    # --- Dessous ---
    rects.append(Rect(dessous_x, h_plinthe, dessous_w, ep,
                       couleur_struct, "Dessous", "dessous"))
    fiche.ajouter_piece(PieceInfo(
        "Dessous", dessous_w, P, ep,
        couleur_fab=config["panneau"]["couleur_fab"],
        chant_desc=f"Avant {config['panneau']['chant_epaisseur']}mm",
    ))

    # --- Fond ---
    fond_cfg = config["fond"]
    fond_type = fond_cfg["type"]
    if fond_type == "rainure":
        fond_l = L - 2 * ep + 2 * fond_cfg["profondeur_rainure"]
        fond_h = h_corps - 2 * ep + 2 * fond_cfg["profondeur_rainure"]
    elif fond_type == "applique":
        fond_l = L
        fond_h = h_corps
    else:  # vissage
        fond_l = larg_int
        fond_h = h_corps - 2 * ep

    fiche.ajouter_piece(PieceInfo(
        "Fond", fond_l, fond_h, fond_cfg["epaisseur"],
        materiau="Panneau fond",
        couleur_fab=config["panneau"]["couleur_fab"],
        notes=f"Assemblage {fond_type}",
    ))

    # =====================================================================
    #  SEPARATIONS
    # =====================================================================

    largeurs = calculer_largeurs_meuble(config)
    x_cursor = ep  # Position X courante (apres flanc gauche)

    compartiments_geom: list[dict] = []
    for comp_idx in range(nb_comp):
        larg_c = largeurs[comp_idx]
        compartiments_geom.append({
            "x": x_cursor,
            "largeur": larg_c,
        })

        if comp_idx < nb_comp - 1:
            x_sep = x_cursor + larg_c
            z_sep = h_plinthe + ep  # sous dessus, sur dessous
            h_sep = h_corps - 2 * ep

            rects.append(Rect(x_sep, z_sep, ep_sep, h_sep,
                               couleur_struct,
                               f"Separation {comp_idx + 1}", "separation"))
            fiche.ajouter_piece(PieceInfo(
                f"Separation {comp_idx + 1}",
                P - config["separation"]["retrait_avant"]
                  - config["separation"]["retrait_arriere"],
                h_sep, ep_sep,
                couleur_fab=config["panneau"]["couleur_fab"],
                chant_desc=f"Avant {config['panneau']['chant_epaisseur']}mm",
            ))
            x_cursor = x_sep + ep_sep
        else:
            x_cursor += larg_c

    # =====================================================================
    #  ETAGERES & CREMAILLERES par compartiment
    # =====================================================================

    for comp_idx in range(nb_comp):
        cg = compartiments_geom[comp_idx]
        comp_data = config["compartiments"][comp_idx]
        nb_etag = comp_data["etageres"]

        if nb_etag > 0:
            z_bas_etag = h_plinthe + ep
            z_haut_etag = h_plinthe + h_corps - ep
            h_zone = z_haut_etag - z_bas_etag
            espacement = h_zone / (nb_etag + 1)
            jeu_lat = config["etagere"]["jeu_lateral"]
            larg_etag = cg["largeur"] - 2 * jeu_lat

            for e_idx in range(nb_etag):
                z_e = z_bas_etag + espacement * (e_idx + 1)
                rects.append(Rect(
                    cg["x"] + jeu_lat, z_e,
                    larg_etag, ep,
                    couleur_etagere,
                    f"Etagere C{comp_idx+1} E{e_idx+1}", "etagere"
                ))

            prof_etag = (P - config["etagere"]["retrait_avant"]
                         - config["fond"]["distance_chant"]
                         - config["fond"]["epaisseur"])
            fiche.ajouter_piece(PieceInfo(
                f"Etagere compartiment {comp_idx+1}",
                larg_etag, prof_etag, ep,
                couleur_fab=config["panneau"]["couleur_fab"],
                chant_desc=f"Avant {config['panneau']['chant_epaisseur']}mm",
                quantite=nb_etag,
            ))

            # Taquets etagere
            fiche.ajouter_quincaillerie(
                f"Taquets etagere (C{comp_idx+1})",
                4 * nb_etag,
                f"4 par etagere x {nb_etag}",
            )

            # Cremailleres (2 par cote du compartiment)
            crem_cfg = config["cremaillere"]
            h_crem = h_corps - 2 * ep
            fiche.ajouter_quincaillerie(
                f"Cremaillere alu (C{comp_idx+1})",
                4, f"L={h_crem:.0f}mm, larg={crem_cfg['largeur']}mm"
            )

    # =====================================================================
    #  FACADES
    # =====================================================================

    for comp_idx in range(nb_comp):
        cg = compartiments_geom[comp_idx]
        comp_data = config["compartiments"][comp_idx]
        facade = comp_data["facade"]
        facade_type = facade["type"]

        # Zone facade disponible
        z_facade_bas = h_plinthe + jeu_p["jeu_bas"]
        z_facade_haut = H - jeu_p["jeu_haut"]
        h_facade_zone = z_facade_haut - z_facade_bas

        if pose == "encloisonnee":
            z_facade_bas = h_plinthe + ep + jeu_p["jeu_bas"]
            z_facade_haut = h_plinthe + h_corps - ep - jeu_p["jeu_haut"]
            h_facade_zone = z_facade_haut - z_facade_bas

        # Position X de la facade
        if pose == "encloisonnee":
            x_facade = cg["x"] + jeu_p["jeu_lateral"]
            w_facade = cg["largeur"] - 2 * jeu_p["jeu_lateral"]
        else:
            # Applique / semi-applique: deborde sur les flancs/separations
            x_facade = cg["x"] - rec + jeu_p["jeu_lateral"]
            w_facade = cg["largeur"] + 2 * rec - 2 * jeu_p["jeu_lateral"]
            # Ajuster si bord exterieur (flanc)
            if comp_idx == 0:
                x_facade = -rec + ep + jeu_p["jeu_lateral"]
            if comp_idx == nb_comp - 1:
                w_facade = (cg["x"] + cg["largeur"] + rec
                            - jeu_p["jeu_lateral"]) - x_facade

        # --- Portes ---
        if facade_type == "portes":
            nb_portes = facade["nb_portes"]
            if nb_portes == 1:
                rects.append(Rect(
                    x_facade, z_facade_bas, w_facade, h_facade_zone,
                    couleur_facade,
                    f"Porte C{comp_idx+1}", "porte"
                ))
                fiche.ajouter_piece(PieceInfo(
                    f"Porte C{comp_idx+1}",
                    w_facade, h_facade_zone, ep_f,
                    couleur_fab=config["facade"]["couleur_fab"],
                    chant_desc="4 chants",
                ))
                nb_ch = _nb_charnieres(h_facade_zone)
                fiche.ajouter_quincaillerie(
                    f"Charnieres CLIP top (C{comp_idx+1})",
                    nb_ch, f"Porte {h_facade_zone:.0f}mm"
                )
            elif nb_portes >= 2:
                jeu_e = jeu_p["jeu_entre"]
                w_porte = (w_facade - jeu_e) / 2
                # Porte gauche
                rects.append(Rect(
                    x_facade, z_facade_bas, w_porte, h_facade_zone,
                    couleur_facade,
                    f"Porte G C{comp_idx+1}", "porte"
                ))
                # Porte droite
                rects.append(Rect(
                    x_facade + w_porte + jeu_e, z_facade_bas,
                    w_porte, h_facade_zone,
                    couleur_facade,
                    f"Porte D C{comp_idx+1}", "porte"
                ))
                fiche.ajouter_piece(PieceInfo(
                    f"Porte C{comp_idx+1}",
                    w_porte, h_facade_zone, ep_f,
                    couleur_fab=config["facade"]["couleur_fab"],
                    chant_desc="4 chants",
                    quantite=2,
                ))
                nb_ch = _nb_charnieres(h_facade_zone)
                fiche.ajouter_quincaillerie(
                    f"Charnieres CLIP top (C{comp_idx+1})",
                    nb_ch * 2, f"2 portes x {nb_ch} charnieres"
                )

        # --- Tiroirs ---
        elif facade_type == "tiroirs":
            nb_tiroirs = facade["nb_tiroirs"]
            hauteur_legrabox = config["tiroir"]["hauteur"]
            jeu_entre_t = config["tiroir"]["jeu_entre"]
            jeu_lat_t = config["tiroir"]["jeu_lateral"]

            h_facade_tiroir = ((h_facade_zone - (nb_tiroirs - 1)
                                * jeu_entre_t) / nb_tiroirs)

            for t_idx in range(nb_tiroirs):
                z_t = z_facade_bas + t_idx * (h_facade_tiroir + jeu_entre_t)
                rects.append(Rect(
                    x_facade, z_t, w_facade, h_facade_tiroir,
                    couleur_facade,
                    f"Tiroir C{comp_idx+1} T{t_idx+1}", "tiroir"
                ))

            # Facade tiroir
            fiche.ajouter_piece(PieceInfo(
                f"Facade tiroir C{comp_idx+1}",
                w_facade, h_facade_tiroir, ep_f,
                couleur_fab=config["facade"]["couleur_fab"],
                chant_desc="4 chants",
                quantite=nb_tiroirs,
            ))

            # Fond tiroir
            larg_tiroir = cg["largeur"] - 2 * LEGRABOX_JEU_LATERAL
            lg_coulisse = _longueur_coulisse(P, ep_f)
            h_cote = LEGRABOX_HAUTEURS.get(hauteur_legrabox, 90.5)

            fiche.ajouter_piece(PieceInfo(
                f"Fond tiroir C{comp_idx+1}",
                larg_tiroir, lg_coulisse - 2 * LEGRABOX_EP_PAROI,
                LEGRABOX_EP_FOND,
                materiau="Panneau fond",
                couleur_fab=config["panneau"]["couleur_fab"],
                quantite=nb_tiroirs,
            ))

            # Arriere tiroir
            fiche.ajouter_piece(PieceInfo(
                f"Arriere tiroir C{comp_idx+1}",
                larg_tiroir - 2 * LEGRABOX_EP_PAROI,
                h_cote - LEGRABOX_EP_FOND,
                LEGRABOX_EP_PAROI,
                materiau="Panneau fond",
                couleur_fab=config["panneau"]["couleur_fab"],
                quantite=nb_tiroirs,
            ))

            # Coulisses LEGRABOX
            fiche.ajouter_quincaillerie(
                f"Coulisse LEGRABOX (C{comp_idx+1})",
                nb_tiroirs * 2,
                f"Paire, L={lg_coulisse}mm, hauteur {hauteur_legrabox}"
            )

        # --- Mixte (tiroirs + porte) ---
        elif facade_type == "mixte":
            nb_tiroirs = facade["nb_tiroirs"]
            nb_portes = facade["nb_portes"]
            hauteur_legrabox = config["tiroir"]["hauteur"]
            h_cote = LEGRABOX_HAUTEURS.get(hauteur_legrabox, 90.5)
            jeu_entre_t = config["tiroir"]["jeu_entre"]

            # Les tiroirs sont en haut, la porte en bas
            h_tiroir_facade = h_cote + 2 * jeu_p["jeu_haut"]
            h_zone_tiroirs = nb_tiroirs * h_tiroir_facade + (nb_tiroirs - 1) * jeu_entre_t
            h_zone_porte = h_facade_zone - h_zone_tiroirs - jeu_p["jeu_entre"]

            # Tiroirs (en haut)
            for t_idx in range(nb_tiroirs):
                z_t = z_facade_haut - h_zone_tiroirs + t_idx * (h_tiroir_facade + jeu_entre_t)
                rects.append(Rect(
                    x_facade, z_t, w_facade, h_tiroir_facade,
                    couleur_facade,
                    f"Tiroir C{comp_idx+1} T{t_idx+1}", "tiroir"
                ))

            fiche.ajouter_piece(PieceInfo(
                f"Facade tiroir C{comp_idx+1}",
                w_facade, h_tiroir_facade, ep_f,
                couleur_fab=config["facade"]["couleur_fab"],
                chant_desc="4 chants",
                quantite=nb_tiroirs,
            ))

            larg_tiroir = cg["largeur"] - 2 * LEGRABOX_JEU_LATERAL
            lg_coulisse = _longueur_coulisse(P, ep_f)

            fiche.ajouter_piece(PieceInfo(
                f"Fond tiroir C{comp_idx+1}",
                larg_tiroir, lg_coulisse - 2 * LEGRABOX_EP_PAROI,
                LEGRABOX_EP_FOND,
                materiau="Panneau fond",
                couleur_fab=config["panneau"]["couleur_fab"],
                quantite=nb_tiroirs,
            ))
            fiche.ajouter_piece(PieceInfo(
                f"Arriere tiroir C{comp_idx+1}",
                larg_tiroir - 2 * LEGRABOX_EP_PAROI,
                h_cote - LEGRABOX_EP_FOND,
                LEGRABOX_EP_PAROI,
                materiau="Panneau fond",
                couleur_fab=config["panneau"]["couleur_fab"],
                quantite=nb_tiroirs,
            ))
            fiche.ajouter_quincaillerie(
                f"Coulisse LEGRABOX (C{comp_idx+1})",
                nb_tiroirs * 2,
                f"Paire, L={lg_coulisse}mm, hauteur {hauteur_legrabox}"
            )

            # Porte (en bas)
            if h_zone_porte > 0:
                rects.append(Rect(
                    x_facade, z_facade_bas, w_facade, h_zone_porte,
                    couleur_facade,
                    f"Porte C{comp_idx+1}", "porte"
                ))
                fiche.ajouter_piece(PieceInfo(
                    f"Porte C{comp_idx+1}",
                    w_facade, h_zone_porte, ep_f,
                    couleur_fab=config["facade"]["couleur_fab"],
                    chant_desc="4 chants",
                ))
                nb_ch = _nb_charnieres(h_zone_porte)
                fiche.ajouter_quincaillerie(
                    f"Charnieres CLIP top (C{comp_idx+1})",
                    nb_ch, f"Porte {h_zone_porte:.0f}mm"
                )

        # --- Niche (pas de facade) ---
        # Rien a dessiner

    # =====================================================================
    #  COTATIONS (lignes de cote)
    # =====================================================================

    # Cotation largeur totale
    rects.append(Rect(0, -30, L, 2, "#333333", f"{L:.0f}", "cotation"))
    # Cotation hauteur totale
    rects.append(Rect(-30, 0, 2, H, "#333333", f"{H:.0f}", "cotation"))
    # Cotation hauteur plinthe
    if h_plinthe > 0:
        rects.append(Rect(-20, 0, 1, h_plinthe, "#666666",
                          f"{h_plinthe:.0f}", "cotation"))

    # Cotation largeurs compartiments
    x_cot = ep
    for comp_idx, larg_c in enumerate(largeurs):
        rects.append(Rect(x_cot, -20, larg_c, 1, "#666666",
                          f"{larg_c:.0f}", "cotation"))
        x_cot += larg_c
        if comp_idx < nb_comp - 1:
            x_cot += ep_sep

    # Visserie estimee
    nb_separations = nb_comp - 1
    fiche.ajouter_quincaillerie(
        "Vis de montage structure", (4 + nb_separations) * 8,
        f"Tourillons + vis confirmation, {4 + nb_separations} panneaux"
    )

    return rects, fiche


def generer_vue_dessus_meuble(config: dict) -> list[Rect]:
    """Genere la geometrie 2D vue de dessus (plan XY) d'un meuble.

    Projection horizontale montrant la largeur (X) et la profondeur (Y).
    Y=0 correspond a la face avant, Y=P au fond.

    Args:
        config: Configuration complete issue de ``meuble_schema_vers_config``.

    Returns:
        Liste de ``Rect`` pour le dessin 2D en vue de dessus.
    """
    rects: list[Rect] = []

    L = config["largeur"]
    P = config["profondeur"]
    ep = config["epaisseur"]
    ep_f = config["epaisseur_facade"]
    assemblage = config["assemblage"]
    nb_comp = config["nombre_compartiments"]
    ep_sep = config["separation"]["epaisseur"]

    couleur_struct = _rgb_to_hex(config["panneau"]["couleur_rgb"])
    couleur_facade = _rgb_to_hex(config["facade"]["couleur_rgb"])
    couleur_fond = "#D4C5A9"
    couleur_etagere = _rgb_to_hex(config["panneau"]["couleur_rgb"])

    # --- Flancs (vus de dessus : ep x P) ---
    rects.append(Rect(0, 0, ep, P, couleur_struct, "Cote gauche", "flanc"))
    rects.append(Rect(L - ep, 0, ep, P, couleur_struct, "Cote droit", "flanc"))

    # --- Dessus (couvre toute la largeur, profondeur P) ---
    if assemblage == "dessus_sur":
        dessus_x, dessus_w = 0, L
    else:
        dessus_x, dessus_w = ep, L - 2 * ep
    rects.append(Rect(dessus_x, 0, dessus_w, P,
                       couleur_struct, "Dessus", "dessus"))

    # --- Fond ---
    fond_cfg = config["fond"]
    ep_fond = fond_cfg["epaisseur"]
    if fond_cfg["type"] == "rainure":
        fond_y = P - fond_cfg["distance_chant"] - ep_fond
        prof_r = fond_cfg["profondeur_rainure"]
        # Le fond rentre dans les rainures des flancs, dessus et dessous
        fond_x = ep - prof_r
        fond_w = L - 2 * ep + 2 * prof_r
    elif fond_cfg["type"] == "applique":
        fond_y = P - ep_fond
        fond_x = 0
        fond_w = L
    else:  # vissage
        fond_y = P - ep_fond
        fond_x = ep
        fond_w = L - 2 * ep

    rects.append(Rect(fond_x, fond_y, fond_w, ep_fond,
                       couleur_fond, "Fond", "fond"))

    # --- Separations ---
    largeurs = calculer_largeurs_meuble(config)
    x_cursor = ep

    compartiments_geom: list[dict] = []
    for comp_idx in range(nb_comp):
        larg_c = largeurs[comp_idx]
        compartiments_geom.append({"x": x_cursor, "largeur": larg_c})

        if comp_idx < nb_comp - 1:
            x_sep = x_cursor + larg_c
            # Separation de la face avant (Y=0) jusqu'au fond
            rects.append(Rect(x_sep, 0, ep_sep, fond_y,
                               couleur_struct,
                               f"Separation {comp_idx + 1}", "separation"))
            x_cursor = x_sep + ep_sep
        else:
            x_cursor += larg_c

    # --- Rainures ---
    couleur_rainure = "#6B5B3A"
    crem_cfg = config["cremaillere"]
    crem_prof = crem_cfg.get("profondeur", 7)
    crem_larg = crem_cfg["largeur"]

    # Positions Y des cremailleres (entre face avant et fond)
    y_crem_av = crem_cfg["distance_avant"]
    y_crem_ar = fond_y - crem_cfg["distance_arriere"] - crem_larg

    # Determiner quels compartiments ont des etageres
    comp_has_etag = [config["compartiments"][i]["etageres"] > 0
                     for i in range(nb_comp)]

    # --- Rainures fond (si type rainure) dans flancs, dessus et dessous ---
    if fond_cfg["type"] == "rainure":
        prof_r = fond_cfg["profondeur_rainure"]
        # Flanc gauche
        rects.append(Rect(ep - prof_r, fond_y, prof_r, ep_fond,
                           couleur_rainure, "Rainure fond G", "rainure"))
        # Flanc droit
        rects.append(Rect(L - ep, fond_y, prof_r, ep_fond,
                           couleur_rainure, "Rainure fond D", "rainure"))
        # Dessus (bande horizontale a fond_y)
        rects.append(Rect(dessus_x, fond_y, dessus_w, ep_fond,
                           couleur_rainure, "Rainure fond dessus", "rainure"))
        # Dessous (bande horizontale a fond_y)
        rects.append(Rect(dessus_x, fond_y, dessus_w, ep_fond,
                           couleur_rainure, "Rainure fond dessous", "rainure"))

    # --- Rainures cremailleres dans les flancs (seulement si etageres) ---
    # Flanc gauche : si le compartiment 0 a des etageres
    if comp_has_etag[0]:
        rects.append(Rect(ep - crem_prof, y_crem_av, crem_prof, crem_larg,
                           couleur_rainure, "Rainure crem av G", "rainure"))
        rects.append(Rect(ep - crem_prof, y_crem_ar, crem_prof, crem_larg,
                           couleur_rainure, "Rainure crem ar G", "rainure"))

    # Flanc droit : si le dernier compartiment a des etageres
    if comp_has_etag[-1]:
        rects.append(Rect(L - ep, y_crem_av, crem_prof, crem_larg,
                           couleur_rainure, "Rainure crem av D", "rainure"))
        rects.append(Rect(L - ep, y_crem_ar, crem_prof, crem_larg,
                           couleur_rainure, "Rainure crem ar D", "rainure"))

    # --- Rainures cremailleres dans les separations (selon compartiments adjacents) ---
    x_cursor_sep = ep
    for comp_idx in range(nb_comp):
        larg_c = largeurs[comp_idx]
        if comp_idx < nb_comp - 1:
            x_sep = x_cursor_sep + larg_c
            # Face gauche de la separation : si le compartiment gauche a des etageres
            if comp_has_etag[comp_idx]:
                rects.append(Rect(x_sep, y_crem_av, crem_prof, crem_larg,
                                   couleur_rainure,
                                   f"Rainure crem av Sep{comp_idx+1} G", "rainure"))
                rects.append(Rect(x_sep, y_crem_ar, crem_prof, crem_larg,
                                   couleur_rainure,
                                   f"Rainure crem ar Sep{comp_idx+1} G", "rainure"))
            # Face droite de la separation : si le compartiment droit a des etageres
            if comp_has_etag[comp_idx + 1]:
                rects.append(Rect(x_sep + ep_sep - crem_prof, y_crem_av,
                                   crem_prof, crem_larg, couleur_rainure,
                                   f"Rainure crem av Sep{comp_idx+1} D", "rainure"))
                rects.append(Rect(x_sep + ep_sep - crem_prof, y_crem_ar,
                                   crem_prof, crem_larg, couleur_rainure,
                                   f"Rainure crem ar Sep{comp_idx+1} D", "rainure"))
            x_cursor_sep = x_sep + ep_sep
        else:
            x_cursor_sep += larg_c

    # --- Etageres (empreinte en plan, une par compartiment) ---
    for comp_idx in range(nb_comp):
        cg = compartiments_geom[comp_idx]
        comp_data = config["compartiments"][comp_idx]
        nb_etag = comp_data["etageres"]

        if nb_etag > 0:
            jeu_lat = config["etagere"]["jeu_lateral"]
            larg_etag = cg["largeur"] - 2 * jeu_lat
            retrait_av = config["etagere"]["retrait_avant"]
            prof_etag = (P - retrait_av
                         - fond_cfg["distance_chant"] - ep_fond)
            # Retrait a l'avant : l'etagere commence apres le retrait
            rects.append(Rect(
                cg["x"] + jeu_lat, retrait_av,
                larg_etag, prof_etag,
                couleur_etagere,
                f"Etagere C{comp_idx+1} (x{nb_etag})", "etagere"
            ))

    # --- Facades (en avant du caisson, y negatif) ---
    pose = config["pose"]
    rec = RECOUVREMENT.get(pose, 16.0)
    jeu_p = config["porte"]

    for comp_idx in range(nb_comp):
        cg = compartiments_geom[comp_idx]
        comp_data = config["compartiments"][comp_idx]
        facade = comp_data["facade"]
        facade_type = facade["type"]

        if facade_type == "niche":
            continue

        # Position X de la facade (meme logique que vue de face)
        if pose == "encloisonnee":
            x_facade = cg["x"] + jeu_p["jeu_lateral"]
            w_facade = cg["largeur"] - 2 * jeu_p["jeu_lateral"]
        else:
            x_facade = cg["x"] - rec + jeu_p["jeu_lateral"]
            w_facade = cg["largeur"] + 2 * rec - 2 * jeu_p["jeu_lateral"]
            if comp_idx == 0:
                x_facade = -rec + ep + jeu_p["jeu_lateral"]
            if comp_idx == nb_comp - 1:
                w_facade = (cg["x"] + cg["largeur"] + rec
                            - jeu_p["jeu_lateral"]) - x_facade

        # Facade positionnee devant le caisson
        label_type = {"portes": "Porte", "tiroirs": "Tiroir",
                      "mixte": "Facade"}.get(facade_type, "Facade")
        rects.append(Rect(
            x_facade, -ep_f, w_facade, ep_f,
            couleur_facade,
            f"{label_type} C{comp_idx+1}", facade_type.rstrip("s")
            if facade_type != "mixte" else "porte"
        ))

    # --- Cotations ---
    rects.append(Rect(0, -50, L, 2, "#333333", f"{L:.0f}", "cotation"))
    rects.append(Rect(-30, 0, 2, P, "#333333", f"{P:.0f}", "cotation"))

    return rects


def generer_vue_cote_meuble(config: dict) -> list[Rect]:
    """Genere la geometrie 2D vue de cote en coupe (plan YZ) d'un meuble.

    Coupe longitudinale montrant la profondeur (X) et la hauteur (Y).
    X=0 correspond a la face avant, X=P au fond.

    Args:
        config: Configuration complete issue de ``meuble_schema_vers_config``.

    Returns:
        Liste de ``Rect`` pour le dessin 2D en vue de cote (coupe).
    """
    rects: list[Rect] = []

    H = config["hauteur"]
    P = config["profondeur"]
    ep = config["epaisseur"]
    ep_f = config["epaisseur_facade"]
    h_plinthe = config["hauteur_plinthe"]
    assemblage = config["assemblage"]
    nb_comp = config["nombre_compartiments"]

    couleur_struct = _rgb_to_hex(config["panneau"]["couleur_rgb"])
    couleur_facade = _rgb_to_hex(config["facade"]["couleur_rgb"])
    couleur_fond = "#D4C5A9"
    couleur_plinthe = "#404040"
    couleur_etagere = _rgb_to_hex(config["panneau"]["couleur_rgb"])

    h_corps = H - h_plinthe

    # Dimensions selon assemblage
    if assemblage == "dessus_sur":
        flanc_h = h_corps - 2 * ep
        flanc_z = h_plinthe + ep
    else:
        flanc_h = h_corps
        flanc_z = h_plinthe

    # --- Flanc (vu de cote : P x flanc_h) ---
    rects.append(Rect(0, flanc_z, P, flanc_h,
                       couleur_struct, "Cote (flanc)", "flanc"))

    # --- Dessus ---
    rects.append(Rect(0, h_plinthe + h_corps - ep, P, ep,
                       couleur_struct, "Dessus", "dessus"))

    # --- Dessous ---
    rects.append(Rect(0, h_plinthe, P, ep,
                       couleur_struct, "Dessous", "dessous"))

    # --- Fond ---
    fond_cfg = config["fond"]
    ep_fond = fond_cfg["epaisseur"]
    if fond_cfg["type"] == "rainure":
        fond_x = P - fond_cfg["distance_chant"] - ep_fond
        prof_r = fond_cfg["profondeur_rainure"]
        # Le fond rentre dans les rainures du dessus et du dessous
        z_fond_bas = h_plinthe + ep - prof_r
        h_fond = h_corps - 2 * ep + 2 * prof_r
    elif fond_cfg["type"] == "applique":
        fond_x = P - ep_fond
        z_fond_bas = h_plinthe + ep
        h_fond = h_corps - 2 * ep
    else:
        fond_x = P - ep_fond
        z_fond_bas = h_plinthe + ep
        h_fond = h_corps - 2 * ep

    rects.append(Rect(fond_x, z_fond_bas, ep_fond, h_fond,
                       couleur_fond, "Fond", "fond"))

    # --- Plinthe ---
    plinthe_cfg = config["plinthe"]
    if plinthe_cfg["type"] != "aucune":
        retrait_p = plinthe_cfg["retrait"]
        rects.append(Rect(retrait_p, 0, plinthe_cfg["epaisseur"], h_plinthe,
                           couleur_plinthe, "Plinthe", "plinthe"))

    # --- Etageres (coupe montrant la profondeur a chaque hauteur) ---
    # On prend le premier compartiment qui a des etageres
    for comp_idx in range(nb_comp):
        comp_data = config["compartiments"][comp_idx]
        nb_etag = comp_data["etageres"]
        if nb_etag > 0:
            z_bas_etag = h_plinthe + ep
            z_haut_etag = h_plinthe + h_corps - ep
            h_zone = z_haut_etag - z_bas_etag
            espacement = h_zone / (nb_etag + 1)
            retrait_av = config["etagere"]["retrait_avant"]
            prof_etag = (P - retrait_av
                         - fond_cfg["distance_chant"] - ep_fond)

            for e_idx in range(nb_etag):
                z_e = z_bas_etag + espacement * (e_idx + 1)
                # Retrait a l'avant : l'etagere commence apres le retrait
                rects.append(Rect(
                    retrait_av, z_e, prof_etag, ep,
                    couleur_etagere,
                    f"Etagere E{e_idx+1}", "etagere"
                ))
            break  # une seule coupe representative

    # --- Rainures dans le flanc (vue en coupe) ---
    couleur_rainure = "#6B5B3A"
    crem_cfg = config["cremaillere"]
    crem_prof = crem_cfg.get("profondeur", 7)
    h_crem = h_corps - 2 * ep
    z_crem = h_plinthe + ep

    # Rainure fond (si type rainure) dans flanc, dessus et dessous
    if fond_cfg["type"] == "rainure":
        prof_r = fond_cfg["profondeur_rainure"]
        # Rainure dans le flanc (bande verticale)
        rects.append(Rect(fond_x, h_plinthe + ep, prof_r, h_corps - 2 * ep,
                           couleur_rainure, "Rainure fond flanc", "rainure"))
        # Rainure dans le dessus (bande horizontale en haut)
        rects.append(Rect(fond_x, h_plinthe + h_corps - ep, ep_fond, ep,
                           couleur_rainure, "Rainure fond dessus", "rainure"))
        # Rainure dans le dessous (bande horizontale en bas)
        rects.append(Rect(fond_x, h_plinthe, ep_fond, ep,
                           couleur_rainure, "Rainure fond dessous", "rainure"))

    # Rainures cremailleres (entailles dans le flanc)
    x_crem_av = crem_cfg["distance_avant"]
    x_crem_ar = fond_x - crem_cfg["distance_arriere"] - crem_cfg["largeur"]
    rects.append(Rect(x_crem_av, z_crem, crem_prof, h_crem,
                       couleur_rainure, "Rainure crem avant", "rainure"))
    rects.append(Rect(x_crem_ar, z_crem, crem_prof, h_crem,
                       couleur_rainure, "Rainure crem arriere", "rainure"))

    # --- Cremailleres (bandes verticales sur les flancs) ---
    # Positionnees entre la face avant (0) et le fond (fond_x)
    # Cremaillere avant
    rects.append(Rect(
        x_crem_av, z_crem,
        crem_cfg["largeur"], h_crem,
        "#A0A0A0", "Cremaillere avant", "cremaillere"
    ))
    # Cremaillere arriere (reference = panneau de fond)
    rects.append(Rect(
        x_crem_ar, z_crem,
        crem_cfg["largeur"], h_crem,
        "#A0A0A0", "Cremaillere arriere", "cremaillere"
    ))

    # --- Facades (en coupe, a l'avant) ---
    jeu_p = config["porte"]
    z_facade_bas = h_plinthe + jeu_p["jeu_bas"]
    z_facade_haut = H - jeu_p["jeu_haut"]
    h_facade_zone = z_facade_haut - z_facade_bas

    # Chercher le type de facade le plus representatif
    facade_type = "niche"
    nb_tiroirs = 0
    for comp_data in config["compartiments"]:
        ft = comp_data["facade"]["type"]
        if ft != "niche":
            facade_type = ft
            nb_tiroirs = comp_data["facade"].get("nb_tiroirs", 0)
            break

    if facade_type == "portes":
        rects.append(Rect(
            -ep_f, z_facade_bas, ep_f, h_facade_zone,
            couleur_facade, "Porte (coupe)", "porte"
        ))
    elif facade_type == "tiroirs" and nb_tiroirs > 0:
        jeu_entre_t = config["tiroir"]["jeu_entre"]
        h_facade_tiroir = ((h_facade_zone - (nb_tiroirs - 1)
                            * jeu_entre_t) / nb_tiroirs)
        for t_idx in range(nb_tiroirs):
            z_t = z_facade_bas + t_idx * (h_facade_tiroir + jeu_entre_t)
            rects.append(Rect(
                -ep_f, z_t, ep_f, h_facade_tiroir,
                couleur_facade, f"Tiroir T{t_idx+1} (coupe)", "tiroir"
            ))
    elif facade_type == "mixte":
        # Simplifie : une facade pleine
        rects.append(Rect(
            -ep_f, z_facade_bas, ep_f, h_facade_zone,
            couleur_facade, "Facade (coupe)", "porte"
        ))

    # --- Cotations ---
    rects.append(Rect(0, -50, P, 2, "#333333", f"{P:.0f}", "cotation"))
    rects.append(Rect(-50, 0, 2, H, "#333333", f"{H:.0f}", "cotation"))

    return rects
