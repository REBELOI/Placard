"""
Optimisation de debit de panneaux — wrapper PlacardCAD.

Ce module re-exporte le moteur standalone ``guillotine_packing``
et ajoute la fonction ``pieces_depuis_fiche`` qui fait le pont
entre la FicheFabrication de PlacardCAD et les PieceDebit du moteur.

Pour utiliser le moteur d'optimisation dans un autre projet,
importez directement ``guillotine_packing`` (aucune dependance).
"""

# Re-export complet du moteur standalone
from guillotine_packing import (  # noqa: F401
    PANNEAU_STD_LONGUEUR,
    PANNEAU_STD_LARGEUR,
    ParametresDebit,
    PieceDebit,
    ZoneLibre,
    Placement,
    PlanDecoupe,
    optimiser_debit,
)

from .placard_builder import FicheFabrication


# =========================================================================
#  CONVERSION FICHE -> PIECES (specifique PlacardCAD)
# =========================================================================

def pieces_depuis_fiche(fiche: FicheFabrication,
                        projet_id: int = 0,
                        amenagement_id: int = 0) -> list[PieceDebit]:
    """Convertit une FicheFabrication en liste de PieceDebit.

    Exclut les tasseaux (bois massif, pas de debit panneau).
    """
    pieces = []
    for i, p in enumerate(fiche.pieces, 1):
        # Les tasseaux sont du bois massif, pas du panneau a debiter
        if p.materiau and "tasseau" in p.materiau.lower():
            continue
        ref = p.reference or f"P{projet_id}/A{amenagement_id}/N{i:02d}"
        pieces.append(PieceDebit(
            nom=p.nom,
            reference=ref,
            longueur=p.longueur,
            largeur=p.largeur,
            epaisseur=p.epaisseur,
            couleur=p.couleur_fab or "Standard",
            quantite=p.quantite,
            sens_fil=getattr(p, "sens_fil", True),
        ))
    return pieces
