"""Tests unitaires pour le module meuble (parser + builder)."""

import pytest

from placardcad.meuble_schema_parser import (
    est_schema_meuble,
    parser_schema_meuble,
    meuble_schema_vers_config,
    _parse_facade,
)
from placardcad.meuble_builder import (
    generer_geometrie_meuble,
    calculer_largeurs_meuble,
    _nb_charnieres,
    _longueur_coulisse,
)


# =====================================================================
#  Detection schema meuble
# =====================================================================

class TestDetectionMeuble:

    def test_schema_meuble_detecte(self):
        assert est_schema_meuble("#MEUBLE\n| P |")

    def test_schema_meuble_casse_insensible(self):
        assert est_schema_meuble("#meuble\n| P |")

    def test_schema_placard_non_detecte(self):
        assert not est_schema_meuble("*---*---*\n|__|__|")

    def test_schema_vide_non_detecte(self):
        assert not est_schema_meuble("")


# =====================================================================
#  Parser facades
# =====================================================================

class TestParseFacade:

    def test_porte_simple(self):
        f = _parse_facade("P")
        assert f["type"] == "portes"
        assert f["nb_portes"] == 1

    def test_porte_gauche(self):
        f = _parse_facade("PG")
        assert f["ouverture"] == "gauche"

    def test_porte_droite(self):
        f = _parse_facade("PD")
        assert f["ouverture"] == "droite"

    def test_portes_doubles(self):
        f = _parse_facade("PP")
        assert f["nb_portes"] == 2
        assert f["ouverture"] == "double"

    def test_tiroirs(self):
        f = _parse_facade("TTT")
        assert f["type"] == "tiroirs"
        assert f["nb_tiroirs"] == 3

    def test_tiroirs_numerique(self):
        f = _parse_facade("4T")
        assert f["nb_tiroirs"] == 4

    def test_niche(self):
        f = _parse_facade("N")
        assert f["type"] == "niche"

    def test_niche_vide(self):
        f = _parse_facade("")
        assert f["type"] == "niche"

    def test_mixte(self):
        f = _parse_facade("2T+P")
        assert f["type"] == "mixte"
        assert f["nb_tiroirs"] == 2
        assert f["nb_portes"] == 1

    # --- Groupes et hauteurs explicites ---

    def test_groupes_tiroir_T(self):
        f = _parse_facade("TTT")
        assert len(f["groupes"]) == 1
        assert f["groupes"][0]["type"] == "tiroir"
        assert f["groupes"][0]["hauteur"] is None
        assert f["groupes"][0]["nombre"] == 3

    def test_groupes_porte(self):
        f = _parse_facade("PP")
        assert len(f["groupes"]) == 1
        assert f["groupes"][0]["type"] == "porte"
        assert f["groupes"][0]["nombre"] == 2

    def test_hauteur_F_simple(self):
        f = _parse_facade("F")
        assert f["type"] == "tiroirs"
        assert f["nb_tiroirs"] == 1
        assert f["groupes"][0]["hauteur"] == "F"

    def test_hauteur_FF_repete(self):
        f = _parse_facade("FF")
        assert f["nb_tiroirs"] == 2
        assert f["groupes"][0]["hauteur"] == "F"
        assert f["groupes"][0]["nombre"] == 2

    def test_hauteur_2F_numerique(self):
        f = _parse_facade("2F")
        assert f["nb_tiroirs"] == 2
        assert f["groupes"][0]["hauteur"] == "F"
        assert f["groupes"][0]["nombre"] == 2

    def test_hauteur_K(self):
        f = _parse_facade("K")
        assert f["groupes"][0]["hauteur"] == "K"

    def test_hauteur_M(self):
        f = _parse_facade("3M")
        assert f["nb_tiroirs"] == 3
        assert f["groupes"][0]["hauteur"] == "M"

    def test_hauteur_C(self):
        f = _parse_facade("CC")
        assert f["nb_tiroirs"] == 2
        assert f["groupes"][0]["hauteur"] == "C"

    def test_multi_hauteur_2F_K(self):
        """2F+K = 2 tiroirs F en bas + 1 tiroir K en haut."""
        f = _parse_facade("2F+K")
        assert f["type"] == "tiroirs"
        assert f["nb_tiroirs"] == 3
        assert len(f["groupes"]) == 2
        # Bas: 2 F
        assert f["groupes"][0]["hauteur"] == "F"
        assert f["groupes"][0]["nombre"] == 2
        # Haut: 1 K
        assert f["groupes"][1]["hauteur"] == "K"
        assert f["groupes"][1]["nombre"] == 1

    def test_multi_hauteur_P_2F_K(self):
        """P+2F+K = porte en bas, 2 F au milieu, 1 K en haut."""
        f = _parse_facade("P+2F+K")
        assert f["type"] == "mixte"
        assert f["nb_portes"] == 1
        assert f["nb_tiroirs"] == 3
        assert len(f["groupes"]) == 3
        assert f["groupes"][0]["type"] == "porte"
        assert f["groupes"][1]["hauteur"] == "F"
        assert f["groupes"][2]["hauteur"] == "K"

    def test_multi_hauteur_K_P(self):
        """K+P = tiroir K en bas, porte en haut."""
        f = _parse_facade("K+P")
        assert f["type"] == "mixte"
        assert f["groupes"][0]["type"] == "tiroir"
        assert f["groupes"][0]["hauteur"] == "K"
        assert f["groupes"][1]["type"] == "porte"

    def test_niche_groupes_vides(self):
        f = _parse_facade("N")
        assert f["groupes"] == []


