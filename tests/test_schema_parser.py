"""
Tests unitaires pour le parser de schemas compacts.
"""

import pytest
from placardcad.schema_parser import parser_schema, schema_vers_config


class TestParserSchemaBase:
    """Tests de base du parser de schema."""

    def test_3_compartiments_egaux(self):
        schema = (
            "*-----------*-----------*-----------*\n"
            "|__________|__________|__________|\n"
            "|__________|__________|__________|\n"
            "|__________|__________|__________|"
        )
        config = parser_schema(schema)
        assert config["nombre_compartiments"] == 3
        assert config["rayon_haut"] is True
        assert all(c["rayons"] == 3 for c in config["compartiments"])

    def test_2_compartiments(self):
        schema = (
            "*-----------*-----------*\n"
            "|__________|__________|\n"
            "|__________|__________|"
        )
        config = parser_schema(schema)
        assert config["nombre_compartiments"] == 2
        assert all(c["rayons"] == 2 for c in config["compartiments"])

    def test_1_compartiment(self):
        schema = (
            "*-----------*\n"
            "|__________|\n"
            "|__________|"
        )
        config = parser_schema(schema)
        assert config["nombre_compartiments"] == 1

    def test_nombre_rayons_different(self):
        schema = (
            "*-----------*-----------*\n"
            "|__________|__________|\n"
            "|__________|"
        )
        config = parser_schema(schema)
        assert config["compartiments"][0]["rayons"] == 2
        assert config["compartiments"][1]["rayons"] == 1


class TestParserModesLargeur:
    """Tests des modes de largeur (egal, dimensions, mixte)."""

    def test_mode_egal(self):
        schema = (
            "*-----------*-----------*\n"
            "|__________|__________|"
        )
        config = parser_schema(schema)
        assert config["mode_largeur"] == "egal"

    def test_mode_dimensions(self):
        schema = (
            "*-----------*-----------*\n"
            "|__________|__________|\n"
            "500         800"
        )
        config = parser_schema(schema)
        assert config["mode_largeur"] == "dimensions"
        assert config["largeurs_compartiments"][0] == 500
        assert config["largeurs_compartiments"][1] == 800

    def test_mode_mixte(self):
        schema = (
            "*-----------*-----------*-----------*\n"
            "|__________|__________|__________|\n"
            "300"
        )
        config = parser_schema(schema)
        assert config["mode_largeur"] == "mixte"
        assert config["largeurs_compartiments"][0] == 300


class TestParserCremailleres:
    """Tests de detection des cremailleres."""

    def test_cremaillere_encastree(self):
        schema = (
            "*-----------*-----------*\n"
            "|__________|__________|"
        )
        config = parser_schema(schema)
        comp0 = config["compartiments"][0]
        assert comp0["type_crem_gauche"] == "encastree"
        assert comp0["type_crem_droite"] == "encastree"

    def test_cremaillere_applique(self):
        schema = (
            "/-----------*-----------/\n"
            "/__________|__________/"
        )
        config = parser_schema(schema)
        comp0 = config["compartiments"][0]
        assert comp0["type_crem_gauche"] == "applique"
        comp1 = config["compartiments"][1]
        assert comp1["type_crem_droite"] == "applique"


class TestParserSeparations:
    """Tests des separations (sous_rayon vs toute_hauteur)."""

    def test_separation_sous_rayon(self):
        schema = (
            "*-----------*-----------*\n"
            "|__________|__________|"
        )
        config = parser_schema(schema)
        assert config["separations"][0]["mode"] == "sous_rayon"

    def test_separation_toute_hauteur(self):
        schema = (
            "*-----------|-----------*\n"
            "|__________|__________|"
        )
        config = parser_schema(schema)
        assert config["separations"][0]["mode"] == "toute_hauteur"

    def test_separations_mixtes(self):
        schema = (
            "*-----------*-----------|----------*\n"
            "|__________|__________|__________|"
        )
        config = parser_schema(schema)
        assert config["separations"][0]["mode"] == "sous_rayon"
        assert config["separations"][1]["mode"] == "toute_hauteur"


class TestSchemaVersConfig:
    """Tests de la fonction complete schema_vers_config."""

    def test_parametres_par_defaut(self):
        schema = (
            "*-----------*-----------*\n"
            "|__________|__________|"
        )
        config = schema_vers_config(schema)
        assert config["hauteur"] == 2500
        assert config["largeur"] == 3000
        assert config["profondeur"] == 600

    def test_parametres_personnalises(self):
        schema = (
            "*-----------*-----------*\n"
            "|__________|__________|"
        )
        params = {"hauteur": 2000, "largeur": 2500, "profondeur": 500}
        config = schema_vers_config(schema, params)
        assert config["hauteur"] == 2000
        assert config["largeur"] == 2500
        assert config["profondeur"] == 500

    def test_schema_vide_erreur(self):
        with pytest.raises(Exception):
            parser_schema("")

    def test_rayon_haut_absent(self):
        """Schema sans rayon haut (premiere ligne sans - ni _)."""
        schema = (
            "|          |          |\n"
            "|__________|__________|\n"
            "|__________|__________|"
        )
        config = parser_schema(schema)
        assert config["rayon_haut"] is False

    def test_panneau_mur_gauche(self):
        """Un | en bord gauche du premier compartiment implique panneau mur."""
        schema = (
            "*-----------*-----------*\n"
            "|__________|__________|"
        )
        config = parser_schema(schema)
        comp0 = config["compartiments"][0]
        assert comp0.get("panneau_mur_gauche", False) is True

    def test_panneau_mur_droite(self):
        """Un | en bord droit du dernier compartiment implique panneau mur."""
        schema = (
            "*-----------*-----------*\n"
            "|__________|__________|"
        )
        config = parser_schema(schema)
        comp_last = config["compartiments"][-1]
        assert comp_last.get("panneau_mur_droite", False) is True
