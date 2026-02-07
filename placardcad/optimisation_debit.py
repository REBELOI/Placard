"""
Optimisation de debit de panneaux.

Algorithme guillotine bin packing pour optimiser la decoupe
de pieces dans des panneaux de stock standard.

Contraintes atelier:
- Coupe guillotine (chaque trait traverse le panneau de bord a bord)
- Delignage (1er trait pour redresser un bord)
- Surcote de debit (marge par cote)
- Trait de scie (espace perdu entre pieces)
- Sens du fil (rotation interdite si decor bois)
"""

from dataclasses import dataclass, field

from .placard_builder import FicheFabrication

# Taille standard des panneaux bruts (mm)
PANNEAU_STD_LONGUEUR = 2800
PANNEAU_STD_LARGEUR = 2070


# =========================================================================
#  DATACLASSES
# =========================================================================

@dataclass
class ParametresDebit:
    """Parametres de decoupe."""
    trait_scie: float = 4.0
    surcote: float = 2.0
    delignage: float = 10.0
    panneau_longueur: float = PANNEAU_STD_LONGUEUR
    panneau_largeur: float = PANNEAU_STD_LARGEUR
    sens_fil: bool = True


@dataclass
class PieceDebit:
    """Piece a decouper."""
    nom: str
    reference: str
    longueur: float
    largeur: float
    epaisseur: float
    couleur: str
    quantite: int = 1


@dataclass
class ZoneLibre:
    """Zone libre rectangulaire dans un panneau."""
    x: float
    y: float
    w: float
    h: float

    @property
    def surface(self) -> float:
        return self.w * self.h


@dataclass
class Placement:
    """Position d'une piece sur un panneau."""
    piece: PieceDebit
    x: float
    y: float
    longueur_debit: float
    largeur_debit: float
    rotation: bool = False


@dataclass
class PlanDecoupe:
    """Plan de decoupe pour un panneau de stock."""
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
#  CONVERSION FICHE -> PIECES
# =========================================================================

def pieces_depuis_fiche(fiche: FicheFabrication,
                        projet_id: int = 0,
                        amenagement_id: int = 0) -> list[PieceDebit]:
    """Convertit une FicheFabrication en liste de PieceDebit."""
    pieces = []
    for i, p in enumerate(fiche.pieces, 1):
        ref = p.reference or f"P{projet_id}/A{amenagement_id}/N{i:02d}"
        pieces.append(PieceDebit(
            nom=p.nom,
            reference=ref,
            longueur=p.longueur,
            largeur=p.largeur,
            epaisseur=p.epaisseur,
            couleur=p.couleur_fab or "Standard",
            quantite=p.quantite,
        ))
    return pieces


# =========================================================================
#  ALGORITHME GUILLOTINE BIN PACKING
# =========================================================================

def optimiser_debit(pieces: list[PieceDebit],
                    params: ParametresDebit
                    ) -> tuple[list[PlanDecoupe], list[PieceDebit]]:
    """
    Optimise le debit de panneaux par algorithme guillotine.

    Regroupe les pieces par (epaisseur, couleur), puis applique
    un bin packing guillotine pour chaque groupe.

    Retourne (plans_de_decoupe, pieces_hors_gabarit).
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

        # Verifier si la piece rentre dans le panneau
        ok_normal = ld <= panneau_utile_l and wd <= panneau_utile_w
        ok_rotate = (not params.sens_fil
                     and wd <= panneau_utile_l and ld <= panneau_utile_w)
        if not ok_normal and not ok_rotate:
            hors_gabarit.append(p)
            continue

        key = (p.epaisseur, p.couleur)
        for _ in range(p.quantite):
            piece_unit = PieceDebit(
                p.nom, p.reference, p.longueur, p.largeur,
                p.epaisseur, p.couleur, 1
            )
            groupes.setdefault(key, []).append((piece_unit, ld, wd))

    plans: list[PlanDecoupe] = []

    for (ep, couleur), group in groupes.items():
        # Trier par surface decroissante
        group.sort(key=lambda x: x[1] * x[2], reverse=True)

        plans_groupe = _bin_packing_guillotine(
            group, panneau_utile_l, panneau_utile_w,
            ep, couleur, params.trait_scie, params.sens_fil
        )
        plans.extend(plans_groupe)

    return plans, hors_gabarit


def _bin_packing_guillotine(
    pieces_debit: list[tuple[PieceDebit, float, float]],
    panneau_l: float, panneau_w: float,
    epaisseur: float, couleur: str,
    trait_scie: float, sens_fil: bool
) -> list[PlanDecoupe]:
    """Algorithme guillotine bin packing Best Fit Decreasing."""
    plans: list[PlanDecoupe] = []

    for piece, ld, wd in pieces_debit:
        placed = False

        # Essayer de placer dans un panneau existant (best fit)
        best_plan = None
        best_zone_idx = -1
        best_rotation = False
        best_score = float('inf')

        for plan in plans:
            zone_idx, rotation, score = _trouver_meilleure_zone(
                plan.zones_libres, ld, wd, sens_fil
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
                plan.zones_libres, ld, wd, sens_fil
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