# =====================================================================
#  Parser schema meuble
# =====================================================================

class TestParserSchemaMeuble:

    def test_2_compartiments_largeurs(self):
        schema = "#MEUBLE\n| PP | TTT |\n| -- |     |\n  600   400"
        parsed = parser_schema_meuble(schema)
        assert parsed["nombre_compartiments"] == 2
        assert parsed["mode_largeur"] == "dimensions"
        assert parsed["largeurs_compartiments"] == [600, 400]

    def test_1_compartiment(self):
        schema = "#MEUBLE\n| P |\n| -- |"
        parsed = parser_schema_meuble(schema)
        assert parsed["nombre_compartiments"] == 1

    def test_etageres_comptees(self):
        schema = "#MEUBLE\n| P |\n| -- |\n| -- |\n| -- |"
        parsed = parser_schema_meuble(schema)
        assert parsed["compartiments"][0]["etageres"] == 3

    def test_mode_egal_sans_largeurs(self):
        schema = "#MEUBLE\n| P | T |\n| -- |   |"
        parsed = parser_schema_meuble(schema)
        assert parsed["mode_largeur"] == "egal"

    def test_3_compartiments(self):
        schema = "#MEUBLE\n| P | TTT | PD |\n| -- |     | -- |"
        parsed = parser_schema_meuble(schema)
        assert parsed["nombre_compartiments"] == 3

    def test_erreur_schema_vide(self):
        with pytest.raises(ValueError):
            parser_schema_meuble("#MEUBLE")

    def test_erreur_pas_separateurs(self):
        with pytest.raises(ValueError):
            parser_schema_meuble("#MEUBLE\nP T")


# =====================================================================
#  Builder meuble
# =====================================================================

class TestCalculLargeursMeuble:

    def test_largeurs_egales(self):
        config = {
            "largeur": 1000, "epaisseur": 19,
            "nombre_compartiments": 2,
            "separation": {"epaisseur": 19},
            "mode_largeur": "egal",
            "largeurs_compartiments": [],
        }
        largeurs = calculer_largeurs_meuble(config)
        assert len(largeurs) == 2
        assert abs(largeurs[0] - largeurs[1]) < 0.01

    def test_largeurs_specifiees(self):
        config = {
            "largeur": 1000, "epaisseur": 19,
            "nombre_compartiments": 2,
            "separation": {"epaisseur": 19},
            "mode_largeur": "dimensions",
            "largeurs_compartiments": [600, 400],
        }
        largeurs = calculer_largeurs_meuble(config)
        assert largeurs[0] > largeurs[1]


