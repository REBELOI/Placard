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
    _positions_charnieres,
    _longueur_coulisse,
    _get_recouvrement_facade,
    _get_ref_charniere,
    RECOUVREMENT,
    CLIP_TOP_REFS,
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


class TestOuvertureEtPercage:
    """Tests des symboles d'ouverture et percages de charnieres."""

    def test_porte_PG_genere_ouverture_G(self):
        """PG genere un symbole ouverture avec label 'G'."""
        schema = "#MEUBLE\n| PG |\n  600"
        config = meuble_schema_vers_config(schema)
        rects, _ = generer_geometrie_meuble(config)
        ouv = [r for r in rects if r.type_elem == "ouverture"]
        assert len(ouv) == 1
        assert ouv[0].label == "G"

    def test_porte_PD_genere_ouverture_D(self):
        """PD genere un symbole ouverture avec label 'D'."""
        schema = "#MEUBLE\n| PD |\n  600"
        config = meuble_schema_vers_config(schema)
        rects, _ = generer_geometrie_meuble(config)
        ouv = [r for r in rects if r.type_elem == "ouverture"]
        assert len(ouv) == 1
        assert ouv[0].label == "D"

    def test_porte_PP_genere_2_ouvertures(self):
        """PP genere 2 symboles ouverture (G et D)."""
        schema = "#MEUBLE\n| PP |\n  600"
        config = meuble_schema_vers_config(schema)
        rects, _ = generer_geometrie_meuble(config)
        ouv = [r for r in rects if r.type_elem == "ouverture"]
        assert len(ouv) == 2
        labels = {r.label for r in ouv}
        assert labels == {"G", "D"}

    def test_percages_presents_sur_porte(self):
        """Une porte genere des percages de charnieres."""
        schema = "#MEUBLE\n| PG |\n  600"
        config = meuble_schema_vers_config(schema)
        rects, _ = generer_geometrie_meuble(config)
        percages = [r for r in rects if r.type_elem == "percage"]
        nb_ch = _nb_charnieres(config["hauteur"]
                               - config["porte"]["jeu_haut"]
                               - config["porte"]["jeu_bas"])
        assert len(percages) == nb_ch

    def test_percages_PP_double(self):
        """PP genere des percages sur les 2 portes."""
        schema = "#MEUBLE\n| PP |\n  600"
        config = meuble_schema_vers_config(schema)
        rects, _ = generer_geometrie_meuble(config)
        percages = [r for r in rects if r.type_elem == "percage"]
        nb_ch = _nb_charnieres(config["hauteur"]
                               - config["porte"]["jeu_haut"]
                               - config["porte"]["jeu_bas"])
        assert len(percages) == nb_ch * 2

    def test_percage_PG_cote_gauche(self):
        """PG: percages positionnes sur le cote gauche de la porte."""
        schema = "#MEUBLE\n| PG |\n  600"
        config = meuble_schema_vers_config(schema)
        rects, _ = generer_geometrie_meuble(config)
        portes = [r for r in rects if r.type_elem == "porte"]
        percages = [r for r in rects if r.type_elem == "percage"]
        assert len(percages) > 0
        x_porte = portes[0].x
        # Les percages sont proches du bord gauche
        for p in percages:
            cx = p.x + p.w / 2
            assert cx < x_porte + portes[0].w / 2

    def test_percage_PD_cote_droit(self):
        """PD: percages positionnes sur le cote droit de la porte."""
        schema = "#MEUBLE\n| PD |\n  600"
        config = meuble_schema_vers_config(schema)
        rects, _ = generer_geometrie_meuble(config)
        portes = [r for r in rects if r.type_elem == "porte"]
        percages = [r for r in rects if r.type_elem == "percage"]
        assert len(percages) > 0
        x_porte = portes[0].x
        w_porte = portes[0].w
        for p in percages:
            cx = p.x + p.w / 2
            assert cx > x_porte + w_porte / 2

    def test_positions_charnieres_2(self):
        """2 charnieres : marge en haut et en bas."""
        pos = _positions_charnieres(600, 2)
        assert len(pos) == 2
        assert pos[0] < pos[1]

    def test_positions_charnieres_3(self):
        """3 charnieres : haut, milieu, bas."""
        pos = _positions_charnieres(1200, 3)
        assert len(pos) == 3
        assert abs(pos[1] - 600) < 1.0

    def test_groupes_porte_avec_ouverture(self):
        """P+K genere ouverture et percages pour la porte."""
        schema = "#MEUBLE\n| P+K |\n  600"
        config = meuble_schema_vers_config(schema)
        rects, _ = generer_geometrie_meuble(config)
        ouv = [r for r in rects if r.type_elem == "ouverture"]
        percages = [r for r in rects if r.type_elem == "percage"]
        assert len(ouv) >= 1
        assert len(percages) >= 1


