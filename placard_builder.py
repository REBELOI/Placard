#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
  AMÉNAGEMENT INTÉRIEUR DE PLACARD - Script paramétrique FreeCAD
=============================================================================
  Génère la représentation 3D et la fiche de fabrication d'un aménagement
  intérieur de placard encastré (entre 3 murs, sol et plafond).

  Matériaux : Panneaux aggloméré mélaminé avec chant plaqué.
  Éléments  : Séparations verticales, rayons horizontaux,
              crémaillères (encastrées / applique), tasseaux.

  Auteur  : Script paramétrique généré pour FreeCAD 0.21+
  Version : 1.3 - Crémaillères encastrées avec rainures
=============================================================================
"""

import FreeCAD as App
import FreeCADGui as Gui
import Part
import math
import os
from datetime import datetime

# ===========================================================================
#  CONFIGURATION PRINCIPALE - MODIFIEZ ICI VOS PARAMÈTRES
# ===========================================================================

CONFIG = {
    # --- Dimensions globales du placard (mm) ---
    "hauteur": 2500,         # Hauteur sol-plafond
    "largeur": 2400,         # Largeur entre les 2 murs latéraux
    "profondeur": 600,       # Profondeur (du mur du fond vers l'avant)

    # --- Schéma d'aménagement ---
    # Liste de compartiments. Chaque compartiment est un dict:
    #   "largeur"   : largeur en mm (ou "=" pour répartition égale)
    #   "rayons"    : nombre de rayons
    #   "type_crem" : "encastree" ou "applique" côté mur
    #   Côté séparation : toujours encastrée
    #
    # Mode des séparations:
    #   "toute_hauteur" : la séparation va du sol au plafond
    #   "sous_rayon"    : la séparation commence sous le rayon haut
    #
    # Rayon haut (toute largeur, posé sur tasseaux):
    #   "rayon_haut": True/False
    #   "rayon_haut_position": distance du haut en mm (ex: 350)

    "rayon_haut": True,
    "rayon_haut_position": 350,  # Distance depuis le plafond

    # --- Définition des séparations et compartiments ---
    # "mode_largeur": "egal" | "proportions" | "dimensions"
    # Si "egal"        : toutes les largeurs identiques
    # Si "proportions" : ex "1/3,2/3" pour 2 compartiments
    # Si "dimensions"  : ex [500, 600] largeurs en mm
    "mode_largeur": "dimensions",
    "largeurs_compartiments": [800, 1600],  # en mm si mode "dimensions"
    # "largeurs_compartiments": "1/3,2/3",  # si mode "proportions"
    # "nombre_compartiments": 2,             # si mode "egal"

    "separations": [
        {
            "mode": "sous_rayon",  # "toute_hauteur" ou "sous_rayon"
        },
        # Ajoutez d'autres séparations si plus de 2 compartiments
    ],

    "compartiments": [
        {
            "nom": "Compartiment 1",
            "rayons": 0,               # Nombre de rayons (0 = vide)
            "type_crem_gauche": None,   # None si côté mur sans crémaillère
            "type_crem_droite": "encastree",  # côté séparation
            "panneau_mur_gauche": False,  # Panneau avec crém. encastrée côté mur
            "tasseau_rayon_haut_gauche": False,  # Tasseau sous rayon haut, fixé à gauche
            "tasseau_rayon_haut_droite": False,  # Tasseau sous rayon haut, fixé à droite
            "tasseau_rayons_gauche": False,      # Tasseaux sous chaque rayon, fixés à gauche
            "tasseau_rayons_droite": False,      # Tasseaux sous chaque rayon, fixés à droite
        },
        {
            "nom": "Compartiment 2",
            "rayons": 3,
            "type_crem_gauche": "encastree",   # côté séparation
            "type_crem_droite": "applique",     # côté mur
            "panneau_mur_droite": False,        # True = panneau + crém encastrée au lieu d'applique
            "tasseau_rayon_haut_gauche": False,
            "tasseau_rayon_haut_droite": False,
            "tasseau_rayons_gauche": False,
            "tasseau_rayons_droite": False,
        },
    ],

    # --- Panneaux de séparation ---
    "panneau_separation": {
        "epaisseur": 19,            # mm
        "couleur_fab": "Blanc Standard",
        "couleur_rgb": (0.95, 0.95, 0.92),  # Blanc cassé
        "chant_epaisseur": 1,       # mm (chant ABS)
        "chant_couleur_fab": "Blanc",
        "chant_couleur_rgb": (0.98, 0.98, 0.96),
    },

    # --- Panneaux des rayons ---
    "panneau_rayon": {
        "epaisseur": 19,            # mm
        "couleur_fab": "Blanc Standard",
        "couleur_rgb": (0.95, 0.95, 0.92),
        "chant_epaisseur": 1,       # mm
        "chant_couleur_fab": "Blanc",
        "chant_couleur_rgb": (0.98, 0.98, 0.96),
    },

    # --- Rayon haut (posé sur tasseaux) ---
    "panneau_rayon_haut": {
        "epaisseur": 22,            # mm (souvent plus épais pour la portée)
        "couleur_fab": "Blanc Standard",
        "couleur_rgb": (0.95, 0.95, 0.92),
        "chant_epaisseur": 1,
        "chant_couleur_fab": "Blanc",
        "chant_couleur_rgb": (0.98, 0.98, 0.96),
    },

    # --- Crémaillère encastrée ---
    "crem_encastree": {
        "largeur": 16,              # Largeur de l'encastrement (mm)
        "epaisseur": 5,             # Profondeur totale de la crémaillère (mm)
        "saillie": 0,               # Dépassement hors du panneau (mm). 0 = affleurante
        "jeu_rayon": 2,             # Jeu entre crémaillère et rayon (mm)
        "retrait_avant": 80,        # Distance du bord avant du panneau (mm)
        "retrait_arriere": 80,      # Distance du mur du fond (mm)
        "couleur_rgb": (0.6, 0.6, 0.6),  # Gris acier
    },

    # --- Crémaillère en applique ---
    "crem_applique": {
        "largeur": 25,              # Largeur de la crémaillère (mm)
        "epaisseur_saillie": 12,    # Épaisseur en saillie du mur (mm)
        "jeu_rayon": 2,             # Jeu entre crémaillère et rayon (mm)
        "retrait_avant": 80,        # Distance du bord avant du rayon (mm)
        "retrait_arriere": 80,      # Distance du mur du fond (mm)
        "couleur_rgb": (0.6, 0.6, 0.6),
    },

    # --- Tasseaux (support rayon haut) ---
    "tasseau": {
        "section_h": 30,            # Hauteur de section (mm)
        "section_l": 30,            # Largeur de section (mm)
        "retrait_avant": 20,        # Retrait par rapport à la profondeur du rayon
        "couleur_rgb": (0.85, 0.75, 0.55),  # Bois naturel
        # Profil bisauté en bout avant
        "biseau_longueur": 15,      # Longueur du biseau (mm)
    },

    # --- Panneau mur (optionnel, remplace applique par encastrée) ---
    "panneau_mur": {
        "epaisseur": 19,
        "couleur_fab": "Blanc Standard",
        "couleur_rgb": (0.95, 0.95, 0.92),
        "chant_epaisseur": 1,
        "chant_couleur_fab": "Blanc",
        "chant_couleur_rgb": (0.98, 0.98, 0.96),
    },

    # --- Murs (représentation visuelle) ---
    "afficher_murs": True,
    "mur_epaisseur": 5,  # Épaisseur visuelle des murs (mm)
    "mur_couleur_rgb": (0.85, 0.85, 0.85),
    "mur_transparence": 70,  # 0-100

    # --- Export fiche de fabrication ---
    "export_fiche": True,
    "dossier_export": "",  # Vide = même dossier que le fichier FreeCAD
}


# ===========================================================================
#  CONFIGURATION EXEMPLE N°2 (décommenter pour tester)
# ===========================================================================
# CONFIG_EXEMPLE2 = {
#     **CONFIG,
#     "rayon_haut": False,
#     "mode_largeur": "proportions",
#     "largeurs_compartiments": "1/2,1/2",
#     "separations": [
#         {"mode": "toute_hauteur"},
#     ],
#     "compartiments": [
#         {
#             "nom": "Compartiment 1",
#             "rayons": 4,
#             "type_crem_gauche": "applique",
#             "type_crem_droite": "encastree",
#         },
#         {
#             "nom": "Compartiment 2",
#             "rayons": 3,
#             "type_crem_gauche": "encastree",
#             "type_crem_droite": "applique",
#         },
#     ],
# }
# CONFIG = CONFIG_EXEMPLE2


# ===========================================================================
#  CLASSES UTILITAIRES
# ===========================================================================

class PieceInfo:
    """Stocke les informations d'une pièce pour la fiche de fabrication."""
    def __init__(self, nom, longueur, largeur, epaisseur,
                 materiau="Aggloméré mélaminé", couleur_fab="",
                 chant_desc="", quantite=1, notes=""):
        self.nom = nom
        self.longueur = longueur  # mm
        self.largeur = largeur    # mm
        self.epaisseur = epaisseur  # mm
        self.materiau = materiau
        self.couleur_fab = couleur_fab
        self.chant_desc = chant_desc
        self.quantite = quantite
        self.notes = notes

    def __repr__(self):
        return (f"{self.nom}: {self.longueur}x{self.largeur}x{self.epaisseur}mm "
                f"(x{self.quantite}) - {self.notes}")