class TestGenererGeometrieMeuble:

    def _config_simple(self):
        schema = "#MEUBLE\n| PP | TTT |\n| -- |     |\n  600   400"
        return meuble_schema_vers_config(schema)

    def test_retourne_rects_et_fiche(self):
        config = self._config_simple()
        rects, fiche = generer_geometrie_meuble(config)
        assert isinstance(rects, list)
        assert len(rects) > 0
        assert len(fiche.pieces) > 0

    def test_flancs_presents(self):
        config = self._config_simple()
        rects, _ = generer_geometrie_meuble(config)
        flancs = [r for r in rects if r.type_elem == "flanc"]
        assert len(flancs) == 2

    def test_portes_presentes(self):
        config = self._config_simple()
        rects, _ = generer_geometrie_meuble(config)
        portes = [r for r in rects if r.type_elem == "porte"]
        assert len(portes) == 2  # PP = 2 portes

    def test_tiroirs_presents(self):
        config = self._config_simple()
        rects, _ = generer_geometrie_meuble(config)
        tiroirs = [r for r in rects if r.type_elem == "tiroir"]
        assert len(tiroirs) == 3

    def test_etageres_presentes(self):
        config = self._config_simple()
        rects, _ = generer_geometrie_meuble(config)
        etag = [r for r in rects if r.type_elem == "etagere"]
        assert len(etag) == 1

    def test_separation_presente(self):
        config = self._config_simple()
        rects, _ = generer_geometrie_meuble(config)
        seps = [r for r in rects if r.type_elem == "separation"]
        assert len(seps) == 1

    def test_plinthe_presente(self):
        config = self._config_simple()
        rects, _ = generer_geometrie_meuble(config)
        plinthes = [r for r in rects if r.type_elem == "plinthe"]
        assert len(plinthes) == 1

    def test_charnieres_quincaillerie(self):
        config = self._config_simple()
        _, fiche = generer_geometrie_meuble(config)
        charnieres = [q for q in fiche.quincaillerie if "charniere" in q["nom"].lower()]
        assert len(charnieres) >= 1

    def test_coulisses_quincaillerie(self):
        config = self._config_simple()
        _, fiche = generer_geometrie_meuble(config)
        coulisses = [q for q in fiche.quincaillerie if "legrabox" in q["nom"].lower()]
        assert len(coulisses) >= 1


class TestCharnières:

    def test_2_charnieres_petite_porte(self):
        assert _nb_charnieres(600) == 2

    def test_3_charnieres_porte_moyenne(self):
        assert _nb_charnieres(1200) == 3

    def test_4_charnieres_grande_porte(self):
        assert _nb_charnieres(1800) == 4


