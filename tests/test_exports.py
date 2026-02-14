"""
Tests unitaires pour les modules d'export (DXF, etiquettes, PDF).
"""

import os
import tempfile
import zipfile
import pytest
from placardcad.schema_parser import schema_vers_config
from placardcad.placard_builder import generer_geometrie_2d
from placardcad.dxf_export import exporter_dxf
from placardcad.etiquettes_export import exporter_etiquettes
from placardcad.pdf_export import exporter_pdf, exporter_pdf_meuble
from placardcad.meuble_schema_parser import meuble_schema_vers_config
from placardcad.meuble_builder import (
    generer_geometrie_meuble,
    generer_vue_dessus_meuble,
    generer_vue_cote_meuble,
)
from placardcad.freecad_export import exporter_freecad_meuble


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


# =====================================================================
#  Donnees de test meuble
# =====================================================================

def _generer_donnees_meuble():
    """Genere un jeu de donnees de test meuble."""
    schema = "#MEUBLE\n| APG | TTT |\n| -- |     |\n  600  400\n"
    config = meuble_schema_vers_config(schema)
    rects_face, fiche = generer_geometrie_meuble(config)
    rects_dessus = generer_vue_dessus_meuble(config)
    rects_cote = generer_vue_cote_meuble(config)
    return config, rects_face, rects_dessus, rects_cote, fiche


# =====================================================================
#  Export PDF Meuble
# =====================================================================

class TestExportPDFMeuble:

    def test_export_genere_fichier(self):
        config, rects_f, rects_d, rects_c, fiche = _generer_donnees_meuble()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            exporter_pdf_meuble(path, config, rects_f, rects_d, rects_c, fiche)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 500
        finally:
            os.unlink(path)

    def test_export_avec_projet_info(self):
        config, rects_f, rects_d, rects_c, fiche = _generer_donnees_meuble()
        projet_info = {"nom": "Cuisine Test", "client": "M. Dupont",
                       "adresse": "10 rue des Meubles"}
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            exporter_pdf_meuble(path, config, rects_f, rects_d, rects_c, fiche,
                                projet_info=projet_info,
                                amenagement_nom="Meuble bas",
                                projet_id=1, amenagement_id=2)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 1000
        finally:
            os.unlink(path)

    def test_export_meuble_pp_charnieres(self):
        """Meuble avec PP + charnieres: le PDF doit inclure la quincaillerie."""
        schema = "#MEUBLE\n| APPA |\n"
        config = meuble_schema_vers_config(schema)
        rects_f, fiche = generer_geometrie_meuble(config)
        rects_d = generer_vue_dessus_meuble(config)
        rects_c = generer_vue_cote_meuble(config)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            exporter_pdf_meuble(path, config, rects_f, rects_d, rects_c, fiche)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 500
            assert len(fiche.quincaillerie) > 0
        finally:
            os.unlink(path)


# =====================================================================
#  Export FreeCAD Meuble
# =====================================================================

class TestExportFreeCADMeuble:

    def test_export_genere_fichier(self):
        config, _, _, _, _ = _generer_donnees_meuble()
        with tempfile.NamedTemporaryFile(suffix=".FCStd", delete=False) as f:
            path = f.name
        try:
            exporter_freecad_meuble(path, config)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 100
        finally:
            os.unlink(path)

    def test_fcstd_est_zip_valide(self):
        config, _, _, _, _ = _generer_donnees_meuble()
        with tempfile.NamedTemporaryFile(suffix=".FCStd", delete=False) as f:
            path = f.name
        try:
            exporter_freecad_meuble(path, config)
            assert zipfile.is_zipfile(path)
            with zipfile.ZipFile(path, "r") as zf:
                names = zf.namelist()
                assert "Document.xml" in names
                assert "GuiDocument.xml" in names
        finally:
            os.unlink(path)

    def test_fcstd_contient_objets(self):
        config, _, _, _, _ = _generer_donnees_meuble()
        with tempfile.NamedTemporaryFile(suffix=".FCStd", delete=False) as f:
            path = f.name
        try:
            exporter_freecad_meuble(path, config)
            with zipfile.ZipFile(path, "r") as zf:
                doc = zf.read("Document.xml").decode("utf-8")
            assert "Part::Box" in doc
            # Au moins flancs, dessus, dessous, fond
            assert doc.count("Part::Box") >= 4
        finally:
            os.unlink(path)

    def test_fcstd_labels_meuble(self):
        config, _, _, _, _ = _generer_donnees_meuble()
        with tempfile.NamedTemporaryFile(suffix=".FCStd", delete=False) as f:
            path = f.name
        try:
            exporter_freecad_meuble(path, config)
            with zipfile.ZipFile(path, "r") as zf:
                doc = zf.read("Document.xml").decode("utf-8")
            # Doit contenir des elements meuble (flancs = "Cote gauche/droit")
            assert "Cote" in doc or "Dessus" in doc
        finally:
            os.unlink(path)