class FicheFabrication:
    """Gère la liste des pièces et génère la fiche de fabrication."""
    def __init__(self):
        self.pieces = []
        self.quincaillerie = []

    def ajouter_piece(self, piece):
        self.pieces.append(piece)

    def ajouter_quincaillerie(self, nom, quantite, description=""):
        self.quincaillerie.append({
            "nom": nom,
            "quantite": quantite,
            "description": description,
        })

    def generer_texte(self, config):
        """Génère la fiche de fabrication en texte formaté."""
        lines = []
        lines.append("=" * 80)
        lines.append("  FICHE DE FABRICATION - AMÉNAGEMENT INTÉRIEUR PLACARD")
        lines.append("=" * 80)
        lines.append(f"  Date : {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        lines.append("")
        lines.append("  DIMENSIONS GLOBALES")
        lines.append(f"    Hauteur   : {config['hauteur']} mm")
        lines.append(f"    Largeur   : {config['largeur']} mm")
        lines.append(f"    Profondeur: {config['profondeur']} mm")
        lines.append("")

        # --- Panneaux ---
        lines.append("-" * 80)
        lines.append("  LISTE DES PANNEAUX")
        lines.append("-" * 80)
        lines.append(f"  {'N°':<4} {'Désignation':<35} {'Long.':<8} {'Larg.':<8} "
                      f"{'Ép.':<5} {'Qté':<4} {'Chant':<20} {'Notes'}")
        lines.append("-" * 80)

        for i, p in enumerate(self.pieces, 1):
            lines.append(
                f"  {i:<4} {p.nom:<35} {p.longueur:<8.0f} {p.largeur:<8.0f} "
                f"{p.epaisseur:<5.0f} {p.quantite:<4} {p.chant_desc:<20} {p.notes}"
            )

        lines.append("")

        # --- Surface totale de panneaux ---
        surface_totale = sum(
            p.longueur * p.largeur * p.quantite / 1e6 for p in self.pieces
        )
        lines.append(f"  Surface totale panneaux : {surface_totale:.2f} m²")
        lines.append("")

        # --- Quincaillerie ---
        if self.quincaillerie:
            lines.append("-" * 80)
            lines.append("  QUINCAILLERIE")
            lines.append("-" * 80)
            for q in self.quincaillerie:
                lines.append(f"    {q['nom']:<40} x{q['quantite']:<4} {q['description']}")
            lines.append("")

        # --- Résumé matériaux ---
        lines.append("-" * 80)
        lines.append("  RÉSUMÉ MATÉRIAUX")
        lines.append("-" * 80)

        # Regrouper par épaisseur et couleur
        materiaux = {}
        for p in self.pieces:
            key = (p.epaisseur, p.couleur_fab, p.materiau)
            if key not in materiaux:
                materiaux[key] = {"surface": 0, "pieces": []}
            materiaux[key]["surface"] += p.longueur * p.largeur * p.quantite / 1e6
            materiaux[key]["pieces"].append(p)

        for (ep, coul, mat), info in materiaux.items():
            lines.append(f"    {mat} {ep}mm {coul}: {info['surface']:.2f} m² "
                          f"({len(info['pieces'])} pièces)")

        lines.append("")
        lines.append("=" * 80)

        return "\n".join(lines)


# ===========================================================================
#  FONCTIONS DE CALCUL DES DIMENSIONS
# ===========================================================================

def calculer_largeurs_compartiments(config):
    """Calcule la largeur utile de chaque compartiment en mm."""
    largeur_totale = config["largeur"]
    nb_separations = len(config["separations"])
    ep_sep = config["panneau_separation"]["epaisseur"]

    # Largeur occupée par les séparations
    largeur_separations = nb_separations * ep_sep

    # Largeur disponible pour les compartiments
    largeur_disponible = largeur_totale - largeur_separations

    mode = config["mode_largeur"]

    if mode == "egal":
        nb = len(config["compartiments"])
        larg = largeur_disponible / nb
        return [larg] * nb

    elif mode == "proportions":
        props_str = config["largeurs_compartiments"]
        # Parse "1/3,2/3" ou "1/2,1/2"
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
        # Vérification
        total_dims = sum(dims)
        if abs(total_dims - largeur_disponible) > 1:
            App.Console.PrintWarning(
                f"⚠ Somme des largeurs compartiments ({total_dims}mm) "
                f"≠ largeur disponible ({largeur_disponible}mm). "
                f"Ajustement proportionnel.\n"
            )
            ratio = largeur_disponible / total_dims
            return [d * ratio for d in dims]
        return list(dims)

    elif mode == "mixte":
        # Certaines largeurs spécifiées, les autres (None) calculées automatiquement
        dims = config["largeurs_compartiments"]
        largeur_fixee = sum(d for d in dims if d is not None)
        nb_auto = sum(1 for d in dims if d is None)
        largeur_restante = largeur_disponible - largeur_fixee
        if nb_auto > 0:
            larg_auto = largeur_restante / nb_auto
        else:
            larg_auto = 0
        result = []
        for d in dims:
            if d is not None:
                result.append(d)
            else:
                result.append(larg_auto)
        # Avertir si ça ne colle pas
        if largeur_restante < 0:
            App.Console.PrintWarning(
                f"⚠ Largeurs fixées ({largeur_fixee}mm) > "
                f"largeur disponible ({largeur_disponible}mm).\n"
            )
        return result

    else:
        raise ValueError(f"Mode largeur inconnu: {mode}")


def calculer_dimensions_rayon(config, compartiment_idx, largeur_compartiment):
    """Calcule les dimensions d'un rayon pour un compartiment donné."""
    comp = config["compartiments"][compartiment_idx]
    profondeur = config["profondeur"]
    ep_rayon = config["panneau_rayon"]["epaisseur"]
    chant_ep = config["panneau_rayon"]["chant_epaisseur"]

    # Profondeur du rayon = profondeur placard - chant avant
    prof_rayon = profondeur - chant_ep

    # Largeur du rayon : dépend des crémaillères de chaque côté
    larg_rayon = largeur_compartiment
    saillie = config["crem_encastree"].get("saillie", 0)

    # Côté gauche
    crem_g = comp.get("type_crem_gauche")
    panneau_mur_g = comp.get("panneau_mur_gauche", False)
    if panneau_mur_g:
        # Panneau mur + crémaillère encastrée : épaisseur panneau + saillie + jeu
        larg_rayon -= (config["panneau_mur"]["epaisseur"]
                       + saillie
                       + config["crem_encastree"]["jeu_rayon"])
    elif crem_g == "encastree":
        # Crémaillère encastrée dans séparation : saillie + jeu
        larg_rayon -= (saillie + config["crem_encastree"]["jeu_rayon"])
    elif crem_g == "applique":
        larg_rayon -= (config["crem_applique"]["epaisseur_saillie"]
                       + config["crem_applique"]["jeu_rayon"])

    # Côté droit
    crem_d = comp.get("type_crem_droite")
    panneau_mur_d = comp.get("panneau_mur_droite", False)
    if panneau_mur_d:
        larg_rayon -= (config["panneau_mur"]["epaisseur"]
                       + saillie
                       + config["crem_encastree"]["jeu_rayon"])
    elif crem_d == "encastree":
        larg_rayon -= (saillie + config["crem_encastree"]["jeu_rayon"])
    elif crem_d == "applique":
        larg_rayon -= (config["crem_applique"]["epaisseur_saillie"]
                       + config["crem_applique"]["jeu_rayon"])

    return prof_rayon, larg_rayon


# ===========================================================================
#  FONCTIONS DE CRÉATION 3D
# ===========================================================================

def creer_panneau(nom, longueur, largeur, epaisseur, position, couleur_rgb,
                  transparence=0, group=None):
    """Crée un panneau rectangulaire (Box) dans FreeCAD."""
    doc = App.ActiveDocument
    body = doc.addObject("Part::Box", nom)
    body.Length = longueur
    body.Width = largeur
    body.Height = epaisseur
    body.Placement = App.Placement(
        App.Vector(position[0], position[1], position[2]),
        App.Rotation(App.Vector(0, 0, 1), 0)
    )

    if Gui.ActiveDocument:
        body.ViewObject.ShapeColor = couleur_rgb
        body.ViewObject.Transparency = transparence

    if group:
        group.addObject(body)

    return body


def creer_tasseau_bisaute(nom, longueur, section_h, section_l,
                          biseau_longueur, position,
                          couleur_rgb, group=None):
    """
    Crée un tasseau orienté dans le sens de la PROFONDEUR (axe Y).
    Le tasseau part de la face avant (Y faible) vers le mur du fond (Y élevé).
    Le biseau est en bout avant (côté Y faible, face visible).

    Profil en section longitudinale (vue de côté, plan YZ):
        ___________________        <- face du dessus (Z = section_h)
        |                          <- face arrière (collée au mur, Y=longueur)
        __________________/        <- face du dessous avec biseau côté avant
                           |       <- face verticale en bout avant (Y=0)
        |<----Longueur---->|       (longueur = sens profondeur Y)

    Le profil est dessiné dans le plan YZ, puis extrudé selon X
    sur section_l (largeur du tasseau).

    position = (X, Y, Z) du coin avant-bas-gauche du tasseau.
    """
    doc = App.ActiveDocument

    # Profil dans le plan YZ (X=0), Y = profondeur, Z = hauteur
    # Biseau côté avant (Y=0):
    #   P0: (Y=longueur, Z=0)                  bas-arrière (mur)
    #   P1: (Y=longueur, Z=section_h)          haut-arrière
    #   P2: (Y=0, Z=section_h)                 haut-avant
    #   P3: (Y=0, Z=biseau_longueur)           bout avant (haut biseau)
    #   P4: (Y=biseau_longueur, Z=0)           fin du biseau, rejoint le bas

    wire_pts = [
        App.Vector(0, longueur, 0),                                # P0 bas-arrière
        App.Vector(0, longueur, section_h),                        # P1 haut-arrière
        App.Vector(0, 0, section_h),                               # P2 haut-avant
        App.Vector(0, 0, biseau_longueur),                         # P3 bout avant
        App.Vector(0, biseau_longueur, 0),                         # P4 bas biseau
        App.Vector(0, longueur, 0),                                # Fermeture
    ]

    wire = Part.makePolygon(wire_pts)
    face = Part.Face(wire)
    # Extrusion selon X (largeur/section du tasseau)
    solid = face.extrude(App.Vector(section_l, 0, 0))

    part_obj = doc.addObject("Part::Feature", nom)
    part_obj.Shape = solid
    part_obj.Placement = App.Placement(
        App.Vector(position[0], position[1], position[2]),
        App.Rotation(App.Vector(0, 0, 1), 0)
    )

    if Gui.ActiveDocument:
        part_obj.ViewObject.ShapeColor = couleur_rgb

    if group:
        group.addObject(part_obj)

    return part_obj


def creer_cremaillere(nom, hauteur, largeur, epaisseur, position,
                      couleur_rgb, group=None):
    """Crée une crémaillère (représentation simplifiée comme un panneau fin).
    
    Paramètres positionnels dans l'espace:
      epaisseur -> axe X (fine dimension)
      largeur   -> axe Y (profondeur dans le placard)
      hauteur   -> axe Z
    """
    return creer_panneau(nom, epaisseur, largeur, hauteur, position,
                         couleur_rgb, transparence=0, group=group)


def creer_rainure_dans_panneau(panneau_obj, rainure_x, rainure_y, rainure_z,
                                rainure_longueur_x, rainure_largeur_y,
                                rainure_hauteur_z, nom_rainure="Rainure"):
    """
    Soustrait une rainure rectangulaire d'un panneau existant.
    Retourne le nouvel objet avec la rainure.
    
    Les paramètres définissent la position et dimensions de la boîte à soustraire.
    """
    doc = App.ActiveDocument

    # Créer la boîte de découpe
    cut_box = doc.addObject("Part::Box", nom_rainure + "_cut")
    cut_box.Length = rainure_longueur_x
    cut_box.Width = rainure_largeur_y
    cut_box.Height = rainure_hauteur_z
    cut_box.Placement = App.Placement(
        App.Vector(rainure_x, rainure_y, rainure_z),
        App.Rotation(App.Vector(0, 0, 1), 0)
    )

    # Opération booléenne de soustraction
    cut_obj = doc.addObject("Part::Cut", panneau_obj.Name + "_rainure")
    cut_obj.Base = panneau_obj
    cut_obj.Tool = cut_box

    # Copier les propriétés visuelles
    if Gui.ActiveDocument and hasattr(panneau_obj, 'ViewObject'):
        cut_obj.ViewObject.ShapeColor = panneau_obj.ViewObject.ShapeColor
        cut_obj.ViewObject.Transparency = panneau_obj.ViewObject.Transparency

    # Masquer les objets sources
    if Gui.ActiveDocument:
        panneau_obj.ViewObject.Visibility = False
        cut_box.ViewObject.Visibility = False

    return cut_obj


def appliquer_rainures_cremaillere(panneau_obj, face_x, panneau_ep,
                                    hauteur_crem, config_crem, z_base,
                                    profondeur_placard, side="gauche",
                                    group=None):
    """
    Applique 2 rainures (avant + arrière) pour crémaillères encastrées
    sur une face d'un panneau.
    
    face_x : position X de la face du panneau où encastrer
    panneau_ep : épaisseur du panneau
    side : "gauche" (rainure côté X+) ou "droite" (rainure côté X-)
    
    Retourne le panneau modifié et la liste des crémaillères créées.
    """
    doc = App.ActiveDocument
    ce = config_crem
    profondeur_encastrement = ce["epaisseur"] - ce["saillie"]

    result_panneau = panneau_obj

    positions_y = [
        ce["retrait_avant"],                                      # Avant (Y=0)
        profondeur_placard - ce["retrait_arriere"] - ce["largeur"],  # Arrière (Y=P)
    ]

    for i, y_pos in enumerate(positions_y):
        pos_label = "Arr" if i == 0 else "Avt"

        if side == "gauche":
            # Rainure sur la face droite du panneau (X+ du panneau)
            rainure_x = face_x + panneau_ep - profondeur_encastrement
        else:
            # Rainure sur la face gauche du panneau (X- du panneau)
            rainure_x = face_x

        result_panneau = creer_rainure_dans_panneau(
            result_panneau,
            rainure_x, y_pos, z_base,
            profondeur_encastrement, ce["largeur"], hauteur_crem,
            nom_rainure=f"Rainure_{side}_{pos_label}"
        )

    if group:
        group.addObject(result_panneau)

    return result_panneau


def creer_chant(nom, longueur, hauteur, epaisseur, position,
                couleur_rgb, group=None):
    """Crée un chant de panneau."""
    return creer_panneau(nom, epaisseur, longueur, hauteur, position,
                         couleur_rgb, transparence=0, group=group)


# ===========================================================================
#  FONCTION PRINCIPALE DE CONSTRUCTION
# ===========================================================================

def construire_placard(config):
    """Construit l'ensemble du placard dans FreeCAD."""

    # --- Initialisation du document ---
    doc_name = "Placard_Amenagement"
    if App.ActiveDocument:
        App.closeDocument(App.ActiveDocument.Name)
    doc = App.newDocument(doc_name)

    fiche = FicheFabrication()

    # --- Groupes pour organiser l'arbre ---
    grp_murs = doc.addObject("App::DocumentObjectGroup", "Murs")
    grp_separations = doc.addObject("App::DocumentObjectGroup", "Separations")
    grp_rayons = doc.addObject("App::DocumentObjectGroup", "Rayons")
    grp_tasseaux = doc.addObject("App::DocumentObjectGroup", "Tasseaux")
    grp_cremailleres = doc.addObject("App::DocumentObjectGroup", "Cremailleres")
    grp_panneaux_mur = doc.addObject("App::DocumentObjectGroup", "Panneaux_Mur")

    H = config["hauteur"]
    L = config["largeur"]
    P = config["profondeur"]
    ep_sep = config["panneau_separation"]["epaisseur"]
    ep_rayon = config["panneau_rayon"]["epaisseur"]
    ep_rayon_haut = config["panneau_rayon_haut"]["epaisseur"]

    # ===================================================================
    #  MURS (représentation visuelle)
    #  Convention Y: Y=0 = face avant, Y=P = mur du fond
    # ===================================================================
    if config["afficher_murs"]:
        ep_mur = config["mur_epaisseur"]
        coul_mur = config["mur_couleur_rgb"]
        transp_mur = config["mur_transparence"]

        # Mur du fond (plan XZ à Y=P)
        creer_panneau("Mur_Fond", L, ep_mur, H,
                       (-ep_mur, P, 0), coul_mur, transp_mur, grp_murs)
        # Mur gauche (plan YZ à X=0)
        creer_panneau("Mur_Gauche", ep_mur, P, H,
                       (-ep_mur, 0, 0), coul_mur, transp_mur, grp_murs)
        # Mur droit (plan YZ à X=L)
        creer_panneau("Mur_Droit", ep_mur, P, H,
                       (L, 0, 0), coul_mur, transp_mur, grp_murs)
        # Sol
        creer_panneau("Sol", L + 2 * ep_mur, P + ep_mur, ep_mur,
                       (-ep_mur, 0, -ep_mur), coul_mur, transp_mur, grp_murs)
        # Plafond
        creer_panneau("Plafond", L + 2 * ep_mur, P + ep_mur, ep_mur,
                       (-ep_mur, 0, H), coul_mur, transp_mur, grp_murs)

    # ===================================================================
    #  CALCUL DES LARGEURS
    # ===================================================================
    largeurs = calculer_largeurs_compartiments(config)
    nb_comp = len(config["compartiments"])

    App.Console.PrintMessage(f"\n{'='*60}\n")
    App.Console.PrintMessage(f"  PLACARD v1.6 - Tasseaux rayon_haut/rayons séparés\n")
    App.Console.PrintMessage(f"  Construction du placard {L}x{H}x{P}mm\n")
    App.Console.PrintMessage(f"  {nb_comp} compartiments: {[f'{l:.0f}mm' for l in largeurs]}\n")
    App.Console.PrintMessage(f"{'='*60}\n\n")

    # Position X courante (de gauche à droite)
    x_courant = 0.0

    # ===================================================================
    #  RAYON HAUT (toute largeur, sur tasseaux)
    # ===================================================================
    if config["rayon_haut"]:
        z_rayon_haut = H - config["rayon_haut_position"]
        prof_rayon_haut = P - config["panneau_rayon_haut"]["chant_epaisseur"]
        chant_ep = config["panneau_rayon_haut"]["chant_epaisseur"]

        # Chant avant du rayon haut (face avant = Y=0)
        creer_panneau(
            "Chant_Rayon_Haut", L, chant_ep, ep_rayon_haut,
            (0, 0, z_rayon_haut),
            config["panneau_rayon_haut"]["chant_couleur_rgb"],
            group=grp_rayons
        )

        # Rayon haut (derrière le chant, vers le mur du fond)
        creer_panneau(
            "Rayon_Haut", L, prof_rayon_haut, ep_rayon_haut,
            (0, chant_ep, z_rayon_haut),
            config["panneau_rayon_haut"]["couleur_rgb"],
            group=grp_rayons
        )

        fiche.ajouter_piece(PieceInfo(
            "Rayon haut (toute largeur)", L, prof_rayon_haut, ep_rayon_haut,
            couleur_fab=config["panneau_rayon_haut"]["couleur_fab"],
            chant_desc=f"Avant {chant_ep}mm",
            notes="Posé sur tasseaux"
        ))

        # --- Tasseaux du rayon haut ---
        # Les tasseaux sous le rayon haut sont maintenant gérés par compartiment
        # via tasseau_gauche / tasseau_droite

        # Tasseaux sur les séparations (si sous_rayon) - aussi géré par compartiment

    # ===================================================================
    #  BOUCLE : SÉPARATIONS ET COMPARTIMENTS
    # ===================================================================
    positions_separations = []  # [(x_centre, mode), ...]

    for comp_idx in range(nb_comp):
        comp = config["compartiments"][comp_idx]
        larg_comp = largeurs[comp_idx]

        App.Console.PrintMessage(f"  Compartiment {comp_idx + 1}: "
                                  f"largeur={larg_comp:.0f}mm, "
                                  f"rayons={comp['rayons']}\n")

        # Position X du compartiment
        x_debut_comp = x_courant
        x_fin_comp = x_courant + larg_comp

        # ---------------------------------------------------------------
        #  Panneau mur latéral (optionnel, remplace applique)
        # ---------------------------------------------------------------
        if comp.get("panneau_mur_gauche", False) and comp_idx == 0:
            pm = config["panneau_mur"]
            h_panneau_mur = H
            if config["rayon_haut"]:
                h_panneau_mur = H - config["rayon_haut_position"]
            # Chant avant (Y=0)
            creer_panneau(
                f"Chant_Panneau_Mur_Gauche", pm["epaisseur"],
                pm["chant_epaisseur"], h_panneau_mur,
                (0, 0, 0),
                pm["chant_couleur_rgb"], group=grp_panneaux_mur
            )
            # Panneau (après le chant, vers le mur du fond)
            pm_obj = creer_panneau(
                f"Panneau_Mur_Gauche", pm["epaisseur"], P - pm["chant_epaisseur"],
                h_panneau_mur,
                (0, pm["chant_epaisseur"], 0), pm["couleur_rgb"], group=grp_panneaux_mur
            )

            # Rainures crémaillères dans la face intérieure (côté X+)
            if comp["rayons"] > 0:
                ce = config["crem_encastree"]
                saillie_pm = ce.get("saillie", 0)
                prof_enc_pm = ce["epaisseur"] - saillie_pm
                for y_pos in [
                    ce["retrait_avant"],
                    P - ce["retrait_arriere"] - ce["largeur"]
                ]:
                    pm_obj = creer_rainure_dans_panneau(
                        pm_obj,
                        pm["epaisseur"] - prof_enc_pm, y_pos, 0,
                        prof_enc_pm, ce["largeur"], h_panneau_mur,
                        nom_rainure="Rain_PM_G"
                    )
                if pm_obj.Name != "Panneau_Mur_Gauche":
                    grp_panneaux_mur.addObject(pm_obj)

            fiche.ajouter_piece(PieceInfo(
                "Panneau mur gauche", h_panneau_mur,
                P - pm["chant_epaisseur"], pm["epaisseur"],
                couleur_fab=pm["couleur_fab"],
                chant_desc=f"Avant {pm['chant_epaisseur']}mm",
                notes="Fixé au mur, crémaillères encastrées"
            ))

        if comp.get("panneau_mur_droite", False) and comp_idx == nb_comp - 1:
            pm = config["panneau_mur"]
            h_panneau_mur = H
            if config["rayon_haut"]:
                h_panneau_mur = H - config["rayon_haut_position"]
            # Chant avant (Y=0)
            creer_panneau(
                f"Chant_Panneau_Mur_Droit", pm["epaisseur"],
                pm["chant_epaisseur"], h_panneau_mur,
                (L - pm["epaisseur"], 0, 0),
                pm["chant_couleur_rgb"], group=grp_panneaux_mur
            )
            # Panneau (après le chant, vers le mur du fond)
            pm_obj_d = creer_panneau(
                f"Panneau_Mur_Droit", pm["epaisseur"],
                P - pm["chant_epaisseur"], h_panneau_mur,
                (L - pm["epaisseur"], pm["chant_epaisseur"], 0), pm["couleur_rgb"],
                group=grp_panneaux_mur
            )

            # Rainures crémaillères dans la face intérieure (côté X-)
            if comp["rayons"] > 0:
                ce = config["crem_encastree"]
                saillie_pm = ce.get("saillie", 0)
                prof_enc_pm = ce["epaisseur"] - saillie_pm
                for y_pos in [
                    ce["retrait_avant"],
                    P - ce["retrait_arriere"] - ce["largeur"]
                ]:
                    pm_obj_d = creer_rainure_dans_panneau(
                        pm_obj_d,
                        L - pm["epaisseur"], y_pos, 0,
                        prof_enc_pm, ce["largeur"], h_panneau_mur,
                        nom_rainure="Rain_PM_D"
                    )
                if pm_obj_d.Name != "Panneau_Mur_Droit":
                    grp_panneaux_mur.addObject(pm_obj_d)

            fiche.ajouter_piece(PieceInfo(
                "Panneau mur droit", h_panneau_mur,
                P - pm["chant_epaisseur"], pm["epaisseur"],
                couleur_fab=pm["couleur_fab"],
                chant_desc=f"Avant {pm['chant_epaisseur']}mm",
                notes="Fixé au mur, crémaillères encastrées"
            ))

        # ---------------------------------------------------------------
        #  Crémaillères du compartiment (PAIRE : avant + arrière)
        #  Les crémaillères encastrées sont enfoncées dans le panneau
        #  et ne dépassent que de "saillie" mm.
        #  Les rainures sont creusées dans les panneaux par soustraction.
        # ---------------------------------------------------------------
        if comp["rayons"] > 0:
            z_base_crem = 0
            z_haut_crem = H
            if config["rayon_haut"]:
                z_haut_crem = H - config["rayon_haut_position"]
            h_crem = z_haut_crem - z_base_crem

            ce = config["crem_encastree"]
            saillie = ce.get("saillie", 0)
            prof_encastrement = ce["epaisseur"] - saillie

            # --- Crémaillère gauche (paire avant + arrière) ---
            crem_g = comp.get("type_crem_gauche")
            panneau_mur_g = comp.get("panneau_mur_gauche", False)

            if panneau_mur_g:
                # Encastrée dans panneau mur gauche (face intérieure = côté X+)
                pm_ep = config["panneau_mur"]["epaisseur"]
                x_crem_g = x_debut_comp + pm_ep - ce["epaisseur"]
                App.Console.PrintMessage(
                    f"    DEBUG Crem PM gauche: panneau=[{x_debut_comp},{x_debut_comp+pm_ep}], "
                    f"crem=[{x_crem_g},{x_crem_g+ce['epaisseur']}], "
                    f"saillie={saillie}, prof_enc={prof_encastrement}\n"
                )
                for i, y_pos in enumerate([
                    ce["retrait_avant"],
                    P - ce["retrait_arriere"] - ce["largeur"]
                ]):
                    pos_label = "Arr" if i == 0 else "Avt"
                    creer_cremaillere(
                        f"Crem_Enc_G_{pos_label}_C{comp_idx+1}", h_crem,
                        ce["largeur"], ce["epaisseur"],
                        (x_crem_g, y_pos, z_base_crem),
                        ce["couleur_rgb"], grp_cremailleres
                    )
                fiche.ajouter_quincaillerie(
                    f"Crémaillère encastrée (C{comp_idx+1} gauche, panneau mur)", 2,
                    f"L={h_crem}mm, encastrement {ce['largeur']}x{prof_encastrement}mm, saillie {saillie}mm"
                )
                # Les rainures dans le panneau mur seront gérées via panneau_mur_rainures

            elif crem_g == "encastree":
                # Encastrée dans la séparation de gauche (ou panneau précédent)
                # La séparation qui borde ce compartiment à gauche:
                #   si comp_idx > 0 : c'est separations[comp_idx-1] à x_debut_comp - ep_sep
                # La crémaillère s'enfonce dans la face droite de cette séparation
                x_crem_g = x_debut_comp - prof_encastrement
                for i, y_pos in enumerate([
                    ce["retrait_avant"],
                    P - ce["retrait_arriere"] - ce["largeur"]
                ]):
                    pos_label = "Arr" if i == 0 else "Avt"
                    creer_cremaillere(
                        f"Crem_Enc_G_{pos_label}_C{comp_idx+1}", h_crem,
                        ce["largeur"], ce["epaisseur"],
                        (x_crem_g, y_pos, z_base_crem),
                        ce["couleur_rgb"], grp_cremailleres
                    )
                fiche.ajouter_quincaillerie(
                    f"Crémaillère encastrée (C{comp_idx+1} gauche)", 2,
                    f"L={h_crem}mm, encastrement {ce['largeur']}x{prof_encastrement}mm, saillie {saillie}mm"
                )

            elif crem_g == "applique" and not panneau_mur_g:
                ca = config["crem_applique"]
                for i, y_pos in enumerate([
                    ca["retrait_avant"],
                    P - ca["retrait_arriere"] - ca["largeur"]
                ]):
                    pos_label = "Arr" if i == 0 else "Avt"
                    creer_cremaillere(
                        f"Crem_App_G_{pos_label}_C{comp_idx+1}", h_crem,
                        ca["largeur"], ca["epaisseur_saillie"],
                        (x_debut_comp, y_pos, z_base_crem),
                        ca["couleur_rgb"], grp_cremailleres
                    )
                fiche.ajouter_quincaillerie(
                    f"Crémaillère applique (C{comp_idx+1} gauche)", 2,
                    f"L={h_crem}mm, largeur {ca['largeur']}mm, "
                    f"saillie {ca['epaisseur_saillie']}mm"
                )

            # --- Crémaillère droite (paire avant + arrière) ---
            crem_d = comp.get("type_crem_droite")
            panneau_mur_d = comp.get("panneau_mur_droite", False)

            if panneau_mur_d:
                # Encastrée dans panneau mur droit (face intérieure = côté X-)
                pm_ep = config["panneau_mur"]["epaisseur"]
                x_crem_d = x_fin_comp - pm_ep - saillie
                App.Console.PrintMessage(
                    f"    DEBUG Crem PM droit: panneau=[{x_fin_comp-pm_ep},{x_fin_comp}], "
                    f"crem=[{x_crem_d},{x_crem_d+ce['epaisseur']}], "
                    f"saillie={saillie}, prof_enc={prof_encastrement}\n"
                )
                for i, y_pos in enumerate([
                    ce["retrait_avant"],
                    P - ce["retrait_arriere"] - ce["largeur"]
                ]):
                    pos_label = "Arr" if i == 0 else "Avt"
                    creer_cremaillere(
                        f"Crem_Enc_D_{pos_label}_C{comp_idx+1}", h_crem,
                        ce["largeur"], ce["epaisseur"],
                        (x_crem_d, y_pos, z_base_crem),
                        ce["couleur_rgb"], grp_cremailleres
                    )
                fiche.ajouter_quincaillerie(
                    f"Crémaillère encastrée (C{comp_idx+1} droite, panneau mur)", 2,
                    f"L={h_crem}mm, encastrement {ce['largeur']}x{prof_encastrement}mm, saillie {saillie}mm"
                )

            elif crem_d == "encastree":
                # Encastrée dans la séparation de droite
                # La séparation est à x_fin_comp, face gauche à x_fin_comp
                # La crémaillère s'enfonce dans la face gauche
                x_crem_d = x_fin_comp + prof_encastrement - ce["epaisseur"]
                for i, y_pos in enumerate([
                    ce["retrait_avant"],
                    P - ce["retrait_arriere"] - ce["largeur"]
                ]):
                    pos_label = "Arr" if i == 0 else "Avt"
                    creer_cremaillere(
                        f"Crem_Enc_D_{pos_label}_C{comp_idx+1}", h_crem,
                        ce["largeur"], ce["epaisseur"],
                        (x_crem_d, y_pos, z_base_crem),
                        ce["couleur_rgb"], grp_cremailleres
                    )
                fiche.ajouter_quincaillerie(
                    f"Crémaillère encastrée (C{comp_idx+1} droite)", 2,
                    f"L={h_crem}mm, encastrement {ce['largeur']}x{prof_encastrement}mm, saillie {saillie}mm"
                )

            elif crem_d == "applique" and not panneau_mur_d:
                ca = config["crem_applique"]
                for i, y_pos in enumerate([
                    ca["retrait_avant"],
                    P - ca["retrait_arriere"] - ca["largeur"]
                ]):
                    pos_label = "Arr" if i == 0 else "Avt"
                    creer_cremaillere(
                        f"Crem_App_D_{pos_label}_C{comp_idx+1}", h_crem,
                        ca["largeur"], ca["epaisseur_saillie"],
                        (x_fin_comp - ca["epaisseur_saillie"],
                         y_pos, z_base_crem),
                        ca["couleur_rgb"], grp_cremailleres
                    )
                fiche.ajouter_quincaillerie(
                    f"Crémaillère applique (C{comp_idx+1} droite)", 2,
                    f"L={h_crem}mm, largeur {ca['largeur']}mm, "
                    f"saillie {ca['epaisseur_saillie']}mm"
                )

        # ---------------------------------------------------------------
        #  Rayons du compartiment
        # ---------------------------------------------------------------
        if comp["rayons"] > 0:
            prof_rayon, larg_rayon = calculer_dimensions_rayon(
                config, comp_idx, larg_comp
            )
            chant_ep = config["panneau_rayon"]["chant_epaisseur"]

            App.Console.PrintMessage(
                f"    Rayon C{comp_idx+1}: larg_comp={larg_comp:.1f}, "
                f"larg_rayon={larg_rayon:.1f}, prof_rayon={prof_rayon:.1f}\n"
            )

            # Zone de répartition des rayons
            z_base_rayons = 0
            z_haut_rayons = H
            if config["rayon_haut"]:
                z_haut_rayons = H - config["rayon_haut_position"] - ep_rayon_haut

            # Répartition régulière des rayons
            nb_rayons = comp["rayons"]
            espace = (z_haut_rayons - z_base_rayons) / (nb_rayons + 1)

            # Offset X du rayon (en tenant compte des crémaillères et panneaux mur)
            x_rayon = x_debut_comp
            crem_g = comp.get("type_crem_gauche")
            panneau_mur_g = comp.get("panneau_mur_gauche", False)
            ce_offset = config["crem_encastree"]
            saillie_offset = ce_offset.get("saillie", 0)
            if panneau_mur_g:
                # Panneau mur + crémaillère encastrée : épaisseur panneau + saillie + jeu
                x_rayon += (config["panneau_mur"]["epaisseur"]
                            + saillie_offset
                            + ce_offset["jeu_rayon"])
            elif crem_g == "encastree":
                # Crémaillère encastrée dans séparation : saillie + jeu
                x_rayon += saillie_offset + ce_offset["jeu_rayon"]
            elif crem_g == "applique":
                x_rayon += (config["crem_applique"]["epaisseur_saillie"]
                            + config["crem_applique"]["jeu_rayon"])

            for r_idx in range(nb_rayons):
                z_rayon = z_base_rayons + espace * (r_idx + 1)

                # Chant avant (Y=0)
                creer_panneau(
                    f"Chant_Rayon_C{comp_idx+1}_R{r_idx+1}",
                    larg_rayon, chant_ep, ep_rayon,
                    (x_rayon, 0, z_rayon),
                    config["panneau_rayon"]["chant_couleur_rgb"],
                    group=grp_rayons
                )

                # Rayon (après le chant, vers le mur du fond)
                creer_panneau(
                    f"Rayon_C{comp_idx+1}_R{r_idx+1}",
                    larg_rayon, prof_rayon, ep_rayon,
                    (x_rayon, chant_ep, z_rayon),
                    config["panneau_rayon"]["couleur_rgb"],
                    group=grp_rayons
                )

            fiche.ajouter_piece(PieceInfo(
                f"Rayon compartiment {comp_idx+1}",
                larg_rayon, prof_rayon, ep_rayon,
                couleur_fab=config["panneau_rayon"]["couleur_fab"],
                chant_desc=f"Avant {chant_ep}mm",
                quantite=nb_rayons,
                notes=f"Sur crémaillères"
            ))

        # ---------------------------------------------------------------
        #  Tasseaux du compartiment (fixés sur mur/séparation/panneau mur)
        #  4 bools indépendants par compartiment:
        #    tasseau_rayon_haut_gauche / _droite : sous le rayon haut
        #    tasseau_rayons_gauche / _droite     : sous chaque rayon
        # ---------------------------------------------------------------
        trh_g = comp.get("tasseau_rayon_haut_gauche", False)
        trh_d = comp.get("tasseau_rayon_haut_droite", False)
        tr_g = comp.get("tasseau_rayons_gauche", False)
        tr_d = comp.get("tasseau_rayons_droite", False)

        if trh_g or trh_d or tr_g or tr_d:
            tass = config["tasseau"]
            longueur_tasseau = P - config["panneau_rayon"]["chant_epaisseur"] - tass["retrait_avant"]
            y_tass = P - longueur_tasseau  # Tasseau collé au mur du fond

            # --- Position X gauche ---
            if comp_idx == 0:
                if comp.get("panneau_mur_gauche", False):
                    x_tass_g = config["panneau_mur"]["epaisseur"]
                else:
                    x_tass_g = 0
            else:
                x_tass_g = x_debut_comp

            # --- Position X droite ---
            if comp_idx == nb_comp - 1:
                if comp.get("panneau_mur_droite", False):
                    x_tass_d = L - config["panneau_mur"]["epaisseur"] - tass["section_l"]
                else:
                    x_tass_d = L - tass["section_l"]
            else:
                x_tass_d = x_fin_comp - tass["section_l"]

            nb_tasseaux_g = 0
            nb_tasseaux_d = 0

            # --- Tasseaux sous le rayon haut ---
            if config["rayon_haut"] and (trh_g or trh_d):
                z_rh = H - config["rayon_haut_position"]
                z_tass_rh = z_rh - tass["section_h"]

                if trh_g:
                    creer_tasseau_bisaute(
                        f"Tasseau_C{comp_idx+1}_G_rayon_haut",
                        longueur_tasseau,
                        tass["section_h"], tass["section_l"],
                        tass["biseau_longueur"],
                        (x_tass_g, y_tass, z_tass_rh),
                        tass["couleur_rgb"], grp_tasseaux
                    )
                    nb_tasseaux_g += 1

                if trh_d:
                    creer_tasseau_bisaute(
                        f"Tasseau_C{comp_idx+1}_D_rayon_haut",
                        longueur_tasseau,
                        tass["section_h"], tass["section_l"],
                        tass["biseau_longueur"],
                        (x_tass_d, y_tass, z_tass_rh),
                        tass["couleur_rgb"], grp_tasseaux
                    )
                    nb_tasseaux_d += 1

            # --- Tasseaux sous les rayons du compartiment ---
            if comp["rayons"] > 0 and (tr_g or tr_d):
                z_base_rayons = 0
                z_haut_rayons = H
                if config["rayon_haut"]:
                    z_haut_rayons = H - config["rayon_haut_position"] - ep_rayon_haut
                nb_rayons = comp["rayons"]
                espace = (z_haut_rayons - z_base_rayons) / (nb_rayons + 1)

                for r_idx in range(nb_rayons):
                    z_r = z_base_rayons + espace * (r_idx + 1)
                    z_tass_r = z_r - tass["section_h"]

                    if tr_g:
                        creer_tasseau_bisaute(
                            f"Tasseau_C{comp_idx+1}_G_R{r_idx+1}",
                            longueur_tasseau,
                            tass["section_h"], tass["section_l"],
                            tass["biseau_longueur"],
                            (x_tass_g, y_tass, z_tass_r),
                            tass["couleur_rgb"], grp_tasseaux
                        )
                        nb_tasseaux_g += 1

                    if tr_d:
                        creer_tasseau_bisaute(
                            f"Tasseau_C{comp_idx+1}_D_R{r_idx+1}",
                            longueur_tasseau,
                            tass["section_h"], tass["section_l"],
                            tass["biseau_longueur"],
                            (x_tass_d, y_tass, z_tass_r),
                            tass["couleur_rgb"], grp_tasseaux
                        )
                        nb_tasseaux_d += 1

            # Fiche de fabrication
            if nb_tasseaux_g > 0:
                support = "mur" if comp_idx == 0 else f"séparation {comp_idx}"
                if comp_idx == 0 and comp.get("panneau_mur_gauche", False):
                    support = "panneau mur gauche"
                fiche.ajouter_piece(PieceInfo(
                    f"Tasseau C{comp_idx+1} gauche ({support})",
                    longueur_tasseau, tass["section_l"], tass["section_h"],
                    materiau="Tasseau bois", quantite=nb_tasseaux_g,
                    notes=f"Bisauté en bout, fixé sur {support}"
                ))
            if nb_tasseaux_d > 0:
                support = "mur" if comp_idx == nb_comp - 1 else f"séparation {comp_idx+1}"
                if comp_idx == nb_comp - 1 and comp.get("panneau_mur_droite", False):
                    support = "panneau mur droit"
                fiche.ajouter_piece(PieceInfo(
                    f"Tasseau C{comp_idx+1} droite ({support})",
                    longueur_tasseau, tass["section_l"], tass["section_h"],
                    materiau="Tasseau bois", quantite=nb_tasseaux_d,
                    notes=f"Bisauté en bout, fixé sur {support}"
                ))

        # ---------------------------------------------------------------
        #  Séparation après ce compartiment (sauf le dernier)
        # ---------------------------------------------------------------
        if comp_idx < nb_comp - 1:
            sep = config["separations"][comp_idx]
            x_sep = x_fin_comp  # Position X de la séparation

            # Hauteur de la séparation
            if sep["mode"] == "toute_hauteur":
                z_sep = 0
                h_sep = H
            elif sep["mode"] == "sous_rayon":
                z_sep = 0
                if config["rayon_haut"]:
                    h_sep = H - config["rayon_haut_position"]
                else:
                    h_sep = H
            else:
                z_sep = 0
                h_sep = H

            prof_sep = P - config["panneau_separation"]["chant_epaisseur"]
            chant_ep_sep = config["panneau_separation"]["chant_epaisseur"]

            # Chant avant de la séparation (Y=0)
            creer_panneau(
                f"Chant_Sep_{comp_idx+1}",
                ep_sep, chant_ep_sep, h_sep,
                (x_sep, 0, z_sep),
                config["panneau_separation"]["chant_couleur_rgb"],
                group=grp_separations
            )

            # Panneau de séparation (après le chant, vers le mur du fond)
            sep_obj = creer_panneau(
                f"Separation_{comp_idx+1}",
                ep_sep, prof_sep, h_sep,
                (x_sep, chant_ep_sep, z_sep),
                config["panneau_separation"]["couleur_rgb"],
                group=grp_separations
            )

            # --- Rainures crémaillères dans la séparation ---
            ce = config["crem_encastree"]
            saillie = ce.get("saillie", 0)
            prof_encastrement = ce["epaisseur"] - saillie

            # Hauteur crémaillère
            h_crem_sep = h_sep
            z_base_crem_sep = z_sep

            # Face gauche de la séparation (côté compartiment courant)
            # Vérifier si le compartiment courant a crem_droite encastrée
            if comp.get("type_crem_droite") == "encastree":
                for y_pos in [
                    ce["retrait_avant"],
                    P - ce["retrait_arriere"] - ce["largeur"]
                ]:
                    sep_obj = creer_rainure_dans_panneau(
                        sep_obj,
                        x_sep, y_pos, z_base_crem_sep,
                        prof_encastrement, ce["largeur"], h_crem_sep,
                        nom_rainure=f"Rain_Sep{comp_idx+1}_G"
                    )
                fiche.ajouter_quincaillerie(
                    f"Rainure crém. encastrée (Sep {comp_idx+1}, face gauche)", 2,
                    f"Rainure {ce['largeur']}x{prof_encastrement}mm (avant + arrière)"
                )

            # Face droite de la séparation (côté compartiment suivant)
            comp_next = config["compartiments"][comp_idx + 1]
            if comp_next.get("type_crem_gauche") == "encastree":
                for y_pos in [
                    ce["retrait_avant"],
                    P - ce["retrait_arriere"] - ce["largeur"]
                ]:
                    sep_obj = creer_rainure_dans_panneau(
                        sep_obj,
                        x_sep + ep_sep - prof_encastrement, y_pos,
                        z_base_crem_sep,
                        prof_encastrement, ce["largeur"], h_crem_sep,
                        nom_rainure=f"Rain_Sep{comp_idx+1}_D"
                    )
                fiche.ajouter_quincaillerie(
                    f"Rainure crém. encastrée (Sep {comp_idx+1}, face droite)", 2,
                    f"Rainure {ce['largeur']}x{prof_encastrement}mm (avant + arrière)"
                )

            # Remettre dans le groupe
            if sep_obj.Name != f"Separation_{comp_idx+1}":
                grp_separations.addObject(sep_obj)

            positions_separations.append((x_sep, sep["mode"]))

            fiche.ajouter_piece(PieceInfo(
                f"Séparation {comp_idx+1}",
                h_sep, prof_sep, ep_sep,
                couleur_fab=config["panneau_separation"]["couleur_fab"],
                chant_desc=f"Avant {chant_ep_sep}mm",
                notes=f"Mode: {sep['mode']}, rainures crémaillères"
            ))


        # Avancer au prochain compartiment
        x_courant = x_fin_comp
        if comp_idx < nb_comp - 1:
            x_courant += ep_sep

    # ===================================================================
    #  FICHE DE FABRICATION
    # ===================================================================
    fiche_texte = fiche.generer_texte(config)
    App.Console.PrintMessage("\n" + fiche_texte + "\n")

    if config["export_fiche"]:
        dossier = config["dossier_export"]
        if not dossier:
            dossier = os.path.expanduser("~")
        
        fichier_fiche = os.path.join(dossier, "fiche_fabrication_placard.txt")
        with open(fichier_fiche, "w", encoding="utf-8") as f:
            f.write(fiche_texte)
        App.Console.PrintMessage(f"\n✅ Fiche exportée: {fichier_fiche}\n")

    # ===================================================================
    #  FINALISATION
    # ===================================================================
    doc.recompute()

    if Gui.ActiveDocument:
        Gui.ActiveDocument.ActiveView.viewFront()
        Gui.SendMsgToActiveView("ViewFit")

    App.Console.PrintMessage("\n✅ Construction terminée!\n")

    return doc, fiche


# ===========================================================================
#  POINT D'ENTRÉE
# ===========================================================================