class TestMultiHauteurBuilder:
    """Tests du builder avec tiroirs multi-hauteurs."""

    def test_2F_K_genere_3_tiroirs(self):
        """Schema 2F+K genere 3 tiroirs avec hauteurs differentes."""
        schema = "#MEUBLE\n| PP | 2F+K |\n  600   400"
        config = meuble_schema_vers_config(schema)
        rects, fiche = generer_geometrie_meuble(config)
        tiroirs = [r for r in rects if r.type_elem == "tiroir"]
        assert len(tiroirs) == 3

    def test_2F_K_fiche_2_groupes_coulisses(self):
        """2F+K genere 2 groupes de coulisses distincts (F et K)."""
        schema = "#MEUBLE\n| PP | 2F+K |\n  600   400"
        config = meuble_schema_vers_config(schema)
        _, fiche = generer_geometrie_meuble(config)
        coulisses = [q for q in fiche.quincaillerie
                     if "legrabox" in q["nom"].lower()]
        assert len(coulisses) >= 1
        # Verifier qu'il y a des coulisses F et K
        noms = " ".join(q["nom"] for q in coulisses)
        assert "F" in noms
        assert "K" in noms

    def test_P_K_mixte_groupes(self):
        """P+K = porte en bas, tiroir K en haut."""
        schema = "#MEUBLE\n| P+K |\n  600"
        config = meuble_schema_vers_config(schema)
        rects, fiche = generer_geometrie_meuble(config)
        portes = [r for r in rects if r.type_elem == "porte"]
        tiroirs = [r for r in rects if r.type_elem == "tiroir"]
        assert len(portes) >= 1
        assert len(tiroirs) >= 1
        # Porte en bas, tiroir en haut
        z_porte = portes[0].y
        z_tiroir = tiroirs[0].y
        assert z_tiroir > z_porte

    def test_K_P_ordre_inverse(self):
        """K+P = tiroir K en bas, porte en haut."""
        schema = "#MEUBLE\n| K+P |\n  600"
        config = meuble_schema_vers_config(schema)
        rects, _ = generer_geometrie_meuble(config)
        portes = [r for r in rects if r.type_elem == "porte"]
        tiroirs = [r for r in rects if r.type_elem == "tiroir"]
        assert len(portes) >= 1
        assert len(tiroirs) >= 1
        # Tiroir en bas, porte en haut
        z_porte = portes[0].y
        z_tiroir = tiroirs[0].y
        assert z_tiroir < z_porte

    def test_3F_adaptation_hauteurs(self):
        """3F: tiroir du haut au minimum LEGRABOX, les bas adaptes."""
        from placardcad.meuble_builder import LEGRABOX_HAUTEURS
        schema = "#MEUBLE\n| 3F |\n  600"
        config = meuble_schema_vers_config(schema)
        rects, _ = generer_geometrie_meuble(config)
        tiroirs = sorted(
            [r for r in rects if r.type_elem == "tiroir"],
            key=lambda r: r.y)
        assert len(tiroirs) == 3
        h_min = LEGRABOX_HAUTEURS["F"] + 2 * config["porte"]["jeu_haut"]
        # Le tiroir du haut (dernier) garde la hauteur minimum
        assert abs(tiroirs[2].h - h_min) < 0.1
        # Les tiroirs du bas sont >= minimum (adaptes)
        assert tiroirs[0].h >= h_min - 0.1
        assert tiroirs[1].h >= h_min - 0.1
        # Les 2 tiroirs du bas ont la meme hauteur (adaptee)
        assert abs(tiroirs[0].h - tiroirs[1].h) < 0.1


    def test_tiroirs_remplissent_facade(self):
        """Les tiroirs remplissent toute la zone facade sans espace vide."""
        schema = "#MEUBLE\n| 3K |\n  500"
        config = meuble_schema_vers_config(schema, {"hauteur": 840})
        rects, _ = generer_geometrie_meuble(config)
        tiroirs = sorted(
            [r for r in rects if r.type_elem == "tiroir"],
            key=lambda r: r.y)
        assert len(tiroirs) == 3
        jeu_entre = config["tiroir"]["jeu_entre"]
        jeu_bas = config["porte"]["jeu_bas"]
        jeu_haut = config["porte"]["jeu_haut"]
        h_plinthe = config["hauteur_plinthe"]
        # Zone totale = H - jeu_bas - jeu_haut - h_plinthe ... (approx)
        # Verifier que le dernier tiroir arrive pres du haut
        z_top_tiroir = tiroirs[2].y + tiroirs[2].h
        z_facade_haut = 840 - jeu_haut
        assert abs(z_top_tiroir - z_facade_haut) < 1.0

    def test_adaptation_mixte_pas_appliquee(self):
        """Avec porte+tiroir, les tiroirs gardent leur hauteur minimale."""
        from placardcad.meuble_builder import LEGRABOX_HAUTEURS
        schema = "#MEUBLE\n| P+K |\n  500"
        config = meuble_schema_vers_config(schema)
        rects, _ = generer_geometrie_meuble(config)
        tiroirs = [r for r in rects if r.type_elem == "tiroir"]
        assert len(tiroirs) == 1
        h_min = LEGRABOX_HAUTEURS["K"] + 2 * config["porte"]["jeu_haut"]
        # Le tiroir garde sa hauteur minimale
        assert abs(tiroirs[0].h - h_min) < 0.1


class TestCoulisses:

    def test_coulisse_500(self):
        assert _longueur_coulisse(560, 19) == 500

    def test_coulisse_courte(self):
        assert _longueur_coulisse(350, 19) == 300
