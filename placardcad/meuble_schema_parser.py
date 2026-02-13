"""Parser de schema compact pour meuble parametrique.

Syntaxe du schema meuble::

    #MEUBLE
    | PP | TTT |
    | -- |     |
    | -- |     |
      600  400

Symboles:
    - ``#MEUBLE`` : en-tete obligatoire (1ere ligne)
    - ``|`` : flanc (bord) ou separation verticale
    - ``P`` : porte (PP = 2 portes doubles, PG = gauche, PD = droite)
    - ``T`` : tiroir (TT = 2 tiroirs, TTT = 3, etc.)
    - ``N`` : niche (pas de facade)
    - ``--`` ou ``==`` : etagere dans un compartiment
    - Derniere ligne (chiffres) : largeurs en mm par compartiment
"""

import re


def est_schema_meuble(schema_text: str) -> bool:
    """Detecte si un schema est de type meuble (commence par #MEUBLE).

    Args:
        schema_text: Texte du schema a tester.

    Returns:
        True si le schema commence par #MEUBLE.
    """
    first_line = schema_text.strip().split("\n")[0].strip()
    return first_line.upper() == "#MEUBLE"


def _parse_facade(zone: str) -> dict:
    """Parse la specification de facade d'un compartiment.

    Args:
        zone: Texte entre separateurs sur la ligne de facade.
            Ex: 'PP', '3T', 'PG', 'N', '2T+P'.

    Returns:
        Dictionnaire avec les cles:
            - type: 'portes', 'tiroirs', 'niche', 'mixte'
            - nb_portes: nombre de portes
            - nb_tiroirs: nombre de tiroirs
            - ouverture: 'gauche', 'droite', 'double' ou None
    """
    zone = zone.strip().upper()
    if not zone or zone == "N":
        return {"type": "niche", "nb_portes": 0, "nb_tiroirs": 0,
                "ouverture": None}

    # Mixte: combinaison T+P (ex: "2T+P", "3T+PD")
    if "+" in zone:
        parts = zone.split("+")
        result = {"type": "mixte", "nb_portes": 0, "nb_tiroirs": 0,
                  "ouverture": None}
        for part in parts:
            sub = _parse_facade(part.strip())
            result["nb_portes"] += sub["nb_portes"]
            result["nb_tiroirs"] += sub["nb_tiroirs"]
            if sub["ouverture"]:
                result["ouverture"] = sub["ouverture"]
        return result

    # Tiroirs: T, TT, TTT, 2T, 3T, etc.
    m_tiroir = re.match(r'^(\d*)T+$', zone)
    if m_tiroir:
        if m_tiroir.group(1):
            nb = int(m_tiroir.group(1))
        else:
            nb = zone.count("T")
        return {"type": "tiroirs", "nb_portes": 0, "nb_tiroirs": nb,
                "ouverture": None}

    # Portes: P, PG, PD, PP, PPP, 2P, 3P, etc.
    # PP ou PPP... = compter les P
    if re.match(r'^P{2,}$', zone):
        nb = len(zone)
        return {"type": "portes", "nb_portes": nb, "nb_tiroirs": 0,
                "ouverture": "double"}

    m_porte = re.match(r'^(\d*)P([GD]?)$', zone)
    if m_porte:
        nb = int(m_porte.group(1)) if m_porte.group(1) else 1
        ouv = "gauche"
        if m_porte.group(2) == "D":
            ouv = "droite"
        if nb >= 2:
            ouv = "double"
        return {"type": "portes", "nb_portes": nb, "nb_tiroirs": 0,
                "ouverture": ouv}

    # Fallback: niche
    return {"type": "niche", "nb_portes": 0, "nb_tiroirs": 0,
            "ouverture": None}


