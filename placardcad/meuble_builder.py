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
#  Charnieres: 71B959 (applique), 71B969 (semi-applique), 71B979 (encloisonnee)
#  Embases: 174710ZE
# =====================================================================

CLIP_TOP_DIAMETRE_CUVETTE = 35.0
CLIP_TOP_PROFONDEUR_CUVETTE = 13.0
CLIP_TOP_DISTANCE_BORD = 3.0
CLIP_TOP_MARGE_HAUT_BAS = 80.0  # distance min du bord haut/bas de la porte

RECOUVREMENT = {
    "applique": 16.0,       # 71B959
    "semi_applique": 8.0,   # 71B969
    "encloisonnee": 0.0,    # 71B979, jeu de 2mm
}

CLIP_TOP_REFS = {
    "applique": "71B959",
    "semi_applique": "71B969",
    "encloisonnee": "71B979",
}

# =====================================================================
#  Catalogue poignees baton inox (POI12xxxIN)
# =====================================================================

POIGNEE_BATON_CATALOGUE = {
    96:  {"ref": "POI1296IN",  "longueur": 154},
    128: {"ref": "POI12128IN", "longueur": 186},
    160: {"ref": "POI12160IN", "longueur": 218},
    192: {"ref": "POI12192IN", "longueur": 250},
    224: {"ref": "POI12224IN", "longueur": 282},
    256: {"ref": "POI12256IN", "longueur": 314},
    320: {"ref": "POI12320IN", "longueur": 384},
    392: {"ref": "POI12392IN", "longueur": 456},
    492: {"ref": "POI12492IN", "longueur": 556},
    592: {"ref": "POI12592IN", "longueur": 656},
    692: {"ref": "POI12692IN", "longueur": 756},
    792: {"ref": "POI12792IN", "longueur": 856},
}


def _ajouter_poignee(
    rects: list[Rect],
    config: dict,
    x_facade: float,
    z_facade: float,
    w_facade: float,
    h_facade: float,
    label: str,
) -> None:
    """Ajoute un rectangle de poignee sur une facade (vue de face).

    La poignee est centree en largeur et placee a distance_haut du haut.

    Args:
        rects: Liste de Rect a completer.
        config: Configuration complete du meuble.
        x_facade: Position X de la facade.
        z_facade: Position Z basse de la facade.
        w_facade: Largeur de la facade.
        h_facade: Hauteur de la facade.
        label: Libelle de la poignee.
    """
    poignee_cfg = config.get("poignee", {})
    if poignee_cfg.get("modele", "baton_inox") == "aucune":
        return
    entraxe = int(poignee_cfg.get("entraxe", 128))
    diametre = poignee_cfg.get("diametre", 12)
    dist_haut = poignee_cfg.get("distance_haut", 50)
    cat = POIGNEE_BATON_CATALOGUE.get(entraxe)
    longueur = cat["longueur"] if cat else entraxe + 58

    x_poignee = x_facade + (w_facade - longueur) / 2
    z_poignee = z_facade + h_facade - dist_haut - diametre / 2
    rects.append(Rect(
        x_poignee, z_poignee, longueur, diametre,
        "#A0A0A0", label, "poignee"
    ))


def _get_recouvrement_facade(facade: dict, pose_globale: str) -> tuple[float, float]:
    """Retourne (rec_gauche, rec_droite) pour une facade.

    Si le type de charniere est specifie dans la facade, l'utilise.
    Sinon, utilise la pose globale du meuble.

    Args:
        facade: Dictionnaire facade avec charniere optionnel.
        pose_globale: Pose globale du meuble (applique, semi_applique, encloisonnee).

    Returns:
        Tuple (recouvrement_gauche, recouvrement_droite) en mm.
    """
    ch = facade.get("charniere")
    ch_g = facade.get("charniere_g")
    ch_d = facade.get("charniere_d")

    if ch:
        rec = RECOUVREMENT.get(ch, RECOUVREMENT.get(pose_globale, 16.0))
        return rec, rec
    elif ch_g or ch_d:
        rec_g = RECOUVREMENT.get(ch_g or pose_globale, 16.0)
        rec_d = RECOUVREMENT.get(ch_d or pose_globale, 16.0)
        return rec_g, rec_d
    else:
        rec = RECOUVREMENT.get(pose_globale, 16.0)
        return rec, rec


def _get_ref_charniere(facade: dict, pose_globale: str, cote: str = "g") -> str:
    """Retourne la reference Blum de la charniere pour une facade.

    Args:
        facade: Dictionnaire facade.
        pose_globale: Pose globale du meuble.
        cote: 'g' pour gauche, 'd' pour droite.

    Returns:
        Reference Blum (ex: '71B959').
    """
    ch = facade.get("charniere")
    if ch:
        return CLIP_TOP_REFS.get(ch, CLIP_TOP_REFS.get(pose_globale, "71B959"))
    ch_side = facade.get(f"charniere_{cote}")
    if ch_side:
        return CLIP_TOP_REFS.get(ch_side, CLIP_TOP_REFS.get(pose_globale, "71B959"))
    return CLIP_TOP_REFS.get(pose_globale, "71B959")


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


def _positions_charnieres(h_porte: float, nb: int) -> list[float]:
    """Calcule les positions verticales des charnieres sur une porte.

    Les positions sont relatives au bas de la porte.

    Args:
        h_porte: Hauteur de la porte en mm.
        nb: Nombre de charnieres.

    Returns:
        Liste des positions Y (depuis le bas) en mm.
    """
    marge = CLIP_TOP_MARGE_HAUT_BAS
    if nb <= 1:
        return [h_porte / 2]
    positions = []
    for i in range(nb):
        positions.append(marge + i * (h_porte - 2 * marge) / (nb - 1))
    return positions


