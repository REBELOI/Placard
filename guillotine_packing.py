#!/usr/bin/env python3
"""
guillotine_packing — Optimisation de debit de panneaux par coupe guillotine.

Module standalone sans dependance externe (uniquement la stdlib Python 3.10+).
Peut etre copie dans n'importe quel projet pour optimiser la decoupe de
pieces rectangulaires dans des panneaux de stock.

Algorithme : Guillotine Bin Packing — Best Fit Decreasing.

Contraintes atelier :
- Coupe guillotine (chaque trait traverse le panneau de bord a bord)
- Delignage (1er trait pour redresser un bord)
- Surcote de debit (marge par cote)
- Trait de scie (espace perdu entre pieces)
- Sens du fil par piece (rotation interdite si decor bois)

Usage :
    from guillotine_packing import (
        ParametresDebit, PieceDebit, optimiser_debit,
    )

    # Definir les parametres de decoupe
    params = ParametresDebit(
        panneau_longueur=2800,   # longueur panneau brut (mm)
        panneau_largeur=2070,    # largeur panneau brut (mm)
        trait_scie=4.0,          # largeur du trait de scie (mm)
        surcote=2.0,             # surcote par cote (mm)
        delignage=10.0,          # delignage initial (mm)
        sens_fil=True,           # respect global du sens du fil
    )

    # Definir les pieces a decouper
    pieces = [
        PieceDebit("Rayon", "R1", 800, 500, 19, "Chene", quantite=6),
        PieceDebit("Separation", "S1", 2400, 580, 19, "Chene", quantite=2),
        PieceDebit("Fond", "F1", 1200, 600, 10, "Blanc", quantite=1, sens_fil=False),
    ]

    # Optimiser
    plans, hors_gabarit = optimiser_debit(pieces, params)

    # Exploiter les resultats
    for i, plan in enumerate(plans, 1):
        print(f"Panneau {i}: {plan.couleur} ep.{plan.epaisseur}mm "
              f"— {len(plan.placements)} pieces, {plan.pct_chute:.1f}% chute")
        for p in plan.placements:
            rot = " (pivote)" if p.rotation else ""
            print(f"  {p.piece.reference} {p.piece.nom} "
                  f"{p.longueur_debit:.0f}x{p.largeur_debit:.0f}mm "
                  f"@ ({p.x:.0f}, {p.y:.0f}){rot}")

    for p in hors_gabarit:
        print(f"HORS GABARIT: {p.nom} {p.longueur:.0f}x{p.largeur:.0f}mm")
"""

from __future__ import annotations

from dataclasses import dataclass, field

__version__ = "1.0.0"
__all__ = [
    "PANNEAU_STD_LONGUEUR",
    "PANNEAU_STD_LARGEUR",
    "ParametresDebit",
    "PieceDebit",
    "ZoneLibre",
    "Placement",
    "PlanDecoupe",
    "optimiser_debit",
]

# Taille standard des panneaux bruts (mm)
PANNEAU_STD_LONGUEUR: float = 2800
PANNEAU_STD_LARGEUR: float = 2070


# =========================================================================
#  DATACLASSES
# =========================================================================

@dataclass
class ParametresDebit:
    """Parametres de decoupe.

    Attributs:
        trait_scie:       Largeur du trait de scie en mm (espace perdu entre pieces).
        surcote:          Surcote ajoutee par cote de chaque piece en mm.
        delignage:        Bande retiree sur un bord pour redresser le panneau, en mm.
        panneau_longueur: Longueur du panneau brut de stock en mm.
        panneau_largeur:  Largeur du panneau brut de stock en mm.
        sens_fil:         Si True, interrupteur global de respect du sens du fil.
                          Si False, toutes les pieces peuvent pivoter.
    """
    trait_scie: float = 4.0
    surcote: float = 2.0
    delignage: float = 10.0
    panneau_longueur: float = PANNEAU_STD_LONGUEUR
    panneau_largeur: float = PANNEAU_STD_LARGEUR
    sens_fil: bool = True


