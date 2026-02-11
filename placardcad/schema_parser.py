"""Parser de schema compact pour amenagement de placard.

Ce module fournit les fonctions pour analyser un schema compact textuel
(dessin ASCII) decrivant la configuration d'un placard, et le convertir
en un dictionnaire de configuration exploitable par le constructeur.

Syntaxe du schema::

    *-----------*-----------*
    |__________|__________|
    |__________|__________|
    500         800

Symboles:
    - ``-`` : rayon haut (1ere ligne uniquement)
    - ``_`` : rayon dans un compartiment
    - ``*`` : tasseau sous ce rayon a cette position
    - ``|`` : cremaillere encastree (+ panneau mur si bord exterieur)
    - ``/`` : cremaillere en applique
    - espace : rien / mur brut
    - Derniere ligne (chiffres) : largeurs en mm par compartiment
"""

import re


def parser_schema(schema_text: str) -> dict:
    """Parse un schema compact et retourne les elements d'amenagement.

    Analyse le texte du schema ligne par ligne pour en extraire la topologie
    du placard : rayon haut, compartiments, separations, cremailleres,
    tasseaux et largeurs.

    Args:
        schema_text: Texte du schema compact (dessin ASCII multi-lignes).

    Returns:
        Dictionnaire contenant les cles suivantes :
            - ``rayon_haut`` (bool) : presence d'un rayon haut.
            - ``nombre_compartiments`` (int) : nombre de compartiments detectes.
            - ``mode_largeur`` (str) : ``"egal"``, ``"dimensions"`` ou ``"mixte"``.
            - ``largeurs_compartiments`` (list) : largeurs specifiees en mm ou liste vide.
            - ``separations`` (list[dict]) : liste des separations avec leur mode.
            - ``compartiments`` (list[dict]) : details de chaque compartiment
              (rayons, cremailleres, tasseaux, panneaux mur).

    Raises:
        ValueError: Si le schema contient moins de 2 lignes ou moins de
            2 separateurs verticaux.
    """
    lines = schema_text.strip().split("\n")
    if len(lines) < 2:
        raise ValueError("Le schema doit contenir au moins 2 lignes")

    # Detecter si la derniere ligne contient des largeurs
    last_line = lines[-1].strip()
    has_widths = any(c.isdigit() for c in last_line)

    content_lines = lines[:-1] if has_widths else lines[:]
    width_line = lines[-1] if has_widths else None

    # La premiere ligne est le rayon haut si elle contient -
    first_line = content_lines[0]
    has_rayon_haut = "-" in first_line or "_" in first_line

    if has_rayon_haut:
        rayon_haut_line = first_line
        rayon_lines = content_lines[1:]
    else:
        rayon_haut_line = None
        rayon_lines = content_lines[:]

    # --- Trouver les positions des separateurs verticaux ---
    all_positions = set()
    for line in content_lines:
        for i, c in enumerate(line):
            if c in ("|", "/", "*"):
                all_positions.add(i)

    hard_sep_positions = set()
    star_only_positions = set()
    for pos in all_positions:
        has_hard = False
        for line in content_lines:
            if pos < len(line) and line[pos] in ("|", "/"):
                has_hard = True
                break
        if has_hard:
            hard_sep_positions.add(pos)
        else:
            star_only_positions.add(pos)

    all_sep = sorted(hard_sep_positions | star_only_positions)

    if not all_sep:
        raise ValueError("Le schema doit contenir au moins 2 separateurs verticaux (| ou /)")

    # Fusionner les positions adjacentes en clusters
    clusters = [[all_sep[0]]]
    for pos in all_sep[1:]:
        if pos - clusters[-1][-1] <= 3:
            clusters[-1].append(pos)
        else:
            clusters.append([pos])

    sep_positions = []
    for cluster in clusters:
        ref = None
        for p in cluster:
            if p in hard_sep_positions:
                ref = p
                break
        if ref is None:
            ref = cluster[0]
        sep_positions.append(ref)

    if len(sep_positions) < 2:
        raise ValueError("Le schema doit contenir au moins 2 separateurs verticaux (| ou /)")

    # Map: position -> contient un * (tasseau) ?
    cluster_has_star = {}
    for i, cluster in enumerate(clusters):
        has_star = False
        for p in cluster:
            if p in star_only_positions:
                has_star = True
                break
            for line in content_lines:
                if p < len(line) and line[p] == "*":
                    has_star = True
                    break
            if has_star:
                break
        cluster_has_star[sep_positions[i]] = has_star

    nb_separateurs = len(sep_positions)
    nb_compartiments = nb_separateurs - 1

    # --- Analyser le rayon haut ---
    tasseau_rh = {}
    if rayon_haut_line:
        for pos in sep_positions:
            has_star = False
            for delta in [0, -1, 1, -2, 2]:
                p = pos + delta
                if 0 <= p < len(rayon_haut_line) and rayon_haut_line[p] == "*":
                    has_star = True
                    break
            tasseau_rh[pos] = has_star

    # --- Determiner le type de cremaillere par separateur ---
    sep_types = {}
    for pos in sep_positions:
        crem_type = None
        for line in content_lines:
            for delta in [0, -1, 1, -2, 2]:
                p = pos + delta
                if 0 <= p < len(line):
                    c = line[p]
                    if c == "|":
                        crem_type = "encastree"
                        break
                    elif c == "/":
                        crem_type = "applique"
                        break
            if crem_type:
                break
        sep_types[pos] = crem_type

    compartiments = []
    for comp_idx in range(nb_compartiments):
        pos_gauche = sep_positions[comp_idx]
        pos_droite = sep_positions[comp_idx + 1]

        type_crem_g = sep_types[pos_gauche]
        type_crem_d = sep_types[pos_droite]

        nb_rayons = 0
        tasseau_rayons_g = False
        tasseau_rayons_d = False

        for line in rayon_lines:
            zone = ""
            if pos_droite < len(line):
                zone = line[pos_gauche:pos_droite + 1]
            elif pos_gauche < len(line):
                zone = line[pos_gauche:]

            inner_zone = zone[1:-1] if len(zone) > 2 else zone[1:] if len(zone) > 1 else ""
            if "_" in inner_zone:
                nb_rayons += 1
                if pos_gauche < len(line) and line[pos_gauche] == "*":
                    tasseau_rayons_g = True
                if pos_droite < len(line) and line[pos_droite] == "*":
                    tasseau_rayons_d = True

        panneau_mur_g = (comp_idx == 0 and type_crem_g == "encastree")
        panneau_mur_d = (comp_idx == nb_compartiments - 1 and type_crem_d == "encastree")

        trh_gauche = tasseau_rh.get(pos_gauche, False) if has_rayon_haut else False
        trh_droite = tasseau_rh.get(pos_droite, False) if has_rayon_haut else False

        compartiments.append({
            "nom": f"Compartiment {comp_idx + 1}",
            "rayons": nb_rayons,
            "type_crem_gauche": type_crem_g,
            "type_crem_droite": type_crem_d,
            "panneau_mur_gauche": panneau_mur_g,
            "panneau_mur_droite": panneau_mur_d,
            "tasseau_rayon_haut_gauche": trh_gauche,
            "tasseau_rayon_haut_droite": trh_droite,
            "tasseau_rayons_gauche": tasseau_rayons_g,
            "tasseau_rayons_droite": tasseau_rayons_d,
        })

    # --- Parser les largeurs ---
    mode_largeur = "egal"
    largeurs = []

    if width_line:
        parts = [None] * nb_compartiments

        # Trouver chaque nombre et l'assigner au compartiment
        # dont la zone contient le centre du nombre
        for match in re.finditer(r'\d+', width_line):
            center = (match.start() + match.end()) / 2
            for comp_idx in range(nb_compartiments):
                pos_g = sep_positions[comp_idx]
                pos_d = sep_positions[comp_idx + 1]
                if pos_g < center < pos_d:
                    parts[comp_idx] = int(match.group())
                    break

        if any(p is not None for p in parts):
            if all(p is not None for p in parts):
                mode_largeur = "dimensions"
                largeurs = parts
            else:
                mode_largeur = "mixte"
                largeurs = parts

    # --- Separations ---
    separations = []
    for sep_idx in range(nb_compartiments - 1):
        pos = sep_positions[sep_idx + 1]
        # Si le separateur est present sur la ligne rayon haut (| ou /),
        # la separation est sur toute la hauteur
        mode = "sous_rayon"
        if rayon_haut_line:
            for delta in [0, -1, 1, -2, 2]:
                p = pos + delta
                if 0 <= p < len(rayon_haut_line) and rayon_haut_line[p] in ("|", "/"):
                    mode = "toute_hauteur"
                    break
        separations.append({"mode": mode})

    return {
        "rayon_haut": has_rayon_haut,
        "nombre_compartiments": nb_compartiments,
        "mode_largeur": mode_largeur,
        "largeurs_compartiments": largeurs,
        "separations": separations,
        "compartiments": compartiments,
    }