class TestCoulisses:

    def test_coulisse_500(self):
        assert _longueur_coulisse(560, 19) == 500

    def test_coulisse_courte(self):
        assert _longueur_coulisse(350, 19) == 300


# =====================================================================
#  Type de charniere (syntaxe parser + recouvrement builder)
# =====================================================================

class TestCharniereParser:
    """Tests du parser pour la syntaxe type de charniere."""

    def test_APG_applique_gauche(self):
        r = _parse_facade("APG")
        assert r["ouverture"] == "gauche"
        assert r["charniere"] == "applique"
        assert r["groupes"][0]["charniere"] == "applique"

    def test_SPG_semi_applique_gauche(self):
        r = _parse_facade("SPG")
        assert r["ouverture"] == "gauche"
        assert r["charniere"] == "semi_applique"

    def test_EPG_encloisonnee_gauche(self):
        r = _parse_facade("EPG")
        assert r["ouverture"] == "gauche"
        assert r["charniere"] == "encloisonnee"

    def test_PDA_applique_droite(self):
        r = _parse_facade("PDA")
        assert r["ouverture"] == "droite"
        assert r["charniere"] == "applique"

    def test_PDS_semi_applique_droite(self):
        r = _parse_facade("PDS")
        assert r["ouverture"] == "droite"
        assert r["charniere"] == "semi_applique"

    def test_PDE_encloisonnee_droite(self):
        r = _parse_facade("PDE")
        assert r["ouverture"] == "droite"
        assert r["charniere"] == "encloisonnee"

    def test_APPA_double_applique(self):
        r = _parse_facade("APPA")
        assert r["ouverture"] == "double"
        assert r["charniere_g"] == "applique"
        assert r["charniere_d"] == "applique"

    def test_SPPS_double_semi_applique(self):
        r = _parse_facade("SPPS")
        assert r["ouverture"] == "double"
        assert r["charniere_g"] == "semi_applique"
        assert r["charniere_d"] == "semi_applique"

    def test_EPPE_double_encloisonnee(self):
        r = _parse_facade("EPPE")
        assert r["ouverture"] == "double"
        assert r["charniere_g"] == "encloisonnee"
        assert r["charniere_d"] == "encloisonnee"

    def test_APPS_mixte_double(self):
        r = _parse_facade("APPS")
        assert r["ouverture"] == "double"
        assert r["charniere_g"] == "applique"
        assert r["charniere_d"] == "semi_applique"

    def test_AP_applique_sans_G_defaut_gauche(self):
        r = _parse_facade("AP")
        assert r["ouverture"] == "gauche"
        assert r["charniere"] == "applique"

    def test_PG_sans_charniere(self):
        """PG sans prefixe: pas de charniere explicite."""
        r = _parse_facade("PG")
        assert r["ouverture"] == "gauche"
        assert "charniere" not in r

    def test_PP_sans_charniere(self):
        """PP sans prefixe/suffixe: pas de charniere explicite."""
        r = _parse_facade("PP")
        assert r["ouverture"] == "double"
        assert "charniere_g" not in r

    def test_combo_APG_plus_2F(self):
        """Combinaison avec + : porte avec charniere + tiroirs."""
        r = _parse_facade("2F+APG")
        assert r["type"] == "mixte"
        grp_porte = [g for g in r["groupes"] if g["type"] == "porte"][0]
        assert grp_porte["charniere"] == "applique"


