"""
Constructeur de placard - Calculs geometriques et fiche de fabrication.

Ce module fournit:
- Le calcul des dimensions de chaque element du placard
- La generation de la geometrie 2D (vue de face) pour le viewer et le PDF
- La fiche de fabrication (liste des pieces et quincaillerie)
- L'integration FreeCAD optionnelle pour la 3D
"""

from datetime import datetime


class PieceInfo:
    """Informations d'une piece pour la fiche de fabrication."""

    def __init__(self, nom: str, longueur: float, largeur: float, epaisseur: float,
                 materiau: str = "Agglomere melamine", couleur_fab: str = "",
                 chant_desc: str = "", quantite: int = 1, notes: str = "",
                 reference: str = ""):
        self.nom = nom
        self.longueur = longueur
        self.largeur = largeur
        self.epaisseur = epaisseur
        self.materiau = materiau
        self.couleur_fab = couleur_fab
        self.chant_desc = chant_desc
        self.quantite = quantite
        self.notes = notes
        self.reference = reference

    def __repr__(self):
        return (f"{self.nom}: {self.longueur:.0f}x{self.largeur:.0f}x{self.epaisseur:.0f}mm "
                f"(x{self.quantite}) - {self.notes}")


class FicheFabrication:
    """Liste des pieces et quincaillerie d'un amenagement."""

    def __init__(self):
        self.pieces: list[PieceInfo] = []
        self.quincaillerie: list[dict] = []

    def ajouter_piece(self, piece: PieceInfo):
        self.pieces.append(piece)

    def ajouter_quincaillerie(self, nom: str, quantite: int, description: str = ""):
        self.quincaillerie.append({
            "nom": nom,
            "quantite": quantite,
            "description": description,
        })

    def generer_texte(self, config: dict) -> str:
        """Genere la fiche de fabrication en texte formate."""
        lines = []
        lines.append("=" * 80)
        lines.append("  FICHE DE FABRICATION - AMENAGEMENT INTERIEUR PLACARD")
        lines.append("=" * 80)
        lines.append(f"  Date : {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        lines.append("")
        lines.append("  DIMENSIONS GLOBALES")
        lines.append(f"    Hauteur   : {config['hauteur']} mm")
        lines.append(f"    Largeur   : {config['largeur']} mm")
        lines.append(f"    Profondeur: {config['profondeur']} mm")
        lines.append("")
        lines.append("-" * 80)
        lines.append("  LISTE DES PANNEAUX")
        lines.append("-" * 80)
        lines.append(f"  {'No':<4} {'Designation':<35} {'Long.':<8} {'Larg.':<8} "
                     f"{'Ep.':<5} {'Qte':<4} {'Chant':<20} {'Notes'}")
        lines.append("-" * 80)

        for i, p in enumerate(self.pieces, 1):
            lines.append(
                f"  {i:<4} {p.nom:<35} {p.longueur:<8.0f} {p.largeur:<8.0f} "
                f"{p.epaisseur:<5.0f} {p.quantite:<4} {p.chant_desc:<20} {p.notes}"
            )

        lines.append("")
        surface_totale = sum(
            p.longueur * p.largeur * p.quantite / 1e6 for p in self.pieces
        )
        lines.append(f"  Surface totale panneaux : {surface_totale:.2f} m2")
        lines.append("")

        if self.quincaillerie:
            lines.append("-" * 80)
            lines.append("  QUINCAILLERIE")
            lines.append("-" * 80)
            for q in self.quincaillerie:
                lines.append(f"    {q['nom']:<40} x{q['quantite']:<4} {q['description']}")
            lines.append("")

        lines.append("-" * 80)
        lines.append("  RESUME MATERIAUX")
        lines.append("-" * 80)

        materiaux = {}
        for p in self.pieces:
            key = (p.epaisseur, p.couleur_fab, p.materiau)
            if key not in materiaux:
                materiaux[key] = {"surface": 0, "pieces": []}
            materiaux[key]["surface"] += p.longueur * p.largeur * p.quantite / 1e6
            materiaux[key]["pieces"].append(p)

        for (ep, coul, mat), info in materiaux.items():
            lines.append(f"    {mat} {ep:.0f}mm {coul}: {info['surface']:.2f} m2 "
                         f"({len(info['pieces'])} pieces)")

        lines.append("")
        lines.append("=" * 80)
        return "\n".join(lines)


# =========================================================================
#  CALCULS GEOMETRIQUES
# =========================================================================

def calculer_largeurs_compartiments(config: dict) -> list[float]:
    """Calcule la largeur utile de chaque compartiment en mm."""
    largeur_totale = config["largeur"]
    nb_separations = len(config["separations"])
    ep_sep = config["panneau_separation"]["epaisseur"]

    largeur_separations = nb_separations * ep_sep
    largeur_disponible = largeur_totale - largeur_separations

    mode = config["mode_largeur"]

    if mode == "egal":
        nb = len(config["compartiments"])
        larg = largeur_disponible / nb
        return [larg] * nb

    elif mode == "proportions":
        props_str = config["largeurs_compartiments"]
        parts = props_str.split(",")
        fractions = []
        for part in parts:
            part = part.strip()
            if "/" in part:
                num, den = part.split("/")
                fractions.append(float(num) / float(den))
            else:
                fractions.append(float(part))
        total_frac = sum(fractions)
        return [largeur_disponible * f / total_frac for f in fractions]

    elif mode == "dimensions":
        dims = config["largeurs_compartiments"]
        total_dims = sum(dims)
        if abs(total_dims - largeur_disponible) > 1:
            ratio = largeur_disponible / total_dims
            return [d * ratio for d in dims]
        return list(map(float, dims))

    elif mode == "mixte":
        dims = config["largeurs_compartiments"]
        largeur_fixee = sum(d for d in dims if d is not None)
        nb_auto = sum(1 for d in dims if d is None)
        largeur_restante = largeur_disponible - largeur_fixee
        larg_auto = largeur_restante / nb_auto if nb_auto > 0 else 0
        return [float(d) if d is not None else larg_auto for d in dims]

    else:
        raise ValueError(f"Mode largeur inconnu: {mode}")


def calculer_dimensions_rayon(config: dict, compartiment_idx: int,
                               largeur_compartiment: float) -> tuple[float, float]:
    """Calcule (profondeur_rayon, largeur_rayon) pour un compartiment."""
    comp = config["compartiments"][compartiment_idx]
    profondeur = config["profondeur"]
    chant_ep = config["panneau_rayon"]["chant_epaisseur"]
    retrait_av = config["panneau_rayon"].get("retrait_avant", 0)
    retrait_ar = config["panneau_rayon"].get("retrait_arriere", 0)

    prof_rayon = profondeur - chant_ep - retrait_av - retrait_ar
    larg_rayon = largeur_compartiment

    saillie = config["crem_encastree"].get("saillie", 0)

    # Cote gauche
    crem_g = comp.get("type_crem_gauche")
    panneau_mur_g = comp.get("panneau_mur_gauche", False)
    if panneau_mur_g:
        larg_rayon -= (config["panneau_mur"]["epaisseur"]
                       + saillie + config["crem_encastree"]["jeu_rayon"])
    elif crem_g == "encastree":
        larg_rayon -= (saillie + config["crem_encastree"]["jeu_rayon"])
    elif crem_g == "applique":
        larg_rayon -= (config["crem_applique"]["epaisseur_saillie"]
                       + config["crem_applique"]["jeu_rayon"])

    # Cote droit
    crem_d = comp.get("type_crem_droite")
    panneau_mur_d = comp.get("panneau_mur_droite", False)
    if panneau_mur_d:
        larg_rayon -= (config["panneau_mur"]["epaisseur"]
                       + saillie + config["crem_encastree"]["jeu_rayon"])
    elif crem_d == "encastree":
        larg_rayon -= (saillie + config["crem_encastree"]["jeu_rayon"])
    elif crem_d == "applique":
        larg_rayon -= (config["crem_applique"]["epaisseur_saillie"]
                       + config["crem_applique"]["jeu_rayon"])

    return prof_rayon, larg_rayon


# =========================================================================
#  GEOMETRIE 2D (VUE DE FACE) POUR VIEWER ET PDF
# =========================================================================

class Rect:
    """Rectangle 2D pour le dessin en vue de face."""
    def __init__(self, x: float, y: float, w: float, h: float,
                 couleur: str = "#C8B68C", label: str = "", type_elem: str = ""):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.couleur = couleur
        self.label = label
        self.type_elem = type_elem

    def __repr__(self):
        return f"Rect({self.label}: x={self.x:.0f}, y={self.y:.0f}, w={self.w:.0f}, h={self.h:.0f})"


def rgb_to_hex(rgb: tuple | list) -> str:
    """Convertit un tuple RGB (0-1) en couleur hex."""
    r, g, b = rgb[:3]
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"


def generer_geometrie_2d(config: dict) -> tuple[list[Rect], FicheFabrication]:
    """
    Genere la liste des rectangles 2D (vue de face, plan XZ) et la fiche de fabrication.

    Retourne (rectangles, fiche_fabrication).
    Vue de face: X = largeur (gauche->droite), Z = hauteur (sol->plafond).
    """
    rects = []
    fiche = FicheFabrication()

    H = config["hauteur"]
    L = config["largeur"]
    P = config["profondeur"]
    ep_sep = config["panneau_separation"]["epaisseur"]
    ep_rayon = config["panneau_rayon"]["epaisseur"]
    ep_rayon_haut = config["panneau_rayon_haut"]["epaisseur"]

    largeurs = calculer_largeurs_compartiments(config)
    nb_comp = len(config["compartiments"])

    # --- Murs ---
    if config.get("afficher_murs", True):
        mur_ep = config.get("mur_epaisseur", 50)
        mur_coul = rgb_to_hex(config.get("mur_couleur_rgb", (0.85, 0.85, 0.82)))
        # Mur gauche
        rects.append(Rect(-mur_ep, 0, mur_ep, H, mur_coul, "Mur gauche", "mur"))
        # Mur droit
        rects.append(Rect(L, 0, mur_ep, H, mur_coul, "Mur droit", "mur"))
        # Sol
        rects.append(Rect(-mur_ep, -mur_ep, L + 2 * mur_ep, mur_ep, mur_coul, "Sol", "mur"))
        # Plafond
        rects.append(Rect(-mur_ep, H, L + 2 * mur_ep, mur_ep, mur_coul, "Plafond", "mur"))

    x_courant = 0.0

    # --- Rayon haut ---
    if config["rayon_haut"]:
        z_rayon_haut = H - config["rayon_haut_position"]
        rects.append(Rect(
            0, z_rayon_haut, L, ep_rayon_haut,
            rgb_to_hex(config["panneau_rayon_haut"]["couleur_rgb"]),
            "Rayon haut", "rayon_haut"
        ))
        rh_retrait_av = config["panneau_rayon_haut"].get("retrait_avant", 0)
        rh_retrait_ar = config["panneau_rayon_haut"].get("retrait_arriere", 0)
        prof_rh = P - config["panneau_rayon_haut"]["chant_epaisseur"] - rh_retrait_av - rh_retrait_ar
        fiche.ajouter_piece(PieceInfo(
            "Rayon haut (toute largeur)", L, prof_rh, ep_rayon_haut,
            couleur_fab=config["panneau_rayon_haut"]["couleur_fab"],
            chant_desc=f"Avant {config['panneau_rayon_haut']['chant_epaisseur']}mm",
            notes="Pose sur tasseaux"
        ))

    # --- Boucle compartiments ---
    for comp_idx in range(nb_comp):
        comp = config["compartiments"][comp_idx]
        larg_comp = largeurs[comp_idx]
        x_debut = x_courant
        x_fin = x_courant + larg_comp

        # --- Panneau mur gauche ---
        if comp.get("panneau_mur_gauche", False) and comp_idx == 0:
            pm = config["panneau_mur"]
            h_pm = H - config["rayon_haut_position"] if config["rayon_haut"] else H
            rects.append(Rect(
                0, 0, pm["epaisseur"], h_pm,
                rgb_to_hex(pm["couleur_rgb"]),
                "Panneau mur G", "panneau_mur"
            ))
            fiche.ajouter_piece(PieceInfo(
                "Panneau mur gauche", h_pm, P - pm["chant_epaisseur"], pm["epaisseur"],
                couleur_fab=pm["couleur_fab"],
                chant_desc=f"Avant {pm['chant_epaisseur']}mm",
                notes="Fixe au mur, cremailleres encastrees"
            ))

        # --- Panneau mur droit ---
        if comp.get("panneau_mur_droite", False) and comp_idx == nb_comp - 1:
            pm = config["panneau_mur"]
            h_pm = H - config["rayon_haut_position"] if config["rayon_haut"] else H
            rects.append(Rect(
                L - pm["epaisseur"], 0, pm["epaisseur"], h_pm,
                rgb_to_hex(pm["couleur_rgb"]),
                "Panneau mur D", "panneau_mur"
            ))
            fiche.ajouter_piece(PieceInfo(
                "Panneau mur droit", h_pm, P - pm["chant_epaisseur"], pm["epaisseur"],
                couleur_fab=pm["couleur_fab"],
                chant_desc=f"Avant {pm['chant_epaisseur']}mm",
                notes="Fixe au mur, cremailleres encastrees"
            ))

        # --- Cremailleres ---
        if comp["rayons"] > 0:
            z_haut_crem = H - config["rayon_haut_position"] if config["rayon_haut"] else H
            h_crem = z_haut_crem

            crem_g = comp.get("type_crem_gauche")
            panneau_mur_g = comp.get("panneau_mur_gauche", False)
            ce = config["crem_encastree"]
            ca = config["crem_applique"]

            # Cremaillere gauche
            if panneau_mur_g or crem_g == "encastree":
                if panneau_mur_g:
                    x_cg = x_debut + config["panneau_mur"]["epaisseur"] - ce["epaisseur"]
                else:
                    x_cg = x_debut - ce["epaisseur"] + ce.get("saillie", 0)
                rects.append(Rect(
                    x_cg, 0, ce["epaisseur"], h_crem,
                    rgb_to_hex(ce["couleur_rgb"]),
                    f"Crem enc. G C{comp_idx+1}", "cremaillere_encastree"
                ))
                fiche.ajouter_quincaillerie(
                    f"Cremaillere encastree (C{comp_idx+1} gauche)", 2,
                    f"L={h_crem:.0f}mm"
                )
            elif crem_g == "applique":
                rects.append(Rect(
                    x_debut, 0, ca["epaisseur_saillie"], h_crem,
                    rgb_to_hex(ca["couleur_rgb"]),
                    f"Crem app. G C{comp_idx+1}", "cremaillere_applique"
                ))
                fiche.ajouter_quincaillerie(
                    f"Cremaillere applique (C{comp_idx+1} gauche)", 2,
                    f"L={h_crem:.0f}mm"
                )

            # Cremaillere droite
            crem_d = comp.get("type_crem_droite")
            panneau_mur_d = comp.get("panneau_mur_droite", False)
            if panneau_mur_d or crem_d == "encastree":
                if panneau_mur_d:
                    x_cd = L - config["panneau_mur"]["epaisseur"]
                else:
                    x_cd = x_fin - ce.get("saillie", 0)
                rects.append(Rect(
                    x_cd, 0, ce["epaisseur"], h_crem,
                    rgb_to_hex(ce["couleur_rgb"]),
                    f"Crem enc. D C{comp_idx+1}", "cremaillere_encastree"
                ))
                fiche.ajouter_quincaillerie(
                    f"Cremaillere encastree (C{comp_idx+1} droite)", 2,
                    f"L={h_crem:.0f}mm"
                )
            elif crem_d == "applique":
                rects.append(Rect(
                    x_fin - ca["epaisseur_saillie"], 0, ca["epaisseur_saillie"], h_crem,
                    rgb_to_hex(ca["couleur_rgb"]),
                    f"Crem app. D C{comp_idx+1}", "cremaillere_applique"
                ))
                fiche.ajouter_quincaillerie(
                    f"Cremaillere applique (C{comp_idx+1} droite)", 2,
                    f"L={h_crem:.0f}mm"
                )

        # --- Rayons ---
        if comp["rayons"] > 0:
            prof_rayon, larg_rayon = calculer_dimensions_rayon(config, comp_idx, larg_comp)
            z_haut_rayons = H
            if config["rayon_haut"]:
                z_haut_rayons = H - config["rayon_haut_position"] - ep_rayon_haut

            nb_rayons = comp["rayons"]
            espace = z_haut_rayons / (nb_rayons + 1)

            # Offset X du rayon
            x_rayon = x_debut
            crem_g = comp.get("type_crem_gauche")
            panneau_mur_g = comp.get("panneau_mur_gauche", False)
            saillie = ce.get("saillie", 0)
            if panneau_mur_g:
                x_rayon += config["panneau_mur"]["epaisseur"] + saillie + ce["jeu_rayon"]
            elif crem_g == "encastree":
                x_rayon += saillie + ce["jeu_rayon"]
            elif crem_g == "applique":
                x_rayon += ca["epaisseur_saillie"] + ca["jeu_rayon"]

            for r_idx in range(nb_rayons):
                z_rayon = espace * (r_idx + 1)
                rects.append(Rect(
                    x_rayon, z_rayon, larg_rayon, ep_rayon,
                    rgb_to_hex(config["panneau_rayon"]["couleur_rgb"]),
                    f"Rayon C{comp_idx+1} R{r_idx+1}", "rayon"
                ))

            fiche.ajouter_piece(PieceInfo(
                f"Rayon compartiment {comp_idx+1}",
                larg_rayon, prof_rayon, ep_rayon,
                couleur_fab=config["panneau_rayon"]["couleur_fab"],
                chant_desc=f"Avant {config['panneau_rayon']['chant_epaisseur']}mm",
                quantite=nb_rayons,
                notes="Sur cremailleres"
            ))

        # --- Tasseaux ---
        tass = config["tasseau"]
        longueur_tasseau = P - config["panneau_rayon"]["chant_epaisseur"] - tass["retrait_avant"]

        trh_g = comp.get("tasseau_rayon_haut_gauche", False)
        trh_d = comp.get("tasseau_rayon_haut_droite", False)
        tr_g = comp.get("tasseau_rayons_gauche", False)
        tr_d = comp.get("tasseau_rayons_droite", False)

        nb_tass_g = 0
        nb_tass_d = 0

        if config["rayon_haut"] and (trh_g or trh_d):
            z_rh = H - config["rayon_haut_position"]
            z_tass = z_rh - tass["section_h"]

            if trh_g:
                x_tg = config["panneau_mur"]["epaisseur"] if (comp_idx == 0 and comp.get("panneau_mur_gauche")) else (0 if comp_idx == 0 else x_debut)
                rects.append(Rect(
                    x_tg, z_tass, tass["section_l"], tass["section_h"],
                    rgb_to_hex(tass["couleur_rgb"]),
                    f"Tasseau RH G C{comp_idx+1}", "tasseau"
                ))
                nb_tass_g += 1

            if trh_d:
                if comp_idx == nb_comp - 1:
                    x_td = L - config["panneau_mur"]["epaisseur"] - tass["section_l"] if comp.get("panneau_mur_droite") else L - tass["section_l"]
                else:
                    x_td = x_fin - tass["section_l"]
                rects.append(Rect(
                    x_td, z_tass, tass["section_l"], tass["section_h"],
                    rgb_to_hex(tass["couleur_rgb"]),
                    f"Tasseau RH D C{comp_idx+1}", "tasseau"
                ))
                nb_tass_d += 1

        if comp["rayons"] > 0 and (tr_g or tr_d):
            z_haut_rayons = H - config["rayon_haut_position"] - ep_rayon_haut if config["rayon_haut"] else H
            nb_rayons = comp["rayons"]
            espace = z_haut_rayons / (nb_rayons + 1)

            for r_idx in range(nb_rayons):
                z_r = espace * (r_idx + 1)
                z_tass_r = z_r - tass["section_h"]

                if tr_g:
                    x_tg = config["panneau_mur"]["epaisseur"] if (comp_idx == 0 and comp.get("panneau_mur_gauche")) else (0 if comp_idx == 0 else x_debut)
                    rects.append(Rect(
                        x_tg, z_tass_r, tass["section_l"], tass["section_h"],
                        rgb_to_hex(tass["couleur_rgb"]),
                        f"Tasseau R{r_idx+1} G C{comp_idx+1}", "tasseau"
                    ))
                    nb_tass_g += 1

                if tr_d:
                    if comp_idx == nb_comp - 1:
                        x_td = L - config["panneau_mur"]["epaisseur"] - tass["section_l"] if comp.get("panneau_mur_droite") else L - tass["section_l"]
                    else:
                        x_td = x_fin - tass["section_l"]
                    rects.append(Rect(
                        x_td, z_tass_r, tass["section_l"], tass["section_h"],
                        rgb_to_hex(tass["couleur_rgb"]),
                        f"Tasseau R{r_idx+1} D C{comp_idx+1}", "tasseau"
                    ))
                    nb_tass_d += 1

        if nb_tass_g > 0:
            support = "mur" if comp_idx == 0 else f"separation {comp_idx}"
            fiche.ajouter_piece(PieceInfo(
                f"Tasseau C{comp_idx+1} gauche ({support})",
                longueur_tasseau, tass["section_l"], tass["section_h"],
                materiau="Tasseau bois", quantite=nb_tass_g,
                notes=f"Biseaute en bout, fixe sur {support}"
            ))
        if nb_tass_d > 0:
            support = "mur" if comp_idx == nb_comp - 1 else f"separation {comp_idx+1}"
            fiche.ajouter_piece(PieceInfo(
                f"Tasseau C{comp_idx+1} droite ({support})",
                longueur_tasseau, tass["section_l"], tass["section_h"],
                materiau="Tasseau bois", quantite=nb_tass_d,
                notes=f"Biseaute en bout, fixe sur {support}"
            ))

        # --- Separation apres ce compartiment ---
        if comp_idx < nb_comp - 1:
            sep = config["separations"][comp_idx]
            x_sep = x_fin

            if sep["mode"] == "sous_rayon" and config["rayon_haut"]:
                h_sep = H - config["rayon_haut_position"]
            else:
                h_sep = H

            prof_sep = P - config["panneau_separation"]["chant_epaisseur"]

            rects.append(Rect(
                x_sep, 0, ep_sep, h_sep,
                rgb_to_hex(config["panneau_separation"]["couleur_rgb"]),
                f"Separation {comp_idx+1}", "separation"
            ))

            fiche.ajouter_piece(PieceInfo(
                f"Separation {comp_idx+1}",
                h_sep, prof_sep, ep_sep,
                couleur_fab=config["panneau_separation"]["couleur_fab"],
                chant_desc=f"Avant {config['panneau_separation']['chant_epaisseur']}mm",
                notes=f"Mode: {sep['mode']}"
            ))

        x_courant = x_fin
        if comp_idx < nb_comp - 1:
            x_courant += ep_sep

    return rects, fiche
