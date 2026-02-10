"""
Export DXF (format R12 ASCII) pour PlacardCAD.

Genere un fichier DXF 2D a partir de la geometrie calculee par placard_builder.
Compatible avec AutoCAD, LibreCAD, FreeCAD, etc.
Aucune dependance externe requise.
"""

from .placard_builder import Rect, FicheFabrication


# Mapping type_elem → nom de calque DXF
LAYER_MAP = {
    "mur": "MURS",
    "sol": "SOL",
    "separation": "SEPARATIONS",
    "rayon_haut": "RAYON_HAUT",
    "rayon": "RAYONS",
    "cremaillere_encastree": "CREMAILLERES",
    "cremaillere_applique": "CREMAILLERES",
    "panneau_mur": "PANNEAUX_MUR",
    "tasseau": "TASSEAUX",
}

# Couleurs DXF par calque (index ACI : 1=rouge, 2=jaune, 3=vert, 4=cyan, 5=bleu, 6=magenta, 7=blanc)
LAYER_COLORS = {
    "MURS": 8,            # gris fonce
    "SOL": 9,             # gris
    "SEPARATIONS": 30,    # orange
    "RAYON_HAUT": 40,     # jaune-orange
    "RAYONS": 2,          # jaune
    "CREMAILLERES": 5,    # bleu
    "PANNEAUX_MUR": 30,   # orange
    "TASSEAUX": 42,       # brun
}


def _dxf_header(largeur: float, hauteur: float) -> str:
    """Genere l'en-tete DXF minimal avec les limites du dessin."""
    return f"""0
SECTION
2
HEADER
9
$ACADVER
1
AC1009
9
$EXTMIN
10
-100.0
20
-200.0
9
$EXTMAX
10
{largeur + 100.0:.1f}
20
{hauteur + 100.0:.1f}
9
$LIMMIN
10
-100.0
20
-200.0
9
$LIMMAX
10
{largeur + 100.0:.1f}
20
{hauteur + 100.0:.1f}
0
ENDSEC
"""


def _dxf_tables() -> str:
    """Genere la section TABLES avec les calques."""
    lines = ["0\nSECTION\n2\nTABLES\n0\nTABLE\n2\nLAYER\n70\n10"]

    # Calque par defaut
    lines.append("0\nLAYER\n2\n0\n70\n0\n62\n7\n6\nCONTINUOUS")

    # Calques metier
    for name, color in LAYER_COLORS.items():
        lines.append(f"0\nLAYER\n2\n{name}\n70\n0\n62\n{color}\n6\nCONTINUOUS")

    # Calque cotations
    lines.append("0\nLAYER\n2\nCOTATIONS\n70\n0\n62\n3\n6\nCONTINUOUS")

    lines.append("0\nENDTAB\n0\nENDSEC")
    return "\n".join(lines) + "\n"


def _dxf_rect(x: float, y: float, w: float, h: float,
              layer: str = "0") -> str:
    """Genere un rectangle DXF (LWPOLYLINE fermee)."""
    x2 = x + w
    y2 = y + h
    return f"""0
LWPOLYLINE
8
{layer}
90
4
70
1
10
{x:.2f}
20
{y:.2f}
10
{x2:.2f}
20
{y:.2f}
10
{x2:.2f}
20
{y2:.2f}
10
{x:.2f}
20
{y2:.2f}
"""


def _dxf_line(x1: float, y1: float, x2: float, y2: float,
              layer: str = "0") -> str:
    """Genere une ligne DXF."""
    return f"""0
LINE
8
{layer}
10
{x1:.2f}
20
{y1:.2f}
11
{x2:.2f}
21
{y2:.2f}
"""


def _dxf_text(x: float, y: float, texte: str, hauteur: float = 30.0,
              layer: str = "0") -> str:
    """Genere un texte DXF."""
    return f"""0
TEXT
8
{layer}
10
{x:.2f}
20
{y:.2f}
40
{hauteur:.1f}
1
{texte}
"""


def _dxf_dim_h(x1: float, x2: float, y: float, texte: str,
               layer: str = "COTATIONS") -> str:
    """Cotation horizontale simplifiee (ligne + texte)."""
    mid_x = (x1 + x2) / 2
    result = _dxf_line(x1, y, x2, y, layer)
    # Petits traits verticaux aux extremites
    result += _dxf_line(x1, y - 15, x1, y + 15, layer)
    result += _dxf_line(x2, y - 15, x2, y + 15, layer)
    # Texte au milieu
    result += _dxf_text(mid_x - len(texte) * 8, y + 20, texte, 25.0, layer)
    return result


def _dxf_dim_v(x: float, y1: float, y2: float, texte: str,
               layer: str = "COTATIONS") -> str:
    """Cotation verticale simplifiee (ligne + texte)."""
    mid_y = (y1 + y2) / 2
    result = _dxf_line(x, y1, x, y2, layer)
    # Petits traits horizontaux aux extremites
    result += _dxf_line(x - 15, y1, x + 15, y1, layer)
    result += _dxf_line(x - 15, y2, x + 15, y2, layer)
    # Texte a cote
    result += _dxf_text(x + 20, mid_y - 12, texte, 25.0, layer)
    return result


def exporter_dxf(filepath: str, rects: list[Rect], config: dict,
                 fiche: FicheFabrication | None = None):
    """Exporte la vue de face en fichier DXF.

    Le plan est en mm, coordonnees identiques au modele :
    X = largeur (gauche->droite), Y = hauteur (sol->plafond).
    """
    H = config["hauteur"]
    L = config["largeur"]

    entities = ""

    # --- Rectangles des elements ---
    for r in rects:
        layer = LAYER_MAP.get(r.type_elem, "0")
        entities += _dxf_rect(r.x, r.y, r.w, r.h, layer)

    # --- Cotation largeur totale ---
    entities += _dxf_dim_h(0, L, -80, f"{L:.0f}")

    # --- Cotation hauteur totale ---
    entities += _dxf_dim_v(-80, 0, H, f"{H:.0f}")

    # --- Cotations compartiments ---
    seps = sorted([r for r in rects if r.type_elem == "separation"],
                  key=lambda r: r.x)
    edges = [0.0]
    for s in seps:
        edges.append(s.x)
        edges.append(s.x + s.w)
    edges.append(L)

    for i in range(0, len(edges), 2):
        x_l = edges[i]
        x_r = edges[i + 1]
        w = x_r - x_l
        if w <= 1:
            continue
        entities += _dxf_dim_h(x_l, x_r, -150, f"{w:.0f}")

    # --- Labels des elements ---
    for r in rects:
        if r.type_elem in ("separation", "rayon_haut", "panneau_mur"):
            layer = LAYER_MAP.get(r.type_elem, "0")
            entities += _dxf_text(
                r.x + r.w / 2 - len(r.label) * 5,
                r.y + r.h / 2 - 10,
                r.label, 15.0, layer
            )

    # Assemblage du fichier DXF
    dxf = _dxf_header(L, H)
    dxf += _dxf_tables()
    dxf += "0\nSECTION\n2\nENTITIES\n"
    dxf += entities
    dxf += "0\nENDSEC\n0\nEOF\n"

    with open(filepath, "w", encoding="ascii", errors="replace") as f:
        f.write(dxf)