def parser_schema_meuble(schema_text: str) -> dict:
    """Parse un schema compact de meuble et retourne les elements.

    Analyse le texte du schema ligne par ligne pour en extraire la topologie
    du meuble: compartiments, facades (portes/tiroirs/niches), etageres et
    largeurs.

    Args:
        schema_text: Texte du schema compact commencant par ``#MEUBLE``.

    Returns:
        Dictionnaire contenant:
            - ``nombre_compartiments`` (int): nombre de compartiments.
            - ``compartiments`` (list[dict]): details par compartiment
              avec cles ``facade`` et ``etageres``.
            - ``mode_largeur`` (str): ``"egal"`` ou ``"dimensions"`` ou ``"mixte"``.
            - ``largeurs_compartiments`` (list): largeurs en mm ou liste vide.

    Raises:
        ValueError: Si le schema est invalide.
    """
    lines = schema_text.strip().split("\n")

    # Retirer l'en-tete #MEUBLE
    if lines[0].strip().upper() == "#MEUBLE":
        lines = lines[1:]

    if len(lines) < 1:
        raise ValueError("Le schema meuble doit contenir au moins 1 ligne de contenu")

    # Detecter la ligne de largeurs (derniere ligne avec des chiffres)
    last_line = lines[-1].strip()
    has_widths = bool(re.search(r'\d', last_line)) and '|' not in last_line

    content_lines = lines[:-1] if has_widths else lines[:]
    width_line = lines[-1] if has_widths else None

    if not content_lines:
        raise ValueError("Le schema meuble doit contenir au moins 1 ligne de contenu")

    # --- Trouver les positions des separateurs | ---
    all_positions = set()
    for line in content_lines:
        for i, c in enumerate(line):
            if c == '|':
                all_positions.add(i)

    if len(all_positions) < 2:
        raise ValueError("Le schema meuble doit contenir au moins 2 separateurs |")

    sep_positions = sorted(all_positions)

    # Fusionner les positions adjacentes en clusters
    clusters = [[sep_positions[0]]]
    for pos in sep_positions[1:]:
        if pos - clusters[-1][-1] <= 2:
            clusters[-1].append(pos)
        else:
            clusters.append([pos])

    sep_positions = [cl[0] for cl in clusters]

    if len(sep_positions) < 2:
        raise ValueError("Le schema meuble doit contenir au moins 2 separateurs |")

    nb_comp = len(sep_positions) - 1

    # --- Premiere ligne de contenu = facades ---
    facade_line = content_lines[0]
    shelf_lines = content_lines[1:]

    compartiments = []
    for comp_idx in range(nb_comp):
        pos_g = sep_positions[comp_idx]
        pos_d = sep_positions[comp_idx + 1]

        # Extraire la zone facade
        zone = ""
        if pos_d < len(facade_line):
            zone = facade_line[pos_g + 1:pos_d]
        elif pos_g + 1 < len(facade_line):
            zone = facade_line[pos_g + 1:]
        facade = _parse_facade(zone)

        # Compter les etageres
        nb_etageres = 0
        for line in shelf_lines:
            inner = ""
            if pos_d < len(line):
                inner = line[pos_g + 1:pos_d]
            elif pos_g + 1 < len(line):
                inner = line[pos_g + 1:]
            if '--' in inner or '==' in inner or '__' in inner:
                nb_etageres += 1

        compartiments.append({
            "facade": facade,
            "etageres": nb_etageres,
        })

    # --- Parser les largeurs ---
    mode_largeur = "egal"
    largeurs: list = []

    if width_line:
        parts: list[int | None] = [None] * nb_comp
        for match in re.finditer(r'\d+', width_line):
            center = (match.start() + match.end()) / 2
            for comp_idx in range(nb_comp):
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

    return {
        "nombre_compartiments": nb_comp,
        "compartiments": compartiments,
        "mode_largeur": mode_largeur,
        "largeurs_compartiments": largeurs,
    }


def meuble_schema_vers_config(schema_text: str,
                               params: dict | None = None) -> dict:
    """Combine un schema meuble avec des parametres pour produire une config complete.

    Args:
        schema_text: Texte du schema compact (commencant par ``#MEUBLE``).
        params: Parametres optionnels surchargeant les valeurs par defaut.

    Returns:
        Dictionnaire de configuration complet pour le builder meuble.

    Raises:
        ValueError: Si le schema est invalide.
    """
    parsed = parser_schema_meuble(schema_text)

    config = {
        # Dimensions globales
        "hauteur": 720,
        "profondeur": 560,
        "largeur": 1200,
        "epaisseur": 19,
        "hauteur_plinthe": 100,
        "epaisseur_facade": 19,

        # Assemblage
        "assemblage": "dessus_entre",
        "pose": "applique",

        # Fond
        "fond": {
            "type": "rainure",
            "epaisseur": 3,
            "profondeur_rainure": 8,
            "distance_chant": 10,
        },

        # Plinthe
        "plinthe": {
            "type": "avant",
            "retrait": 30,
            "epaisseur": 16,
        },

        # Tiroirs LEGRABOX
        "tiroir": {
            "hauteur": "M",
            "jeu_lateral": 2,
            "jeu_entre": 4,
        },

        # Portes
        "porte": {
            "jeu_haut": 4,
            "jeu_bas": 4,
            "jeu_lateral": 2,
            "jeu_entre": 3,
        },

        # Etageres
        "etagere": {
            "jeu_lateral": 1,
            "retrait_avant": 20,
        },

        # Separations
        "separation": {
            "epaisseur": 19,
            "retrait_avant": 0,
            "retrait_arriere": 0,
        },

        # Panneaux structure
        "panneau": {
            "couleur_fab": "Melamine chene",
            "couleur_rgb": [0.82, 0.71, 0.55],
            "chant_epaisseur": 1,
            "chant_couleur_fab": "Chene clair",
        },

        # Facades
        "facade": {
            "couleur_fab": "Melamine blanc",
            "couleur_rgb": [0.92, 0.92, 0.92],
        },

        # Cremailleres
        "cremaillere": {
            "largeur": 16,
            "profondeur": 7,
            "distance_avant": 37,
            "distance_arriere": 37,
        },

        # Donnees du schema
        "nombre_compartiments": parsed["nombre_compartiments"],
        "compartiments": parsed["compartiments"],
        "mode_largeur": parsed["mode_largeur"],
        "largeurs_compartiments": parsed["largeurs_compartiments"],
    }

    if params:
        for key, value in params.items():
            if isinstance(value, dict) and key in config and isinstance(config[key], dict):
                config[key].update(value)
            else:
                config[key] = value

    return config