def _ajouter_porte_details(
    rects: list[Rect],
    x_porte: float,
    z_bas: float,
    w_porte: float,
    h_porte: float,
    ouverture: str,
) -> None:
    """Ajoute les symboles d'ouverture et percages de charnieres sur une porte.

    Genere des Rect avec type_elem='ouverture' (triangle d'ouverture)
    et type_elem='percage' (cercles de percage charniere).

    Args:
        rects: Liste de Rect a completer.
        x_porte: Position X de la porte.
        z_bas: Position Z basse de la porte.
        w_porte: Largeur de la porte.
        h_porte: Hauteur de la porte.
        ouverture: Direction: 'gauche' (PG='>'), 'droite' (PD='<').
    """
    if ouverture not in ("gauche", "droite"):
        return

    # Symbole d'ouverture (triangle > ou <)
    direction = "G" if ouverture == "gauche" else "D"
    rects.append(Rect(x_porte, z_bas, w_porte, h_porte,
                       "#333366", direction, "ouverture"))

    # Percages de charnieres (cercles)
    nb_ch = _nb_charnieres(h_porte)
    positions = _positions_charnieres(h_porte, nb_ch)
    diam = CLIP_TOP_DIAMETRE_CUVETTE
    offset_x = CLIP_TOP_DISTANCE_BORD + diam / 2

    for z_pos in positions:
        if ouverture == "gauche":
            cx = x_porte + offset_x
        else:
            cx = x_porte + w_porte - offset_x
        cy = z_bas + z_pos
        rects.append(Rect(cx - diam / 2, cy - diam / 2, diam, diam,
                           "#5A5A8A", "Percage", "percage"))