@dataclass
class PieceDebit:
    """Piece rectangulaire a decouper.

    Attributs:
        nom:       Designation de la piece (ex: "Rayon", "Separation").
        reference: Identifiant unique (ex: "P1/A1/N01").
        longueur:  Longueur finie de la piece en mm (plus grande dimension).
        largeur:   Largeur finie de la piece en mm (plus petite dimension).
        epaisseur: Epaisseur du panneau en mm.
        couleur:   Reference couleur/materiau (les pieces sont regroupees par
                   (epaisseur, couleur) pour le debit).
        quantite:  Nombre d'exemplaires identiques a decouper.
        sens_fil:  Si True, la piece ne peut pas etre pivotee a 90 degres
                   (decor bois avec veinage directionnel).
    """
    nom: str
    reference: str
    longueur: float
    largeur: float
    epaisseur: float
    couleur: str
    quantite: int = 1
    sens_fil: bool = True


@dataclass
class ZoneLibre:
    """Zone libre rectangulaire dans un panneau de stock."""
    x: float
    y: float
    w: float
    h: float

    @property
    def surface(self) -> float:
        return self.w * self.h


@dataclass
class Placement:
    """Position d'une piece placee sur un panneau de stock.

    Attributs:
        piece:          La PieceDebit placee.
        x:              Position X du coin inferieur gauche (mm).
        y:              Position Y du coin inferieur gauche (mm).
        longueur_debit: Longueur de debit (longueur finie + 2 * surcote).
        largeur_debit:  Largeur de debit (largeur finie + 2 * surcote).
        rotation:       True si la piece a ete pivotee de 90 degres.
    """
    piece: PieceDebit
    x: float
    y: float
    longueur_debit: float
    largeur_debit: float
    rotation: bool = False


@dataclass
class PlanDecoupe:
    """Plan de decoupe pour un panneau de stock.

    Regroupe les placements effectues sur un meme panneau physique.
    Tous les placements ont la meme epaisseur et couleur.

    Attributs:
        panneau_l:    Longueur utile du panneau (apres delignage) en mm.
        panneau_w:    Largeur utile du panneau (apres delignage) en mm.
        epaisseur:    Epaisseur du panneau en mm.
        couleur:      Reference couleur/materiau.
        placements:   Liste des pieces placees.
        zones_libres: Zones restantes (usage interne de l'algorithme).
    """
    panneau_l: float
    panneau_w: float
    epaisseur: float
    couleur: str
    placements: list[Placement] = field(default_factory=list)
    zones_libres: list[ZoneLibre] = field(default_factory=list, repr=False)

    @property
    def surface_panneau(self) -> float:
        """Surface du panneau utile en m²."""
        return self.panneau_l * self.panneau_w / 1e6

    @property
    def surface_pieces(self) -> float:
        """Surface des pieces placees en m²."""
        return sum(p.longueur_debit * p.largeur_debit for p in self.placements) / 1e6

    @property
    def pct_chute(self) -> float:
        """Pourcentage de chute."""
        if self.surface_panneau <= 0:
            return 100.0
        return (1 - self.surface_pieces / self.surface_panneau) * 100


# =========================================================================
#  ALGORITHME GUILLOTINE BIN PACKING
# =========================================================================

def optimiser_debit(
    pieces: list[PieceDebit],
    params: ParametresDebit,
) -> tuple[list[PlanDecoupe], list[PieceDebit]]:
    """Optimise le debit de panneaux par algorithme guillotine.

    Regroupe les pieces par (epaisseur, couleur), puis applique
    un bin packing guillotine Best Fit Decreasing pour chaque groupe.

    Le sens du fil effectif de chaque piece est : ``params.sens_fil AND piece.sens_fil``.
    Si le parametre global ``params.sens_fil`` est False, toutes les pieces
    peuvent pivoter independamment de leur reglage individuel.

    Args:
        pieces: Liste de PieceDebit a placer.
        params: Parametres de decoupe (dimensions panneau, trait de scie, etc.).

    Returns:
        (plans_de_decoupe, pieces_hors_gabarit)
        - plans_de_decoupe: liste de PlanDecoupe, chacun representant un panneau.
        - pieces_hors_gabarit: pieces trop grandes pour le panneau de stock.
    """
    # Zone utile du panneau (apres delignage)
    panneau_utile_l = params.panneau_longueur - params.delignage
    panneau_utile_w = params.panneau_largeur - params.delignage

    # Eclater quantites et regrouper par (epaisseur, couleur)
    groupes: dict[tuple, list[tuple[PieceDebit, float, float]]] = {}
    hors_gabarit: list[PieceDebit] = []

    for p in pieces:
        ld = p.longueur + 2 * params.surcote
        wd = p.largeur + 2 * params.surcote

        # sens_fil effectif : global ET par piece
        piece_sens_fil = params.sens_fil and p.sens_fil

        # Verifier si la piece rentre dans le panneau
        ok_normal = ld <= panneau_utile_l and wd <= panneau_utile_w
        ok_rotate = (not piece_sens_fil
                     and wd <= panneau_utile_l and ld <= panneau_utile_w)
        if not ok_normal and not ok_rotate:
            hors_gabarit.append(p)
            continue

        key = (p.epaisseur, p.couleur)
        for _ in range(p.quantite):
            piece_unit = PieceDebit(
                p.nom, p.reference, p.longueur, p.largeur,
                p.epaisseur, p.couleur, 1, sens_fil=piece_sens_fil,
            )
            groupes.setdefault(key, []).append((piece_unit, ld, wd))

    plans: list[PlanDecoupe] = []

    for (ep, couleur), group in groupes.items():
        # Trier par surface decroissante
        group.sort(key=lambda x: x[1] * x[2], reverse=True)

        plans_groupe = _bin_packing_guillotine(
            group, panneau_utile_l, panneau_utile_w,
            ep, couleur, params.trait_scie,
        )
        plans.extend(plans_groupe)

    return plans, hors_gabarit


