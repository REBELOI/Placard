"""
Parser de schéma compact pour aménagement de placard.

Syntaxe du schéma:
    *-----------*-----------*
    *|__________|/_________ |
    *|__________|/_________ |
    *|__________|/_________ |
     |__________|/          |
     |          |           |
    500                   600

Symboles:
    Première ligne (rayon haut):
        -   rayon haut (présent)
        *   tasseau sous le rayon haut à cette position
        |   séparateur avec crémaillère encastrée
        /   séparateur avec crémaillère en applique
        (espace) pas de séparateur

    Lignes de rayons:
        _   rayon dans ce compartiment
        *   tasseau sous ce rayon (en début ou fin de zone rayon)
        |   crémaillère encastrée (+ panneau mur si en bord extérieur)
        /   crémaillère en applique
        (espace) rien (mur brut)

    Dernière ligne (largeurs):
        nombre  largeur en mm du compartiment
        (vide)  répartition automatique (mode "egal")

Exemples:
    CONFIG_EXEMPLE_3 (3 compartiments, crém. encastrées, tasseaux rayon haut):
        *-----------*-----------*
        *|__________|__________|*
        *|__________|__________|*
        *|__________|__________|*
         |__________|__________|
         |          |           |

    2 compartiments, gauche applique, droite encastrée:
        /----------*
        /__________|
        /__________|
        /__________|
        /          |
       500       800
"""