def schema_vers_config(schema_text: str, params_generaux: dict | None = None) -> dict:
    """Combine un schema compact avec des parametres generaux pour produire une configuration complete.

    Parse le schema compact, puis fusionne le resultat avec des valeurs
    par defaut et les parametres generaux fournis. Le dictionnaire resultant
    est directement exploitable par le constructeur (``generer_geometrie_2d``).

    Args:
        schema_text: Texte du schema compact (dessin ASCII multi-lignes).
        params_generaux: Parametres optionnels surchargeant les valeurs par
            defaut (dimensions, panneaux, cremailleres, tasseaux, etc.).
            Les sous-dictionnaires sont fusionnes recursivement.

    Returns:
        Dictionnaire de configuration complet contenant toutes les cles
        necessaires au constructeur : dimensions globales, topologie du
        schema, parametres de panneaux, cremailleres, tasseaux, murs
        et options d'export.

    Raises:
        ValueError: Si le schema est invalide (propage depuis ``parser_schema``).
    """
    parsed = parser_schema(schema_text)

    config = {
        "hauteur": 2500,
        "largeur": 3000,
        "profondeur": 600,
        "rayon_haut": parsed["rayon_haut"],
        "rayon_haut_position": 300,
        "mode_largeur": parsed["mode_largeur"],
        "largeurs_compartiments": parsed["largeurs_compartiments"],
        "nombre_compartiments": parsed["nombre_compartiments"],
        "separations": parsed["separations"],
        "compartiments": parsed["compartiments"],
        "panneau_separation": {
            "epaisseur": 19,
            "couleur_fab": "Chene clair",
            "couleur_rgb": (0.82, 0.71, 0.55),
            "chant_epaisseur": 1,
            "chant_couleur_fab": "Chene clair",
            "chant_couleur_rgb": (0.85, 0.74, 0.58),
        },
        "panneau_rayon": {
            "epaisseur": 19,
            "couleur_fab": "Chene clair",
            "couleur_rgb": (0.82, 0.71, 0.55),
            "chant_epaisseur": 1,
            "chant_couleur_fab": "Chene clair",
            "chant_couleur_rgb": (0.85, 0.74, 0.58),
            "retrait_avant": 0,
            "retrait_arriere": 0,
        },
        "panneau_rayon_haut": {
            "epaisseur": 22,
            "couleur_fab": "Chene clair",
            "couleur_rgb": (0.82, 0.71, 0.55),
            "chant_epaisseur": 1,
            "chant_couleur_fab": "Chene clair",
            "chant_couleur_rgb": (0.85, 0.74, 0.58),
            "retrait_avant": 0,
            "retrait_arriere": 0,
        },
        "crem_encastree": {
            "largeur": 16,
            "epaisseur": 5,
            "saillie": 0,
            "jeu_rayon": 2,
            "pas": 32,
            "retrait_avant": 80,
            "retrait_arriere": 80,
            "couleur_rgb": (0.6, 0.6, 0.6),
        },
        "crem_applique": {
            "largeur": 25,
            "epaisseur_saillie": 12,
            "jeu_rayon": 2,
            "pas": 32,
            "retrait_avant": 80,
            "retrait_arriere": 80,
            "couleur_rgb": (0.6, 0.6, 0.6),
        },
        "tasseau": {
            "section_h": 30,
            "section_l": 30,
            "retrait_avant": 20,
            "couleur_rgb": (0.85, 0.75, 0.55),
            "biseau_longueur": 15,
        },
        "panneau_mur": {
            "epaisseur": 19,
            "couleur_fab": "Chene clair",
            "couleur_rgb": (0.82, 0.71, 0.55),
            "chant_epaisseur": 1,
            "chant_couleur_fab": "Chene clair",
            "chant_couleur_rgb": (0.85, 0.74, 0.58),
        },
        "afficher_murs": True,
        "mur_epaisseur": 50,
        "mur_couleur_rgb": (0.85, 0.85, 0.82),
        "mur_transparence": 85,
        "export_fiche": True,
        "dossier_export": "",
        "debit": {
            "panneau_longueur": 2800,
            "panneau_largeur": 2070,
            "trait_scie": 4.0,
            "surcote": 2.0,
            "delignage": 10.0,
            "sens_fil": True,
        },
    }

    if params_generaux:
        for key, value in params_generaux.items():
            if isinstance(value, dict) and key in config and isinstance(config[key], dict):
                config[key].update(value)
            else:
                config[key] = value

    return config