def _render_facade_groupes(
    rects: list[Rect],
    fiche: FicheFabrication,
    config: dict,
    comp_idx: int,
    cg: dict,
    groupes: list[dict],
    x_facade: float,
    w_facade: float,
    z_facade_bas: float,
    z_facade_haut: float,
    couleur_facade: str,
    ep_f: float,
    jeu_p: dict,
) -> None:
    """Rendu d'une facade composee de groupes ordonnes du bas vers le haut.

    Chaque groupe est soit un groupe de tiroirs (avec hauteur LEGRABOX),
    soit un groupe de portes (qui recoit l'espace restant).

    Les tiroirs sont adaptes pour remplir la hauteur du meuble :
    le tiroir du haut garde sa hauteur LEGRABOX minimum, les tiroirs
    du bas sont agrandis pour occuper l'espace disponible.

    Args:
        rects: Liste de Rect a completer.
        fiche: Fiche de fabrication a completer.
        config: Configuration complete du meuble.
        comp_idx: Indice du compartiment.
        cg: Geometrie du compartiment (x, largeur).
        groupes: Liste de groupes ordonnes bas->haut.
        x_facade: Position X de la facade.
        w_facade: Largeur de la facade.
        z_facade_bas: Position Z basse de la zone facade.
        z_facade_haut: Position Z haute de la zone facade.
        couleur_facade: Couleur de la facade.
        ep_f: Epaisseur facade.
        jeu_p: Parametres porte (jeux).
    """
    h_facade_zone = z_facade_haut - z_facade_bas
    jeu_entre_t = config["tiroir"]["jeu_entre"]
    jeu_entre_g = jeu_p["jeu_entre"]
    P = config["profondeur"]
    hauteur_defaut = config["tiroir"]["hauteur"]

    # --- Calculer la hauteur minimale de chaque groupe ---
    group_infos: list[dict] = []
    total_fixed = 0.0
    nb_porte_groups = 0

    for g in groupes:
        if g["type"] == "tiroir":
            h_code = g.get("hauteur") or hauteur_defaut
            h_cote = LEGRABOX_HAUTEURS.get(h_code, 90.5)
            h_tiroir_min = h_cote + 2 * jeu_p["jeu_haut"]
            nb = g["nombre"]
            h_zone = nb * h_tiroir_min + max(0, nb - 1) * jeu_entre_t
            group_infos.append({
                "type": "tiroir", "hauteur": h_code, "nombre": nb,
                "h_zone": h_zone, "h_facade_min": h_tiroir_min,
                "h_cote": h_cote,
            })
            total_fixed += h_zone
        elif g["type"] == "porte":
            group_infos.append({
                "type": "porte", "nombre": g["nombre"],
                "ouverture": g.get("ouverture", "gauche"),
                "h_zone": 0.0,
            })
            nb_porte_groups += 1

    nb_gaps = max(0, len(groupes) - 1)
    has_porte = nb_porte_groups > 0

    # --- Adapter les hauteurs de tiroirs a l'espace disponible ---
    # Le tiroir du haut garde sa hauteur minimale LEGRABOX.
    # Les tiroirs du bas sont agrandis pour remplir l'espace.
    if has_porte:
        # Avec portes : les portes absorbent l'espace restant
        remaining = h_facade_zone - total_fixed - nb_gaps * jeu_entre_g
        if nb_porte_groups > 0:
            h_per_porte = remaining / nb_porte_groups
            for gi in group_infos:
                if gi["type"] == "porte":
                    gi["h_zone"] = h_per_porte
        # Tiroirs gardent leurs hauteurs minimales
        for gi in group_infos:
            if gi["type"] == "tiroir":
                gi["h_facade_bas"] = gi["h_facade_min"]
                gi["h_facade_haut"] = gi["h_facade_min"]
                gi["nb_bas"] = gi["nombre"]
    else:
        # Pure tiroirs : adapter les hauteurs
        extra = h_facade_zone - total_fixed - nb_gaps * jeu_entre_g

        # Trouver le groupe tiroir le plus haut (dernier dans la liste)
        topmost_idx = -1
        for i in range(len(group_infos) - 1, -1, -1):
            if group_infos[i]["type"] == "tiroir":
                topmost_idx = i
                break

        # Compter les tiroirs adaptables (tous sauf le dernier du groupe haut)
        nb_adaptable = 0
        for i, gi in enumerate(group_infos):
            if gi["type"] == "tiroir":
                if i == topmost_idx:
                    nb_adaptable += gi["nombre"] - 1
                else:
                    nb_adaptable += gi["nombre"]

        if extra > 0 and nb_adaptable > 0:
            extra_per = extra / nb_adaptable
            for i, gi in enumerate(group_infos):
                if gi["type"] != "tiroir":
                    continue
                if i == topmost_idx:
                    # Dernier groupe : tiroirs du bas adaptes, le dernier au minimum
                    gi["nb_bas"] = gi["nombre"] - 1
                    gi["h_facade_bas"] = gi["h_facade_min"] + extra_per
                    gi["h_facade_haut"] = gi["h_facade_min"]
                else:
                    # Groupes inferieurs : tous adaptes
                    gi["nb_bas"] = gi["nombre"]
                    gi["h_facade_bas"] = gi["h_facade_min"] + extra_per
                    gi["h_facade_haut"] = gi["h_facade_min"] + extra_per
                # Recalculer h_zone
                nb_b = gi["nb_bas"]
                nb_h = gi["nombre"] - nb_b
                gi["h_zone"] = (nb_b * gi["h_facade_bas"]
                                + nb_h * gi["h_facade_haut"]
                                + max(0, gi["nombre"] - 1) * jeu_entre_t)
        else:
            # Pas d'espace extra : tous au minimum
            for gi in group_infos:
                if gi["type"] == "tiroir":
                    gi["h_facade_bas"] = gi["h_facade_min"]
                    gi["h_facade_haut"] = gi["h_facade_min"]
                    gi["nb_bas"] = gi["nombre"]

    # --- Positionner et dessiner chaque groupe (bas -> haut) ---
    z_current = z_facade_bas

    for gi_idx, gi in enumerate(group_infos):
        if gi_idx > 0:
            z_current += jeu_entre_g

        if gi["type"] == "tiroir":
            nb = gi["nombre"]
            nb_bas = gi.get("nb_bas", nb)
            h_bas = gi.get("h_facade_bas", gi["h_facade_min"])
            h_haut = gi.get("h_facade_haut", gi["h_facade_min"])
            h_code = gi["hauteur"]
            h_cote = gi["h_cote"]

            z_t = z_current
            for t_idx in range(nb):
                h_t = h_bas if t_idx < nb_bas else h_haut
                rects.append(Rect(
                    x_facade, z_t, w_facade, h_t,
                    couleur_facade,
                    f"Tiroir C{comp_idx+1} {h_code}{t_idx+1}", "tiroir"
                ))
                _ajouter_poignee(
                    rects, config, x_facade, z_t, w_facade, h_t,
                    f"Poignee tiroir C{comp_idx+1} {h_code}{t_idx+1}")
                z_t += h_t + jeu_entre_t

            # BOM: facades tiroirs (groupees par dimension)
            larg_tiroir = cg["largeur"] - 2 * LEGRABOX_JEU_LATERAL
            lg_coulisse = _longueur_coulisse(P, ep_f)
            nb_haut = nb - nb_bas

            if nb_bas > 0:
                fiche.ajouter_piece(PieceInfo(
                    f"Facade tiroir {h_code} C{comp_idx+1}",
                    w_facade, h_bas, ep_f,
                    couleur_fab=config["facade"]["couleur_fab"],
                    chant_desc="4 chants",
                    quantite=nb_bas,
                ))
            if nb_haut > 0 and abs(h_haut - h_bas) > 0.1:
                fiche.ajouter_piece(PieceInfo(
                    f"Facade tiroir {h_code} haut C{comp_idx+1}",
                    w_facade, h_haut, ep_f,
                    couleur_fab=config["facade"]["couleur_fab"],
                    chant_desc="4 chants",
                    quantite=nb_haut,
                ))
            elif nb_haut > 0:
                # Meme dimension que les bas : ajouter a la quantite
                fiche.pieces[-1] = PieceInfo(
                    f"Facade tiroir {h_code} C{comp_idx+1}",
                    w_facade, h_bas, ep_f,
                    couleur_fab=config["facade"]["couleur_fab"],
                    chant_desc="4 chants",
                    quantite=nb,
                )

            # BOM: fond tiroir (memes dimensions pour tous)
            fiche.ajouter_piece(PieceInfo(
                f"Fond tiroir {h_code} C{comp_idx+1}",
                larg_tiroir, lg_coulisse - 2 * LEGRABOX_EP_PAROI,
                LEGRABOX_EP_FOND,
                materiau="Panneau fond",
                couleur_fab=config["panneau"]["couleur_fab"],
                quantite=nb,
            ))

            # BOM: arriere tiroir
            fiche.ajouter_piece(PieceInfo(
                f"Arriere tiroir {h_code} C{comp_idx+1}",
                larg_tiroir - 2 * LEGRABOX_EP_PAROI,
                h_cote - LEGRABOX_EP_FOND,
                LEGRABOX_EP_PAROI,
                materiau="Panneau fond",
                couleur_fab=config["panneau"]["couleur_fab"],
                quantite=nb,
            ))

            # BOM: coulisses
            fiche.ajouter_quincaillerie(
                f"Coulisse LEGRABOX {h_code} (C{comp_idx+1})",
                nb * 2,
                f"Paire, L={lg_coulisse}mm, hauteur {h_code}"
            )

            z_current += gi["h_zone"]

        elif gi["type"] == "porte":
            h_zone_porte = gi["h_zone"]
            nb_portes = gi["nombre"]
            ouverture = gi.get("ouverture", "gauche")
            pose_globale = config["pose"]

            if nb_portes >= 2:
                jeu_e = jeu_p["jeu_entre"]
                w_porte = (w_facade - jeu_e) / 2
                rects.append(Rect(
                    x_facade, z_current, w_porte, h_zone_porte,
                    couleur_facade, f"Porte G C{comp_idx+1}", "porte"
                ))
                rects.append(Rect(
                    x_facade + w_porte + jeu_e, z_current,
                    w_porte, h_zone_porte,
                    couleur_facade, f"Porte D C{comp_idx+1}", "porte"
                ))
                _ajouter_poignee(
                    rects, config, x_facade, z_current,
                    w_porte, h_zone_porte,
                    f"Poignee porte G C{comp_idx+1}")
                _ajouter_poignee(
                    rects, config,
                    x_facade + w_porte + jeu_e, z_current,
                    w_porte, h_zone_porte,
                    f"Poignee porte D C{comp_idx+1}")
                _ajouter_porte_details(
                    rects, x_facade, z_current,
                    w_porte, h_zone_porte, "gauche")
                _ajouter_porte_details(
                    rects, x_facade + w_porte + jeu_e, z_current,
                    w_porte, h_zone_porte, "droite")
                fiche.ajouter_piece(PieceInfo(
                    f"Porte C{comp_idx+1}",
                    w_porte, h_zone_porte, ep_f,
                    couleur_fab=config["facade"]["couleur_fab"],
                    chant_desc="4 chants",
                    quantite=2,
                ))
                nb_ch = _nb_charnieres(h_zone_porte)
                ref_g = _get_ref_charniere(g, pose_globale, "g")
                ref_d = _get_ref_charniere(g, pose_globale, "d")
                if ref_g == ref_d:
                    fiche.ajouter_quincaillerie(
                        f"Charnieres CLIP top {ref_g} (C{comp_idx+1})",
                        nb_ch * 2, f"2 portes x {nb_ch} charnieres"
                    )
                else:
                    fiche.ajouter_quincaillerie(
                        f"Charnieres CLIP top {ref_g} G (C{comp_idx+1})",
                        nb_ch, f"Porte gauche"
                    )
                    fiche.ajouter_quincaillerie(
                        f"Charnieres CLIP top {ref_d} D (C{comp_idx+1})",
                        nb_ch, f"Porte droite"
                    )
                fiche.ajouter_quincaillerie(
                    f"Embases 174710ZE (C{comp_idx+1})",
                    nb_ch * 2, f"Pour charnieres CLIP top"
                )
            else:
                rects.append(Rect(
                    x_facade, z_current, w_facade, h_zone_porte,
                    couleur_facade, f"Porte C{comp_idx+1}", "porte"
                ))
                _ajouter_poignee(
                    rects, config, x_facade, z_current,
                    w_facade, h_zone_porte,
                    f"Poignee porte C{comp_idx+1}")
                _ajouter_porte_details(
                    rects, x_facade, z_current,
                    w_facade, h_zone_porte, ouverture)
                fiche.ajouter_piece(PieceInfo(
                    f"Porte C{comp_idx+1}",
                    w_facade, h_zone_porte, ep_f,
                    couleur_fab=config["facade"]["couleur_fab"],
                    chant_desc="4 chants",
                ))
                nb_ch = _nb_charnieres(h_zone_porte)
                ref_ch = _get_ref_charniere(g, pose_globale)
                fiche.ajouter_quincaillerie(
                    f"Charnieres CLIP top {ref_ch} (C{comp_idx+1})",
                    nb_ch, f"Porte {h_zone_porte:.0f}mm"
                )
                fiche.ajouter_quincaillerie(
                    f"Embases 174710ZE (C{comp_idx+1})",
                    nb_ch, f"Pour charnieres {ref_ch}"
                )

            z_current += h_zone_porte


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

    # Recouvrement facade (global, sera surcharge par facade si charniere specifiee)
    jeu_p = config["porte"]

    # =====================================================================
    #  STRUCTURE
    # =====================================================================

    # --- Plinthe ---
    plinthe_cfg = config["plinthe"]
    if plinthe_cfg["type"] != "aucune":
        retrait_p = plinthe_cfg["retrait"]
        ep_plinthe = plinthe_cfg["epaisseur"]

        if plinthe_cfg["type"] == "trois_cotes":
            retrait_g = plinthe_cfg.get("retrait_gauche", retrait_p)
            retrait_d = plinthe_cfg.get("retrait_droite", retrait_p)
            plinthe_x = retrait_g
            plinthe_w = L - retrait_g - retrait_d
        else:
            plinthe_x = retrait_p
            plinthe_w = L - 2 * retrait_p

        rects.append(Rect(
            plinthe_x, 0, plinthe_w, h_plinthe,
            couleur_plinthe, "Plinthe avant", "plinthe"
        ))
        fiche.ajouter_piece(PieceInfo(
            "Plinthe avant",
            plinthe_w, h_plinthe, ep_plinthe,
            couleur_fab=config["panneau"]["couleur_fab"],
        ))
        if plinthe_cfg["type"] == "trois_cotes":
            longueur_cote = P - retrait_p - ep_plinthe
            for cote, nom in [("gauche", "Plinthe gauche"),
                              ("droite", "Plinthe droite")]:
                fiche.ajouter_piece(PieceInfo(
                    nom, longueur_cote, h_plinthe, ep_plinthe,
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
    dessus_cfg = config.get("dessus", {})
    dessus_type = dessus_cfg.get("type", "traverses")
    z_dessus = h_plinthe + h_corps - ep

    if dessus_type == "plein":
        rects.append(Rect(dessus_x, z_dessus, dessus_w, ep,
                           couleur_struct, "Dessus", "dessus"))
        fiche.ajouter_piece(PieceInfo(
            "Dessus", dessus_w, P, ep,
            couleur_fab=config["panneau"]["couleur_fab"],
            chant_desc=f"Avant {config['panneau']['chant_epaisseur']}mm",
        ))
    else:  # traverses
        larg_trav = dessus_cfg.get("largeur_traverse", 100)
        # Traverse avant (visible de face)
        rects.append(Rect(dessus_x, z_dessus, dessus_w, ep,
                           couleur_struct, "Traverse avant", "traverse"))
        fiche.ajouter_piece(PieceInfo(
            "Traverse avant", dessus_w, larg_trav, ep,
            couleur_fab=config["panneau"]["couleur_fab"],
            chant_desc=f"Avant {config['panneau']['chant_epaisseur']}mm",
        ))
        fiche.ajouter_piece(PieceInfo(
            "Traverse arriere", dessus_w, larg_trav, ep,
            couleur_fab=config["panneau"]["couleur_fab"],
        ))

    # --- Dessous ---
    retrait_ar_dessous = config.get("dessous", {}).get("retrait_arriere", 50)
    prof_dessous = P - retrait_ar_dessous
    rects.append(Rect(dessous_x, h_plinthe, dessous_w, ep,
                       couleur_struct, "Dessous", "dessous"))
    fiche.ajouter_piece(PieceInfo(
        "Dessous", dessous_w, prof_dessous, ep,
        couleur_fab=config["panneau"]["couleur_fab"],
        chant_desc=f"Avant {config['panneau']['chant_epaisseur']}mm",
    ))

    # --- Fond ---
    fond_cfg = config["fond"]
    fond_type = fond_cfg["type"]
    hauteur_fond_imposee = fond_cfg.get("hauteur", 0)
    if fond_type == "rainure":
        fond_l = L - 2 * ep + 2 * fond_cfg["profondeur_rainure"]
        if hauteur_fond_imposee > 0:
            fond_h = hauteur_fond_imposee + 2 * fond_cfg["profondeur_rainure"]
        else:
            fond_h = h_corps - 2 * ep + 2 * fond_cfg["profondeur_rainure"]
    elif fond_type == "applique":
        fond_l = L
        fond_h = hauteur_fond_imposee if hauteur_fond_imposee > 0 else h_corps
    else:  # vissage
        fond_l = larg_int
        fond_h = hauteur_fond_imposee if hauteur_fond_imposee > 0 else h_corps - 2 * ep

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

        # Recouvrement par facade (charniere specifique ou pose globale)
        rec_g, rec_d = _get_recouvrement_facade(facade, pose)
        is_encl = (rec_g == 0 and rec_d == 0)

        # Zone facade disponible
        z_facade_bas = h_plinthe + jeu_p["jeu_bas"]
        z_facade_haut = H - jeu_p["jeu_haut"]
        if is_encl:
            z_facade_bas = h_plinthe + ep + jeu_p["jeu_bas"]
            z_facade_haut = h_plinthe + h_corps - ep - jeu_p["jeu_haut"]
        h_facade_zone = z_facade_haut - z_facade_bas

        # Position X de la facade
        if is_encl:
            x_facade = cg["x"] + jeu_p["jeu_lateral"]
            w_facade = cg["largeur"] - 2 * jeu_p["jeu_lateral"]
        else:
            x_facade = cg["x"] - rec_g + jeu_p["jeu_lateral"]
            w_facade = cg["largeur"] + rec_g + rec_d - 2 * jeu_p["jeu_lateral"]
            if comp_idx == 0:
                x_facade = -rec_g + ep + jeu_p["jeu_lateral"]
            if comp_idx == nb_comp - 1:
                w_facade = (cg["x"] + cg["largeur"] + rec_d
                            - jeu_p["jeu_lateral"]) - x_facade

        # Determiner si on utilise le rendu par groupes
        groupes = facade.get("groupes", [])
        use_groupes = (
            len(groupes) > 1
            or any(g.get("hauteur") is not None
                   for g in groupes if g["type"] == "tiroir")
        )

        if facade_type == "niche":
            pass  # Rien a dessiner

        elif use_groupes:
            # Rendu unifie par groupes (multi-hauteurs, mixte, etc.)
            _render_facade_groupes(
                rects, fiche, config, comp_idx, cg, groupes,
                x_facade, w_facade, z_facade_bas, z_facade_haut,
                couleur_facade, ep_f, jeu_p,
            )

        # --- Portes (groupe unique, pas de hauteur explicite) ---
        elif facade_type == "portes":
            nb_portes = facade["nb_portes"]
            ouverture = facade.get("ouverture", "gauche")
            if nb_portes == 1:
                rects.append(Rect(
                    x_facade, z_facade_bas, w_facade, h_facade_zone,
                    couleur_facade,
                    f"Porte C{comp_idx+1}", "porte"
                ))
                _ajouter_poignee(
                    rects, config, x_facade, z_facade_bas,
                    w_facade, h_facade_zone,
                    f"Poignee porte C{comp_idx+1}")
                _ajouter_porte_details(
                    rects, x_facade, z_facade_bas,
                    w_facade, h_facade_zone, ouverture)
                fiche.ajouter_piece(PieceInfo(
                    f"Porte C{comp_idx+1}",
                    w_facade, h_facade_zone, ep_f,
                    couleur_fab=config["facade"]["couleur_fab"],
                    chant_desc="4 chants",
                ))
                nb_ch = _nb_charnieres(h_facade_zone)
                ref_ch = _get_ref_charniere(facade, pose)
                fiche.ajouter_quincaillerie(
                    f"Charnieres CLIP top {ref_ch} (C{comp_idx+1})",
                    nb_ch, f"Porte {h_facade_zone:.0f}mm"
                )
                fiche.ajouter_quincaillerie(
                    f"Embases 174710ZE (C{comp_idx+1})",
                    nb_ch, f"Pour charnieres {ref_ch}"
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
                _ajouter_poignee(
                    rects, config, x_facade, z_facade_bas,
                    w_porte, h_facade_zone,
                    f"Poignee porte G C{comp_idx+1}")
                _ajouter_poignee(
                    rects, config,
                    x_facade + w_porte + jeu_e, z_facade_bas,
                    w_porte, h_facade_zone,
                    f"Poignee porte D C{comp_idx+1}")
                # Ouverture et percages : gauche > | < droite
                _ajouter_porte_details(
                    rects, x_facade, z_facade_bas,
                    w_porte, h_facade_zone, "gauche")
                _ajouter_porte_details(
                    rects, x_facade + w_porte + jeu_e, z_facade_bas,
                    w_porte, h_facade_zone, "droite")
                fiche.ajouter_piece(PieceInfo(
                    f"Porte C{comp_idx+1}",
                    w_porte, h_facade_zone, ep_f,
                    couleur_fab=config["facade"]["couleur_fab"],
                    chant_desc="4 chants",
                    quantite=2,
                ))
                nb_ch = _nb_charnieres(h_facade_zone)
                ref_ch_g = _get_ref_charniere(facade, pose, "g")
                ref_ch_d = _get_ref_charniere(facade, pose, "d")
                if ref_ch_g == ref_ch_d:
                    fiche.ajouter_quincaillerie(
                        f"Charnieres CLIP top {ref_ch_g} (C{comp_idx+1})",
                        nb_ch * 2, f"2 portes x {nb_ch} charnieres"
                    )
                    fiche.ajouter_quincaillerie(
                        f"Embases 174710ZE (C{comp_idx+1})",
                        nb_ch * 2, f"Pour charnieres {ref_ch_g}"
                    )
                else:
                    fiche.ajouter_quincaillerie(
                        f"Charnieres CLIP top {ref_ch_g} G (C{comp_idx+1})",
                        nb_ch, f"Porte gauche"
                    )
                    fiche.ajouter_quincaillerie(
                        f"Charnieres CLIP top {ref_ch_d} D (C{comp_idx+1})",
                        nb_ch, f"Porte droite"
                    )
                    fiche.ajouter_quincaillerie(
                        f"Embases 174710ZE (C{comp_idx+1})",
                        nb_ch * 2, f"Pour charnieres"
                    )

        # --- Tiroirs generiques T (groupe unique, hauteur=None) ---
        elif facade_type == "tiroirs":
            nb_tiroirs = facade["nb_tiroirs"]
            hauteur_legrabox = config["tiroir"]["hauteur"]
            jeu_entre_t = config["tiroir"]["jeu_entre"]

            h_facade_tiroir = ((h_facade_zone - (nb_tiroirs - 1)
                                * jeu_entre_t) / nb_tiroirs)

            for t_idx in range(nb_tiroirs):
                z_t = z_facade_bas + t_idx * (h_facade_tiroir + jeu_entre_t)
                rects.append(Rect(
                    x_facade, z_t, w_facade, h_facade_tiroir,
                    couleur_facade,
                    f"Tiroir C{comp_idx+1} T{t_idx+1}", "tiroir"
                ))
                _ajouter_poignee(
                    rects, config, x_facade, z_t,
                    w_facade, h_facade_tiroir,
                    f"Poignee tiroir C{comp_idx+1} T{t_idx+1}")

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

    # =====================================================================
    #  POIGNEES (BOM quincaillerie)
    # =====================================================================

    poignee_cfg = config.get("poignee", {})
    if poignee_cfg.get("modele", "baton_inox") != "aucune":
        nb_poignees = sum(1 for r in rects if r.type_elem == "poignee")
        if nb_poignees > 0:
            entraxe = int(poignee_cfg.get("entraxe", 128))
            cat = POIGNEE_BATON_CATALOGUE.get(entraxe)
            if cat:
                ref = cat["ref"]
                longueur = cat["longueur"]
            else:
                ref = f"POI12{entraxe}IN"
                longueur = entraxe + 58
            fiche.ajouter_quincaillerie(
                f"Poignee baton inox {ref}",
                nb_poignees,
                f"Entraxe {entraxe}mm, L={longueur}mm"
            )

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

    # --- Dessus ---
    dessus_cfg = config.get("dessus", {})
    dessus_type = dessus_cfg.get("type", "traverses")
    if assemblage == "dessus_sur":
        dessus_x, dessus_w = 0, L
    else:
        dessus_x, dessus_w = ep, L - 2 * ep

    if dessus_type == "plein":
        rects.append(Rect(dessus_x, 0, dessus_w, P,
                           couleur_struct, "Dessus", "dessus"))
    else:  # traverses
        larg_trav = dessus_cfg.get("largeur_traverse", 100)
        rects.append(Rect(dessus_x, 0, dessus_w, larg_trav,
                           couleur_struct, "Traverse avant", "traverse"))
        rects.append(Rect(dessus_x, P - larg_trav, dessus_w, larg_trav,
                           couleur_struct, "Traverse arriere", "traverse"))

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
    sep_retrait_av = config["separation"].get("retrait_avant", 0)
    sep_retrait_ar = config["separation"].get("retrait_arriere", 0)
    sep_prof = P - sep_retrait_av - sep_retrait_ar

    compartiments_geom: list[dict] = []
    for comp_idx in range(nb_comp):
        larg_c = largeurs[comp_idx]
        compartiments_geom.append({"x": x_cursor, "largeur": larg_c})

        if comp_idx < nb_comp - 1:
            x_sep = x_cursor + larg_c
            rects.append(Rect(x_sep, sep_retrait_av, ep_sep, sep_prof,
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
        hauteur_fond_imposee_top = fond_cfg.get("hauteur", 0)
        H = config["hauteur"]
        h_plinthe_top = config["hauteur_plinthe"]
        h_corps_top = H - h_plinthe_top
        h_int_corps_top = h_corps_top - 2 * ep
        # Flanc gauche
        rects.append(Rect(ep - prof_r, fond_y, prof_r, ep_fond,
                           couleur_rainure, "Rainure fond G", "rainure"))
        # Flanc droit
        rects.append(Rect(L - ep, fond_y, prof_r, ep_fond,
                           couleur_rainure, "Rainure fond D", "rainure"))
        # Dessus/traverse arriere (seulement si fond pleine hauteur)
        fond_atteint_dessus = (hauteur_fond_imposee_top <= 0
                               or hauteur_fond_imposee_top >= h_int_corps_top)
        if fond_atteint_dessus:
            if dessus_type == "plein":
                rects.append(Rect(dessus_x, fond_y, dessus_w, ep_fond,
                                   couleur_rainure, "Rainure fond dessus", "rainure"))
            else:
                rects.append(Rect(dessus_x, fond_y, dessus_w, ep_fond,
                                   couleur_rainure, "Rainure fond trav. ar.", "rainure"))
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
    jeu_p = config["porte"]

    for comp_idx in range(nb_comp):
        cg = compartiments_geom[comp_idx]
        comp_data = config["compartiments"][comp_idx]
        facade = comp_data["facade"]
        facade_type = facade["type"]

        if facade_type == "niche":
            continue

        # Position X de la facade (per-facade recouvrement)
        rec_g, rec_d = _get_recouvrement_facade(facade, pose)
        is_encl = (rec_g == 0 and rec_d == 0)

        if is_encl:
            x_facade = cg["x"] + jeu_p["jeu_lateral"]
            w_facade = cg["largeur"] - 2 * jeu_p["jeu_lateral"]
        else:
            x_facade = cg["x"] - rec_g + jeu_p["jeu_lateral"]
            w_facade = cg["largeur"] + rec_g + rec_d - 2 * jeu_p["jeu_lateral"]
            if comp_idx == 0:
                x_facade = -rec_g + ep + jeu_p["jeu_lateral"]
            if comp_idx == nb_comp - 1:
                w_facade = (cg["x"] + cg["largeur"] + rec_d
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
    dessus_cfg = config.get("dessus", {})
    dessus_type = dessus_cfg.get("type", "traverses")
    z_dessus = h_plinthe + h_corps - ep

    if dessus_type == "plein":
        rects.append(Rect(0, z_dessus, P, ep,
                           couleur_struct, "Dessus", "dessus"))
    else:  # traverses
        larg_trav = dessus_cfg.get("largeur_traverse", 100)
        rects.append(Rect(0, z_dessus, larg_trav, ep,
                           couleur_struct, "Traverse avant", "traverse"))
        rects.append(Rect(P - larg_trav, z_dessus, larg_trav, ep,
                           couleur_struct, "Traverse arriere", "traverse"))

    # --- Dessous ---
    retrait_ar_dessous = config.get("dessous", {}).get("retrait_arriere", 50)
    prof_dessous = P - retrait_ar_dessous
    rects.append(Rect(0, h_plinthe, prof_dessous, ep,
                       couleur_struct, "Dessous", "dessous"))

    # --- Fond ---
    fond_cfg = config["fond"]
    ep_fond = fond_cfg["epaisseur"]
    hauteur_fond_imposee = fond_cfg.get("hauteur", 0)
    if fond_cfg["type"] == "rainure":
        fond_x = P - fond_cfg["distance_chant"] - ep_fond
        prof_r = fond_cfg["profondeur_rainure"]
        if hauteur_fond_imposee > 0:
            z_fond_bas = h_plinthe + ep - prof_r
            h_fond = hauteur_fond_imposee + 2 * prof_r
        else:
            z_fond_bas = h_plinthe + ep - prof_r
            h_fond = h_corps - 2 * ep + 2 * prof_r
    elif fond_cfg["type"] == "applique":
        fond_x = P - ep_fond
        z_fond_bas = h_plinthe + ep
        h_fond = hauteur_fond_imposee if hauteur_fond_imposee > 0 else h_corps - 2 * ep
    else:
        fond_x = P - ep_fond
        z_fond_bas = h_plinthe + ep
        h_fond = hauteur_fond_imposee if hauteur_fond_imposee > 0 else h_corps - 2 * ep

    rects.append(Rect(fond_x, z_fond_bas, ep_fond, h_fond,
                       couleur_fond, "Fond", "fond"))

    # --- Plinthe ---
    plinthe_cfg = config["plinthe"]
    if plinthe_cfg["type"] != "aucune":
        retrait_p = plinthe_cfg["retrait"]
        ep_plinthe = plinthe_cfg["epaisseur"]
        rects.append(Rect(retrait_p, 0, ep_plinthe, h_plinthe,
                           couleur_plinthe, "Plinthe avant", "plinthe"))
        if plinthe_cfg["type"] == "trois_cotes":
            longueur_cote = P - retrait_p - ep_plinthe
            rects.append(Rect(retrait_p + ep_plinthe, 0,
                               longueur_cote, h_plinthe,
                               couleur_plinthe, "Plinthe cote", "plinthe"))

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
        h_int_corps = h_corps - 2 * ep
        h_rainure_flanc = (hauteur_fond_imposee
                           if hauteur_fond_imposee > 0
                           else h_int_corps)
        # Rainure dans le flanc (bande verticale)
        rects.append(Rect(fond_x, h_plinthe + ep, prof_r, h_rainure_flanc,
                           couleur_rainure, "Rainure fond flanc", "rainure"))
        # Rainure dans le dessus (seulement si fond pleine hauteur)
        if hauteur_fond_imposee <= 0 or hauteur_fond_imposee >= h_int_corps:
            rects.append(Rect(fond_x, h_plinthe + h_corps - ep, prof_r, prof_r,
                               couleur_rainure, "Rainure fond dessus", "rainure"))
        # Rainure dans le dessous (entaille depuis la face interieure vers le bas)
        rects.append(Rect(fond_x, h_plinthe + ep - prof_r, prof_r, prof_r,
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

    # Chercher la facade la plus representative
    facade_repr = None
    for comp_data in config["compartiments"]:
        ft = comp_data["facade"]["type"]
        if ft != "niche":
            facade_repr = comp_data["facade"]
            break

    if facade_repr is not None:
        groupes = facade_repr.get("groupes", [])
        facade_type = facade_repr["type"]
        use_groupes = (
            len(groupes) > 1
            or any(g.get("hauteur") is not None
                   for g in groupes if g["type"] == "tiroir")
        )

        if use_groupes:
            # Rendu par groupes avec adaptation des hauteurs (bas -> haut)
            jeu_entre_g = jeu_p["jeu_entre"]
            jeu_entre_t = config["tiroir"]["jeu_entre"]
            hauteur_defaut = config["tiroir"]["hauteur"]

            # Calculer les hauteurs minimales
            has_porte = any(g["type"] == "porte" for g in groupes)
            gi_list = []
            total_min = 0.0
            for g in groupes:
                if g["type"] == "tiroir":
                    h_code = g.get("hauteur") or hauteur_defaut
                    h_cote = LEGRABOX_HAUTEURS.get(h_code, 90.5)
                    h_min = h_cote + 2 * jeu_p["jeu_haut"]
                    nb = g["nombre"]
                    h_zone = nb * h_min + max(0, nb - 1) * jeu_entre_t
                    gi_list.append({"type": "tiroir", "nb": nb,
                                    "h_min": h_min, "h_zone": h_zone})
                    total_min += h_zone
                else:
                    gi_list.append({"type": "porte"})

            nb_gaps = max(0, len(groupes) - 1)

            # Adapter tiroirs si pas de porte
            if not has_porte:
                extra = h_facade_zone - total_min - nb_gaps * jeu_entre_g
                topmost = -1
                for i in range(len(gi_list) - 1, -1, -1):
                    if gi_list[i]["type"] == "tiroir":
                        topmost = i
                        break
                nb_adapt = 0
                for i, gi in enumerate(gi_list):
                    if gi["type"] == "tiroir":
                        nb_adapt += gi["nb"] - 1 if i == topmost else gi["nb"]
                if extra > 0 and nb_adapt > 0:
                    ep_extra = extra / nb_adapt
                    for i, gi in enumerate(gi_list):
                        if gi["type"] != "tiroir":
                            continue
                        if i == topmost:
                            gi["nb_bas"] = gi["nb"] - 1
                            gi["h_bas"] = gi["h_min"] + ep_extra
                            gi["h_haut"] = gi["h_min"]
                        else:
                            gi["nb_bas"] = gi["nb"]
                            gi["h_bas"] = gi["h_min"] + ep_extra
                            gi["h_haut"] = gi["h_min"] + ep_extra
                else:
                    for gi in gi_list:
                        if gi["type"] == "tiroir":
                            gi["nb_bas"] = gi["nb"]
                            gi["h_bas"] = gi["h_min"]
                            gi["h_haut"] = gi["h_min"]
            else:
                for gi in gi_list:
                    if gi["type"] == "tiroir":
                        gi["nb_bas"] = gi["nb"]
                        gi["h_bas"] = gi["h_min"]
                        gi["h_haut"] = gi["h_min"]

            # Dessiner
            z_cur = z_facade_bas
            for gi_idx, (g, gi) in enumerate(zip(groupes, gi_list)):
                if gi_idx > 0:
                    z_cur += jeu_entre_g

                if g["type"] == "tiroir":
                    nb_bas = gi.get("nb_bas", gi["nb"])
                    h_bas = gi.get("h_bas", gi["h_min"])
                    h_haut = gi.get("h_haut", gi["h_min"])
                    h_code = g.get("hauteur") or hauteur_defaut

                    z_t = z_cur
                    for t_idx in range(gi["nb"]):
                        h_t = h_bas if t_idx < nb_bas else h_haut
                        rects.append(Rect(
                            -ep_f, z_t, ep_f, h_t,
                            couleur_facade,
                            f"Tiroir {h_code}{t_idx+1} (coupe)", "tiroir"
                        ))
                        z_t += h_t + jeu_entre_t
                    z_cur = z_t - jeu_entre_t  # retirer le dernier jeu

                elif g["type"] == "porte":
                    total_t = sum(
                        gi2["nb"] * gi2["h_bas"]
                        + max(0, gi2["nb"] - gi2.get("nb_bas", gi2["nb"]))
                        * gi2.get("h_haut", gi2["h_min"])
                        + max(0, gi2["nb"] - 1) * jeu_entre_t
                        for gi2 in gi_list if gi2["type"] == "tiroir"
                    )
                    h_porte = h_facade_zone - total_t - nb_gaps * jeu_entre_g
                    rects.append(Rect(
                        -ep_f, z_cur, ep_f, h_porte,
                        couleur_facade, "Porte (coupe)", "porte"
                    ))
                    z_cur += h_porte

        elif facade_type == "portes":
            rects.append(Rect(
                -ep_f, z_facade_bas, ep_f, h_facade_zone,
                couleur_facade, "Porte (coupe)", "porte"
            ))

        elif facade_type == "tiroirs":
            nb_tiroirs = facade_repr.get("nb_tiroirs", 0)
            if nb_tiroirs > 0:
                jeu_entre_t = config["tiroir"]["jeu_entre"]
                h_facade_tiroir = ((h_facade_zone - (nb_tiroirs - 1)
                                    * jeu_entre_t) / nb_tiroirs)
                for t_idx in range(nb_tiroirs):
                    z_t = z_facade_bas + t_idx * (h_facade_tiroir
                                                  + jeu_entre_t)
                    rects.append(Rect(
                        -ep_f, z_t, ep_f, h_facade_tiroir,
                        couleur_facade,
                        f"Tiroir T{t_idx+1} (coupe)", "tiroir"
                    ))

    # --- Cotations ---
    rects.append(Rect(0, -50, P, 2, "#333333", f"{P:.0f}", "cotation"))
    rects.append(Rect(-50, 0, 2, H, "#333333", f"{H:.0f}", "cotation"))

    return rects