def parser_schema(schema_text):
    """
    Parse un schéma compact et retourne les éléments d'aménagement.

    Retourne un dict:
    {
        "rayon_haut": bool,
        "nombre_compartiments": int,
        "mode_largeur": "egal" | "dimensions",
        "largeurs_compartiments": list,
        "separations": [{"mode": "sous_rayon"}, ...],
        "compartiments": [
            {
                "nom": str,
                "rayons": int,
                "type_crem_gauche": "encastree" | "applique" | None,
                "type_crem_droite": "encastree" | "applique" | None,
                "panneau_mur_gauche": bool,
                "panneau_mur_droite": bool,
                "tasseau_rayon_haut_gauche": bool,
                "tasseau_rayon_haut_droite": bool,
                "tasseau_rayons_gauche": bool,
                "tasseau_rayons_droite": bool,
            }, ...
        ]
    }
    """
    lines = schema_text.strip().split("\n")
    if len(lines) < 2:
        raise ValueError("Le schéma doit contenir au moins 2 lignes")

    # --- 1. Identifier les colonnes de séparateurs ---
    # Trouver toutes les positions de séparateurs (|, /, *) sur toutes les lignes
    # sauf la dernière (largeurs)
    
    # D'abord, détecter si la dernière ligne contient des largeurs
    last_line = lines[-1].strip()
    has_widths = any(c.isdigit() for c in last_line)
    
    content_lines = lines[:-1] if has_widths else lines[:]
    width_line = lines[-1] if has_widths else None
    
    # La première ligne est le rayon haut (si contient -)
    first_line = content_lines[0]
    has_rayon_haut = "-" in first_line or "_" in first_line
    
    if has_rayon_haut:
        rayon_haut_line = first_line
        rayon_lines = content_lines[1:]
    else:
        rayon_haut_line = None
        rayon_lines = content_lines[:]
    
    # --- 2. Trouver les positions des séparateurs verticaux ---
    # | et / sont des séparateurs. * est un tasseau PLUS séparateur.
    # On collecte toutes les positions qui ont |, / ou * et on les regroupe.
    # Une position est un séparateur si elle a au moins un |, / ou * sur l'ensemble des lignes.
    
    all_positions = set()
    for line in content_lines:
        for i, c in enumerate(line):
            if c in ("|", "/", "*"):
                all_positions.add(i)
    
    # Filtrer : une position doit avoir un | ou / sur au moins une ligne
    # OU avoir un * ET être cohérente (voisine d'autres séparateurs)
    # Approche simple : on prend toutes les positions avec |, /, ou *
    # MAIS on exclut les * isolés qui ne sont pas alignés avec des |//
    
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
    
    # Les * isolés sont des tasseaux aux positions de séparateurs.
    # On les fusionne avec la position de séparateur dur la plus proche.
    # Puis on regroupe les positions adjacentes en clusters.
    
    all_sep = sorted(hard_sep_positions | star_only_positions)
    
    # Fusionner les positions adjacentes (±1) en clusters
    if not all_sep:
        raise ValueError("Le schéma doit contenir au moins 2 séparateurs verticaux (| ou /)")
    
    clusters = [[all_sep[0]]]
    for pos in all_sep[1:]:
        if pos - clusters[-1][-1] <= 3:
            clusters[-1].append(pos)
        else:
            clusters.append([pos])
    
    # Chaque cluster = 1 séparateur logique.
    # On prend la position du | ou / comme position de référence, sinon la première.
    sep_positions = []
    for cluster in clusters:
        # Préférer la position d'un séparateur dur
        ref = None
        for p in cluster:
            if p in hard_sep_positions:
                ref = p
                break
        if ref is None:
            ref = cluster[0]
        sep_positions.append(ref)
    
    if len(sep_positions) < 2:
        raise ValueError("Le schéma doit contenir au moins 2 séparateurs verticaux (| ou /)")
    
    # Map: position de cluster -> contient un * (tasseau)?
    cluster_has_star = {}
    for i, cluster in enumerate(clusters):
        has_star = False
        for p in cluster:
            if p in star_only_positions:
                has_star = True
                break
            # Vérifier aussi si * apparaît à cette position sur une ligne
            for line in content_lines:
                if p < len(line) and line[p] == "*":
                    has_star = True
                    break
            if has_star:
                break
        cluster_has_star[sep_positions[i]] = has_star
    
    if len(sep_positions) < 2:
        raise ValueError("Le schéma doit contenir au moins 2 séparateurs verticaux (| ou /)")
    
    # Les séparateurs délimitent les compartiments
    # Le premier et le dernier sont les bords (mur gauche / mur droit)
    # Les intermédiaires sont des séparations
    nb_separateurs = len(sep_positions)
    nb_compartiments = nb_separateurs - 1
    
    # --- 3. Analyser le rayon haut ---
    tasseau_rh = {}  # par position de séparateur: True/False
    if rayon_haut_line:
        for pos in sep_positions:
            # Vérifier si * sur la ligne rayon haut à cette position ou ±1
            has_star = False
            for delta in [0, -1, 1, -2, 2]:
                p = pos + delta
                if 0 <= p < len(rayon_haut_line) and rayon_haut_line[p] == "*":
                    has_star = True
                    break
            tasseau_rh[pos] = has_star
    
    # --- 4. Déterminer le type de crémaillère par séparateur ---
    # Pour chaque séparateur, déterminer le type de crémaillère (|, /, ou espace)
    sep_types = {}  # pos -> "encastree" | "applique" | None
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
        
        # Type de crémaillère: déjà déterminé
        type_crem_g = sep_types[pos_gauche]
        type_crem_d = sep_types[pos_droite]
        
        # Compter les rayons et détecter tasseaux rayons
        nb_rayons = 0
        tasseau_rayons_g = False
        tasseau_rayons_d = False
        
        for line in rayon_lines:
            # Extraire la zone entre les 2 séparateurs
            zone = ""
            if pos_droite < len(line):
                zone = line[pos_gauche:pos_droite + 1]
            elif pos_gauche < len(line):
                zone = line[pos_gauche:]
            
            # Un rayon existe si _ est présent dans la zone intérieure
            inner_zone = zone[1:-1] if len(zone) > 2 else zone[1:] if len(zone) > 1 else ""
            if "_" in inner_zone:
                nb_rayons += 1
                
                # Tasseau gauche sur les rayons: * à la position du séparateur gauche
                if pos_gauche < len(line) and line[pos_gauche] == "*":
                    tasseau_rayons_g = True
                
                # Tasseau droite sur les rayons
                if pos_droite < len(line) and line[pos_droite] == "*":
                    tasseau_rayons_d = True
        
        # Panneau mur : si bord extérieur avec crémaillère encastrée
        panneau_mur_g = (comp_idx == 0 and type_crem_g == "encastree")
        panneau_mur_d = (comp_idx == nb_compartiments - 1 and type_crem_d == "encastree")
        
        # Tasseaux rayon haut
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
    
    # --- 5. Parser les largeurs ---
    mode_largeur = "egal"
    largeurs = []
    
    if width_line:
        # Extraire les nombres entre les séparateurs
        parts = []
        for comp_idx in range(nb_compartiments):
            pos_g = sep_positions[comp_idx]
            pos_d = sep_positions[comp_idx + 1]
            # Prendre la zone complète entre les 2 positions
            zone = width_line[pos_g:pos_d + 1] if pos_d < len(width_line) else width_line[pos_g:]
            zone = zone.strip()
            # Extraire le nombre (tous les chiffres consécutifs)
            import re
            nums = re.findall(r'\d+', zone)
            if nums:
                parts.append(int(nums[0]))
            else:
                parts.append(None)
        
        if any(p is not None for p in parts):
            if all(p is not None for p in parts):
                # Toutes les largeurs spécifiées
                mode_largeur = "dimensions"
                largeurs = parts
            else:
                # Mode mixte : certaines spécifiées, les autres None (= auto)
                mode_largeur = "mixte"
                largeurs = parts  # contient des int et des None
    
    # --- 6. Séparations ---
    separations = [{"mode": "sous_rayon"} for _ in range(nb_compartiments - 1)]
    
    return {
        "rayon_haut": has_rayon_haut,
        "nombre_compartiments": nb_compartiments,
        "mode_largeur": mode_largeur,
        "largeurs_compartiments": largeurs,
        "separations": separations,
        "compartiments": compartiments,
    }


