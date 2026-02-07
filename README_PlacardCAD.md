# PlacardCAD — Gestion d'aménagements de placards

## Architecture

```
placardcad/
├── requirements.txt
├── run.py                      # Point d'entrée
├── placardcad/
│   ├── __init__.py
│   ├── app.py                  # Application PyQt5
│   ├── database.py             # Modèle SQLite
│   ├── schema_parser.py        # Parser de schéma compact
│   ├── placard_builder.py      # Constructeur 3D (FreeCAD)
│   ├── pdf_export.py           # Export PDF (vue filaire + débit)
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py      # Fenêtre principale
│   │   ├── project_panel.py    # Panel arbre projets
│   │   ├── schema_editor.py    # Éditeur de schéma compact
│   │   ├── params_editor.py    # Éditeur paramètres
│   │   └── viewer_3d.py        # Widget vue 3D FreeCAD
│   └── resources/
│       └── icons/
└── tests/
```

## Modèle de données (SQLite)

```
projets
├── id              INTEGER PRIMARY KEY
├── nom             TEXT            -- Nom du projet/chantier
├── client          TEXT
├── adresse         TEXT
├── date_creation   DATETIME
├── date_modif      DATETIME
└── notes           TEXT

amenagements
├── id              INTEGER PRIMARY KEY
├── projet_id       INTEGER FK → projets.id
├── numero          INTEGER         -- N° séquentiel
├── nom             TEXT            -- Ex: "Placard chambre 1"
├── schema_txt      TEXT            -- Schéma compact
├── params_json     TEXT            -- Paramètres (JSON)
├── freecad_path    TEXT            -- Chemin .FCStd
├── date_creation   DATETIME
├── date_modif      DATETIME
└── notes           TEXT
```

## Phases de développement

| Phase | Contenu | État |
|-------|---------|------|
| 1 | Structure, gestion projets/aménagements, éditeur schéma | À faire |
| 2 | Intégration FreeCAD (génération 3D, viewer) | À faire |
| 3 | Export PDF (vue filaire + fiche de débit) | À faire |

---

## Installation

### Prérequis

| Composant | Version | Obligatoire |
|-----------|---------|-------------|
| Python | 3.10+ | ✓ |
| FreeCAD | 0.21+ | Phase 2+ |
| Git | quelconque | Optionnel |

---

### Linux (Ubuntu/Debian)

#### 1. Système

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv python3-pyqt5 git
```

#### 2. FreeCAD (pour la Phase 2)

```bash
# Option A : PPA (recommandé pour l'accès Python)
sudo add-apt-repository -y ppa:freecad-maintainers/freecad-stable
sudo apt update
sudo apt install -y freecad

# Option B : Snap (si déjà installé)
# Nécessite de localiser le module Python
```

#### 3. Trouver le chemin Python FreeCAD

```bash
# PPA :
FREECAD_LIB="/usr/lib/freecad-python3/lib"

# Snap :
FREECAD_LIB="/snap/freecad/current/usr/lib/freecad-python3/lib"

# Vérifier :
python3 -c "import sys; sys.path.insert(0,'$FREECAD_LIB'); import FreeCAD; print('FreeCAD OK')"
```

#### 4. Installer PlacardCAD

```bash
mkdir -p ~/placardcad && cd ~/placardcad

# Environnement virtuel avec accès aux packages système (PyQt5)
python3 -m venv venv --system-site-packages
source venv/bin/activate

# Dépendances
pip install -r requirements.txt

# Lien vers FreeCAD (remplacer par votre chemin)
echo "$FREECAD_LIB" > venv/lib/python3.*/site-packages/freecad.pth
```

#### 5. Lancer

```bash
cd ~/placardcad
source venv/bin/activate
python run.py
```

---

### Windows 10/11

#### 1. Python

- Télécharger depuis https://www.python.org/downloads/
- **Cocher "Add Python to PATH"** à l'installation
- Vérifier dans PowerShell : `python --version`

#### 2. FreeCAD (pour la Phase 2)

- Télécharger depuis https://www.freecad.org/downloads.php
- Installer dans `C:\Program Files\FreeCAD 0.21\`

#### 3. Trouver le chemin Python FreeCAD

```powershell
# Chemin typique (adapter à votre version) :
python -c "import sys; sys.path.insert(0, r'C:\Program Files\FreeCAD 0.21\bin'); import FreeCAD; print('FreeCAD OK')"

# Si erreur, essayer aussi :
# C:\Program Files\FreeCAD 0.21\lib
# C:\Users\VOTRE_NOM\AppData\Local\FreeCAD\bin
```

#### 4. Installer PlacardCAD

```powershell
mkdir C:\placardcad
cd C:\placardcad

# Environnement virtuel
python -m venv venv
.\venv\Scripts\Activate.ps1

# Dépendances
pip install -r requirements.txt

# Lien vers FreeCAD (adapter le chemin)
echo "C:\Program Files\FreeCAD 0.21\bin" > venv\Lib\site-packages\freecad.pth
```

#### 5. Lancer

```powershell
cd C:\placardcad
.\venv\Scripts\Activate.ps1
python run.py
```

---

### Dépendances (requirements.txt)

```
PyQt5>=5.15
reportlab>=4.0
Pillow>=10.0
```

> FreeCAD s'installe séparément. Son module Python est lié via un fichier `.pth`.

---

### Vérification

```bash
python -c "
import sys
print(f'Python {sys.version}')

try:
    from PyQt5 import QtWidgets
    print('  PyQt5 ......... OK')
except: print('  PyQt5 ......... MANQUANT')

try:
    import FreeCAD
    v = FreeCAD.Version()
    print(f'  FreeCAD ....... OK ({v[0]}.{v[1]})')
except: print('  FreeCAD ....... MANQUANT (optionnel Phase 1)')

try:
    import reportlab
    print('  ReportLab ..... OK')
except: print('  ReportLab ..... MANQUANT (optionnel Phase 1)')
"
```

---

### Problèmes courants

| Problème | Solution |
|----------|----------|
| `No module named 'FreeCAD'` | Vérifier le chemin dans le fichier `.pth` |
| FreeCAD Snap : pas d'accès Python | Utiliser le PPA ou AppImage |
| PyQt5 conflit Qt avec FreeCAD | Utiliser `--system-site-packages` |
| Windows : `python` non reconnu | Réinstaller avec "Add to PATH" |
| `ModuleNotFoundError: PyQt5` | `pip install PyQt5` dans le venv |