# =========================================================================
#  FONCTIONS INTERNES
# =========================================================================

def _bin_packing_guillotine(
    pieces_debit: list[tuple[PieceDebit, float, float]],
    panneau_l: float, panneau_w: float,
    epaisseur: float, couleur: str,
    trait_scie: float,
) -> list[PlanDecoupe]:
    """Algorithme guillotine bin packing Best Fit Decreasing."""
    plans: list[PlanDecoupe] = []

    for piece, ld, wd in pieces_debit:
        placed = False
        piece_sens_fil = piece.sens_fil

        # Essayer de placer dans un panneau existant (best fit)
        best_plan = None
        best_zone_idx = -1
        best_rotation = False
        best_score = float('inf')

        for plan in plans:
            zone_idx, rotation, score = _trouver_meilleure_zone(
                plan.zones_libres, ld, wd, piece_sens_fil
            )
            if zone_idx >= 0 and score < best_score:
                best_score = score
                best_plan = plan
                best_zone_idx = zone_idx
                best_rotation = rotation

        if best_plan is not None:
            _effectuer_placement(
                best_plan, best_zone_idx, piece, ld, wd,
                best_rotation, trait_scie
            )
            placed = True

        if not placed:
            # Ouvrir un nouveau panneau
            plan = PlanDecoupe(panneau_l, panneau_w, epaisseur, couleur)
            plan.zones_libres = [ZoneLibre(0, 0, panneau_l, panneau_w)]

            zone_idx, rotation, _ = _trouver_meilleure_zone(
                plan.zones_libres, ld, wd, piece_sens_fil
            )
            if zone_idx >= 0:
                _effectuer_placement(
                    plan, zone_idx, piece, ld, wd, rotation, trait_scie
                )
                plans.append(plan)

    return plans


def _trouver_meilleure_zone(
    zones: list[ZoneLibre], ld: float, wd: float, sens_fil: bool
) -> tuple[int, bool, float]:
    """Trouve la zone libre la mieux adaptee. Retourne (index, rotation, score)."""
    best_idx = -1
    best_rotation = False
    best_score = float('inf')

    for i, zone in enumerate(zones):
        # Orientation normale
        if ld <= zone.w and wd <= zone.h:
            score = zone.surface - ld * wd
            if score < best_score:
                best_score = score
                best_idx = i
                best_rotation = False

        # Orientation pivotee
        if not sens_fil and wd <= zone.w and ld <= zone.h:
            score = zone.surface - ld * wd
            if score < best_score:
                best_score = score
                best_idx = i
                best_rotation = True

    return best_idx, best_rotation, best_score


