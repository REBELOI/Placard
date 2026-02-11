"""
Tests unitaires pour le constructeur de placard (geometrie 2D et fiche).
"""

import pytest
from placardcad.schema_parser import schema_vers_config
from placardcad.placard_builder import (
    generer_geometrie_2d, calculer_largeurs_compartiments,
    calculer_dimensions_rayon, Rect, PieceInfo, FicheFabrication,
)


def _config_2comp():
    """Configuration basique : 2 compartiments egaux."""
    schema = (
        "*-----------*-----------*\n"
        "|__________|__________|\n"
        "|__________|__________|"
    )
    return schema_vers_config(schema)


def _config_3comp():
    """Configuration basique : 3 compartiments egaux."""
    schema = (
        "*-----------*-----------*-----------*\n"
        "|__________|__________|__________|\n"
        "|__________|__________|__________|"
    )
    return schema_vers_config(schema)


class TestCalculLargeurs:
    """Tests du calcul des largeurs de compartiments."""

    def test_largeurs_egales(self):
        config = _config_2comp()
        largeurs = calculer_largeurs_compartiments(config)
        assert len(largeurs) == 2
        assert abs(largeurs[0] - largeurs[1]) < 1.0

    def test_largeurs_3_comp(self):
        config = _config_3comp()
        largeurs = calculer_largeurs_compartiments(config)
        assert len(largeurs) == 3
        total = sum(largeurs) + (len(largeurs) - 1) * config["panneau_separation"]["epaisseur"]
        assert abs(total - config["largeur"]) < 1.0

    def test_largeurs_dimensions_ratio(self):
        schema = (
            "*-----------*-----------*\n"
            "|__________|__________|\n"
            "500         800"
        )
        config = schema_vers_config(schema)
        largeurs = calculer_largeurs_compartiments(config)
        # Le ratio 500:800 doit etre respecte
        ratio = largeurs[0] / largeurs[1]
        assert abs(ratio - 500 / 800) < 0.01


class TestGenererGeometrie:
    """Tests de la generation de geometrie 2D."""

    def test_retourne_rects_et_fiche(self):
        config = _config_2comp()
        rects, fiche = generer_geometrie_2d(config)
        assert isinstance(rects, list)
        assert isinstance(fiche, FicheFabrication)
        assert len(rects) > 0
        assert len(fiche.pieces) > 0

    def test_types_elements_presents(self):
        config = _config_2comp()
        rects, _ = generer_geometrie_2d(config)
        types = {r.type_elem for r in rects}
        assert "mur" in types
        assert "sol" in types
        assert "separation" in types
        assert "rayon_haut" in types or "rayon" in types

    def test_nombre_separations(self):
        config = _config_2comp()
        rects, _ = generer_geometrie_2d(config)
        seps = [r for r in rects if r.type_elem == "separation"]
        assert len(seps) == 1  # 2 compartiments = 1 separation

    def test_nombre_separations_3comp(self):
        config = _config_3comp()
        rects, _ = generer_geometrie_2d(config)
        seps = [r for r in rects if r.type_elem == "separation"]
        assert len(seps) == 2  # 3 compartiments = 2 separations

    def test_rayons_par_compartiment(self):
        config = _config_2comp()
        rects, _ = generer_geometrie_2d(config)
        rayons = [r for r in rects if r.type_elem == "rayon"]
        # 2 comp x 2 rayons chacun = 4 rayons
        assert len(rayons) == 4

    def test_rect_attributes(self):
        config = _config_2comp()
        rects, _ = generer_geometrie_2d(config)
        for r in rects:
            assert isinstance(r, Rect)
            assert hasattr(r, 'x')
            assert hasattr(r, 'y')
            assert hasattr(r, 'w')
            assert hasattr(r, 'h')
            assert hasattr(r, 'type_elem')
            assert hasattr(r, 'label')

    def test_dimensions_coherentes(self):
        config = _config_2comp()
        rects, _ = generer_geometrie_2d(config)
        H = config["hauteur"]
        L = config["largeur"]
        for r in rects:
            if r.type_elem not in ("mur", "sol"):
                assert r.x >= -1, f"{r.label} x={r.x} < 0"
                assert r.y >= -1, f"{r.label} y={r.y} < 0"
                assert r.x + r.w <= L + 1, f"{r.label} depasse a droite"
                assert r.y + r.h <= H + 1, f"{r.label} depasse en haut"


class TestSeparationTouteHauteur:
    """Tests des separations toute hauteur."""

    def test_separation_th_hauteur_complete(self):
        schema = (
            "*-----------|-----------*\n"
            "|__________|__________|\n"
            "|__________|__________|"
        )
        config = schema_vers_config(schema)
        rects, _ = generer_geometrie_2d(config)
        seps = [r for r in rects if r.type_elem == "separation"]
        assert len(seps) == 1
        assert abs(seps[0].h - config["hauteur"]) < 1.0

    def test_separation_sous_rayon_pas_complete(self):
        config = _config_2comp()
        rects, _ = generer_geometrie_2d(config)
        seps = [r for r in rects if r.type_elem == "separation"]
        assert len(seps) == 1
        assert seps[0].h < config["hauteur"]

    def test_rayon_haut_coupe_par_separation_th(self):
        schema = (
            "*-----------|-----------*\n"
            "|__________|__________|\n"
            "|__________|__________|"
        )
        config = schema_vers_config(schema)
        rects, fiche = generer_geometrie_2d(config)
        rh = [r for r in rects if r.type_elem == "rayon_haut"]
        # Le rayon haut doit etre coupe en 2 segments
        assert len(rh) == 2


class TestCremailleresHauteur:
    """Tests de la hauteur des cremailleres."""

    def test_crem_separation_th(self):
        schema = (
            "*-----------|-----------*\n"
            "|__________|__________|\n"
            "|__________|__________|"
        )
        config = schema_vers_config(schema)
        rects, _ = generer_geometrie_2d(config)
        H = config["hauteur"]
        crems = [r for r in rects if "cremaillere" in r.type_elem]
        # Crems cote separation TH doivent faire H
        crems_th = [c for c in crems if abs(c.h - H) < 1.0]
        assert len(crems_th) >= 2  # au moins 2 (gauche et droite de la sep)

    def test_crem_separation_sous_rayon(self):
        config = _config_2comp()
        rects, _ = generer_geometrie_2d(config)
        H = config["hauteur"]
        crems = [r for r in rects if "cremaillere" in r.type_elem]
        for c in crems:
            assert c.h < H  # toutes sous le rayon haut


class TestFicheFabrication:
    """Tests de la fiche de fabrication."""

    def test_fiche_pieces_non_vide(self):
        config = _config_2comp()
        _, fiche = generer_geometrie_2d(config)
        assert len(fiche.pieces) > 0

    def test_fiche_quincaillerie(self):
        config = _config_2comp()
        _, fiche = generer_geometrie_2d(config)
        assert len(fiche.quincaillerie) > 0

    def test_piece_info_dimensions(self):
        config = _config_2comp()
        _, fiche = generer_geometrie_2d(config)
        for p in fiche.pieces:
            assert p.longueur > 0, f"{p.nom} longueur={p.longueur}"
            assert p.largeur > 0, f"{p.nom} largeur={p.largeur}"
            assert p.epaisseur > 0, f"{p.nom} epaisseur={p.epaisseur}"