def schema_vers_config(schema_text, params_generaux=None):
    """
    Combine un schéma compact avec des paramètres généraux pour produire
    un CONFIG complet prêt à passer à construire_placard().
    
    params_generaux : dict optionnel avec les paramètres non couverts par le schéma
    (dimensions, couleurs, épaisseurs, etc.)
    """
    parsed = parser_schema(schema_text)
    
    # Paramètres par défaut
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
            "couleur_fab": "Chêne clair",
            "couleur_rgb": (0.82, 0.71, 0.55),
            "chant_epaisseur": 1,
            "chant_couleur_fab": "Chêne clair",
            "chant_couleur_rgb": (0.85, 0.74, 0.58),
        },
        "panneau_rayon": {
            "epaisseur": 19,
            "couleur_fab": "Chêne clair",
            "couleur_rgb": (0.82, 0.71, 0.55),
            "chant_epaisseur": 1,
            "chant_couleur_fab": "Chêne clair",
            "chant_couleur_rgb": (0.85, 0.74, 0.58),
        },
        "panneau_rayon_haut": {
            "epaisseur": 22,
            "couleur_fab": "Chêne clair",
            "couleur_rgb": (0.82, 0.71, 0.55),
            "chant_epaisseur": 1,
            "chant_couleur_fab": "Chêne clair",
            "chant_couleur_rgb": (0.85, 0.74, 0.58),
        },
        "crem_encastree": {
            "largeur": 16,
            "epaisseur": 5,
            "saillie": 0,
            "jeu_rayon": 2,
            "retrait_avant": 80,
            "retrait_arriere": 80,
            "couleur_rgb": (0.6, 0.6, 0.6),
        },
        "crem_applique": {
            "largeur": 25,
            "epaisseur_saillie": 12,
            "jeu_rayon": 2,
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
            "couleur_fab": "Chêne clair",
            "couleur_rgb": (0.82, 0.71, 0.55),
            "chant_epaisseur": 1,
            "chant_couleur_fab": "Chêne clair",
            "chant_couleur_rgb": (0.85, 0.74, 0.58),
        },
        "afficher_murs": True,
        "mur_epaisseur": 50,
        "mur_couleur_rgb": (0.85, 0.85, 0.82),
        "mur_transparence": 85,
        "export_fiche": True,
        "dossier_export": "",
    }
    
    # Fusionner les paramètres généraux (écrasent les défauts)
    if params_generaux:
        for key, value in params_generaux.items():
            if isinstance(value, dict) and key in config and isinstance(config[key], dict):
                config[key].update(value)
            else:
                config[key] = value
    
    return config


# ===========================================================================
#  TESTS
# ===========================================================================
