"""
Tests unitaires pour les modules d'export (DXF, etiquettes, PDF).
"""

import os
import tempfile
import pytest
from placardcad.schema_parser import schema_vers_config
from placardcad.placard_builder import generer_geometrie_2d
from placardcad.dxf_export import exporter_dxf
from placardcad.etiquettes_export import exporter_etiquettes
from placardcad.pdf_export import exporter_pdf


def _generer_donnees():
    """Genere un jeu de donnees de test (rects, config, fiche)."""
    schema = (
        "*-----------*-----------*\n"
        "|__________|__________|\n"
        "|__________|__________|"
    )
    config = schema_vers_config(schema)
    rects, fiche = generer_geometrie_2d(config)
    return rects, config, fiche


class TestExportDXF:
    """Tests de l'export DXF."""

    def test_export_genere_fichier(self):
        rects, config, fiche = _generer_donnees()
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
            path = f.name
        try:
            exporter_dxf(path, rects, config, fiche)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 100
        finally:
            os.unlink(path)

    def test_dxf_structure(self):
        rects, config, fiche = _generer_donnees()
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
            path = f.name
        try:
            exporter_dxf(path, rects, config, fiche)
            with open(path) as f:
                content = f.read()
            assert "HEADER" in content
            assert "TABLES" in content
            assert "ENTITIES" in content
            assert "EOF" in content
        finally:
            os.unlink(path)

    def test_dxf_calques(self):
        rects, config, fiche = _generer_donnees()
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
            path = f.name
        try:
            exporter_dxf(path, rects, config, fiche)
            with open(path) as f:
                content = f.read()
            assert "SEPARATIONS" in content
            assert "RAYONS" in content
            assert "MURS" in content
        finally:
            os.unlink(path)

    def test_dxf_contient_geometrie(self):
        rects, config, fiche = _generer_donnees()
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
            path = f.name
        try:
            exporter_dxf(path, rects, config, fiche)
            with open(path) as f:
                content = f.read()
            assert "LWPOLYLINE" in content
            assert content.count("LWPOLYLINE") >= len(rects)
        finally:
            os.unlink(path)


class TestExportEtiquettes:
    """Tests de l'export etiquettes PDF."""

    def test_export_genere_fichier(self):
        _, _, fiche = _generer_donnees()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            exporter_etiquettes(path, fiche, projet_id=1, amenagement_id=1)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 500
        finally:
            os.unlink(path)

    def test_references_attribuees(self):
        _, _, fiche = _generer_donnees()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            exporter_etiquettes(path, fiche, projet_id=1, amenagement_id=2)
            for p in fiche.pieces:
                assert p.reference.startswith("P1/A2/")
        finally:
            os.unlink(path)

    def test_nombre_etiquettes(self):
        _, _, fiche = _generer_donnees()
        total = sum(p.quantite for p in fiche.pieces)
        assert total > 0


class TestExportPDF:
    """Tests de l'export PDF principal."""

    def test_export_genere_fichier(self):
        rects, config, fiche = _generer_donnees()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            exporter_pdf(path, rects, config, fiche)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 1000
        finally:
            os.unlink(path)

    def test_export_avec_projet_info(self):
        rects, config, fiche = _generer_donnees()
        projet_info = {"nom": "Test", "client": "Client Test",
                       "adresse": "123 Rue Test"}
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            exporter_pdf(path, rects, config, fiche, projet_info,
                         projet_id=1, amenagement_id=1)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 1000
        finally:
            os.unlink(path)