def _effectuer_placement(
    plan: PlanDecoupe, zone_idx: int,
    piece: PieceDebit, ld: float, wd: float,
    rotation: bool, trait_scie: float
):
    """Place une piece dans la zone et decoupe les zones restantes."""
    zone = plan.zones_libres.pop(zone_idx)

    if rotation:
        piece_w, piece_h = wd, ld
    else:
        piece_w, piece_h = ld, wd

    plan.placements.append(Placement(
        piece=piece, x=zone.x, y=zone.y,
        longueur_debit=ld, largeur_debit=wd,
        rotation=rotation,
    ))

    ts = trait_scie

    # Coupe guillotine : choisir entre horizontal-first et vertical-first
    # Option A : coupe horizontale d'abord
    #   Droite = meme hauteur que piece, Dessus = pleine largeur
    zones_a: list[ZoneLibre] = []
    w_droite = zone.w - piece_w - ts
    if w_droite > 10:
        zones_a.append(ZoneLibre(zone.x + piece_w + ts, zone.y, w_droite, piece_h))
    h_dessus = zone.h - piece_h - ts
    if h_dessus > 10:
        zones_a.append(ZoneLibre(zone.x, zone.y + piece_h + ts, zone.w, h_dessus))

    # Option B : coupe verticale d'abord
    #   Dessus = meme largeur que piece, Droite = pleine hauteur
    zones_b: list[ZoneLibre] = []
    h_dessus_b = zone.h - piece_h - ts
    if h_dessus_b > 10:
        zones_b.append(ZoneLibre(zone.x, zone.y + piece_h + ts, piece_w, h_dessus_b))
    w_droite_b = zone.w - piece_w - ts
    if w_droite_b > 10:
        zones_b.append(ZoneLibre(zone.x + piece_w + ts, zone.y, w_droite_b, zone.h))

    # Choisir l'option qui donne la plus grande zone libre
    max_a = max((z.surface for z in zones_a), default=0)
    max_b = max((z.surface for z in zones_b), default=0)

    if max_a >= max_b:
        plan.zones_libres.extend(zones_a)
    else:
        plan.zones_libres.extend(zones_b)

    # Trier par surface croissante (best fit)
    plan.zones_libres.sort(key=lambda z: z.surface)


# =========================================================================
#  POINT D'ENTREE (demo)
# =========================================================================

if __name__ == "__main__":
    # Exemple d'utilisation standalone
    params = ParametresDebit(
        panneau_longueur=2800,
        panneau_largeur=2070,
        trait_scie=4.0,
        surcote=2.0,
        delignage=10.0,
        sens_fil=True,
    )

    pieces = [
        PieceDebit("Rayon", "R1", 800, 500, 19, "Chene clair", quantite=6),
        PieceDebit("Separation", "S1", 2400, 580, 19, "Chene clair", quantite=2),
        PieceDebit("Rayon haut", "RH1", 2980, 580, 22, "Chene clair", quantite=1),
        PieceDebit("Panneau mur", "PM1", 2200, 580, 19, "Chene clair", quantite=2),
        PieceDebit("Fond", "F1", 1200, 600, 10, "Blanc", quantite=1, sens_fil=False),
    ]

    plans, hors_gabarit = optimiser_debit(pieces, params)

    print(f"{'='*60}")
    print(f"  PLAN DE DEBIT — {len(plans)} panneau(x)")
    print(f"{'='*60}")

    for i, plan in enumerate(plans, 1):
        print(f"\n--- Panneau {i} : {plan.couleur} ep.{plan.epaisseur:.0f}mm "
              f"({plan.panneau_l:.0f} x {plan.panneau_w:.0f}mm) ---")
        print(f"    Pieces: {len(plan.placements)}, "
              f"Chute: {plan.pct_chute:.1f}%")
        for p in plan.placements:
            rot = " [pivote]" if p.rotation else ""
            print(f"    {p.piece.reference:>6} {p.piece.nom:<25} "
                  f"{p.longueur_debit:>6.0f} x {p.largeur_debit:>5.0f}mm "
                  f"@ ({p.x:>6.0f}, {p.y:>5.0f}){rot}")

    if hors_gabarit:
        print(f"\n--- HORS GABARIT ({len(hors_gabarit)}) ---")
        for p in hors_gabarit:
            print(f"    {p.reference} {p.nom} "
                  f"{p.longueur:.0f}x{p.largeur:.0f}mm ep.{p.epaisseur:.0f}mm")

    total_surface = sum(plan.surface_panneau for plan in plans)
    total_pieces = sum(plan.surface_pieces for plan in plans)
    print(f"\n{'='*60}")
    print(f"  Surface panneaux : {total_surface:.2f} m²")
    print(f"  Surface pieces   : {total_pieces:.2f} m²")
    if total_surface > 0:
        print(f"  Chute globale    : {(1 - total_pieces/total_surface)*100:.1f}%")
    print(f"{'='*60}")