class TestCharniereRecouvrement:
    """Tests du calcul de recouvrement selon le type de charniere."""

    def test_recouvrement_applique(self):
        facade = {"charniere": "applique"}
        rg, rd = _get_recouvrement_facade(facade, "applique")
        assert rg == 16.0
        assert rd == 16.0

    def test_recouvrement_semi_applique(self):
        facade = {"charniere": "semi_applique"}
        rg, rd = _get_recouvrement_facade(facade, "applique")
        assert rg == 8.0
        assert rd == 8.0

    def test_recouvrement_encloisonnee(self):
        facade = {"charniere": "encloisonnee"}
        rg, rd = _get_recouvrement_facade(facade, "applique")
        assert rg == 0.0
        assert rd == 0.0

    def test_recouvrement_double_mixte(self):
        facade = {"charniere_g": "applique", "charniere_d": "semi_applique"}
        rg, rd = _get_recouvrement_facade(facade, "applique")
        assert rg == 16.0
        assert rd == 8.0

    def test_recouvrement_defaut_pose_globale(self):
        """Sans charniere explicite, utilise la pose globale."""
        facade = {}
        rg, rd = _get_recouvrement_facade(facade, "semi_applique")
        assert rg == 8.0
        assert rd == 8.0

    def test_ref_charniere_applique(self):
        facade = {"charniere": "applique"}
        assert _get_ref_charniere(facade, "applique") == "71B959"

    def test_ref_charniere_semi_applique(self):
        facade = {"charniere": "semi_applique"}
        assert _get_ref_charniere(facade, "applique") == "71B969"

    def test_ref_charniere_encloisonnee(self):
        facade = {"charniere": "encloisonnee"}
        assert _get_ref_charniere(facade, "applique") == "71B979"

    def test_ref_double_mixte(self):
        facade = {"charniere_g": "applique", "charniere_d": "encloisonnee"}
        assert _get_ref_charniere(facade, "applique", "g") == "71B959"
        assert _get_ref_charniere(facade, "applique", "d") == "71B979"


class TestCharniereBuilder:
    """Tests d'integration: le type de charniere affecte la geometrie."""

    def _config_avec_facade(self, facade_str, pose="applique"):
        schema = f"#MEUBLE\n| {facade_str} |\n"
        config = meuble_schema_vers_config(schema)
        config["pose"] = pose
        return config

    def test_APG_largeur_facade_applique(self):
        """APG doit donner le meme recouvrement qu'une pose applique."""
        config = self._config_avec_facade("APG")
        rects, fiche = generer_geometrie_meuble(config)
        portes = [r for r in rects if r.type_elem == "porte"]
        assert len(portes) == 1
        # Largeur = larg_int + 2*16 - 2*jeu_lat
        larg_int = config["largeur"] - 2 * config["epaisseur"]
        expected_w = larg_int + 2 * 16.0 - 2 * config["porte"]["jeu_lateral"]
        assert abs(portes[0].w - expected_w) < 0.1

    def test_SPG_largeur_facade_semi_applique(self):
        """SPG = recouvrement 8mm des deux cotes."""
        config = self._config_avec_facade("SPG")
        rects, fiche = generer_geometrie_meuble(config)
        portes = [r for r in rects if r.type_elem == "porte"]
        assert len(portes) == 1
        larg_int = config["largeur"] - 2 * config["epaisseur"]
        expected_w = larg_int + 2 * 8.0 - 2 * config["porte"]["jeu_lateral"]
        assert abs(portes[0].w - expected_w) < 0.1

    def test_EPG_largeur_facade_encloisonnee(self):
        """EPG = encloisonnee, facade interieure au caisson."""
        config = self._config_avec_facade("EPG")
        rects, fiche = generer_geometrie_meuble(config)
        portes = [r for r in rects if r.type_elem == "porte"]
        assert len(portes) == 1
        larg_int = config["largeur"] - 2 * config["epaisseur"]
        expected_w = larg_int - 2 * config["porte"]["jeu_lateral"]
        assert abs(portes[0].w - expected_w) < 0.1

    def test_EPG_hauteur_encloisonnee(self):
        """EPG = encloisonnee, hauteur entre dessus et dessous."""
        config = self._config_avec_facade("EPG")
        rects, fiche = generer_geometrie_meuble(config)
        portes = [r for r in rects if r.type_elem == "porte"]
        ep = config["epaisseur"]
        h_plinthe = config["hauteur_plinthe"]
        h_corps = config["hauteur"] - h_plinthe
        jeu = config["porte"]
        expected_h = (h_corps - 2 * ep - jeu["jeu_haut"] - jeu["jeu_bas"])
        assert abs(portes[0].h - expected_h) < 0.1

    def test_APPS_double_recouvrement_mixte(self):
        """APPS = applique gauche (16mm) + semi-applique droite (8mm)."""
        config = self._config_avec_facade("APPS")
        rects, fiche = generer_geometrie_meuble(config)
        portes = [r for r in rects if r.type_elem == "porte"]
        assert len(portes) == 2
        # Largeur totale facade = larg_int + 16 + 8 - 2*jeu_lat
        larg_int = config["largeur"] - 2 * config["epaisseur"]
        expected_total = larg_int + 16.0 + 8.0 - 2 * config["porte"]["jeu_lateral"]
        jeu_e = config["porte"]["jeu_entre"]
        expected_per_door = (expected_total - jeu_e) / 2
        assert abs(portes[0].w - expected_per_door) < 0.1
        assert abs(portes[1].w - expected_per_door) < 0.1

    def test_quincaillerie_ref_charniere_APG(self):
        """APG: quincaillerie contient ref 71B959."""
        config = self._config_avec_facade("APG")
        _, fiche = generer_geometrie_meuble(config)
        quinc = fiche.quincaillerie
        refs = [q["nom"] for q in quinc]
        assert any("71B959" in r for r in refs)
        assert any("174710ZE" in r for r in refs)

    def test_quincaillerie_ref_charniere_SPG(self):
        """SPG: quincaillerie contient ref 71B969."""
        config = self._config_avec_facade("SPG")
        _, fiche = generer_geometrie_meuble(config)
        quinc = fiche.quincaillerie
        refs = [q["nom"] for q in quinc]
        assert any("71B969" in r for r in refs)

    def test_quincaillerie_APPS_refs_mixtes(self):
        """APPS: quincaillerie contient les 2 refs differentes."""
        config = self._config_avec_facade("APPS")
        _, fiche = generer_geometrie_meuble(config)
        quinc = fiche.quincaillerie
        refs = [q["nom"] for q in quinc]
        assert any("71B959" in r for r in refs)
        assert any("71B969" in r for r in refs)

    def test_PG_defaut_utilise_pose_globale(self):
        """PG sans charniere: utilise la pose globale du meuble."""
        config = self._config_avec_facade("PG", pose="semi_applique")
        rects, fiche = generer_geometrie_meuble(config)
        portes = [r for r in rects if r.type_elem == "porte"]
        larg_int = config["largeur"] - 2 * config["epaisseur"]
        expected_w = larg_int + 2 * 8.0 - 2 * config["porte"]["jeu_lateral"]
        assert abs(portes[0].w - expected_w) < 0.1
