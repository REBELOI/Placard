# PlacardCAD

Application de conception d'amenagements interieurs de placards (dressings, rangements).
Elle permet de dessiner un placard via un schema compact textuel, de visualiser le resultat
en 2D, d'optimiser le debit des panneaux et d'exporter une fiche de fabrication en PDF.

## Fonctionnalites

- Gestion de projets et amenagements (CRUD, sauvegarde SQLite)
- Editeur de schema compact avec coloration syntaxique
- Editeur de parametres (dimensions, panneaux, cremailleres, tasseaux)
- Visualisation 2D en vue de face avec cotes
- Export PDF : fiche de fabrication, plan de debit, quincaillerie
- Optimisation de debit (guillotine bin packing) avec mixage multi-amenagements
- Filigrane couleur/epaisseur sur les plans de debit
- Sens du fil configurable par type de panneau
- Configurations type reutilisables (presets)

## Stack technique

| Composant  | Role                          |
|------------|-------------------------------|
| Python 3.10+ | Langage principal           |
| PyQt5      | Interface graphique           |
| SQLite     | Base de donnees locale        |
| ReportLab  | Generation PDF                |
| Pillow     | Traitement d'images (ReportLab) |

---

## Installation

### Linux (Ubuntu / Debian)

```bash
# 1. Paquets systeme
sudo apt update
sudo apt install -y python3 python3-pip python3-venv python3-pyqt5 git

# 2. Recuperer le projet
git clone <url_du_depot> ~/PlacardCAD
cd ~/PlacardCAD

# 3. Environnement virtuel (avec acces a PyQt5 systeme)
python3 -m venv venv --system-site-packages
source venv/bin/activate

# 4. Dependances
pip install -r requirements.txt

# 5. Lancer
python run.py
```

### Windows 10 / 11

**1. Installer Python**

- Telecharger depuis https://www.python.org/downloads/
- **Cocher "Add Python to PATH"** a l'installation
- Verifier dans PowerShell : `python --version`

**2. Recuperer le projet**

```powershell
git clone <url_du_depot> C:\PlacardCAD
cd C:\PlacardCAD
```

Ou telecharger le ZIP et decompresser dans `C:\PlacardCAD`.

**3. Environnement virtuel et dependances**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**4. Lancer**

```powershell
cd C:\PlacardCAD
.\venv\Scripts\Activate.ps1
python run.py
```

### Verification de l'installation

```bash
python -c "
import sys
print(f'Python {sys.version}')
try:
    from PyQt5 import QtWidgets
    print('  PyQt5 ......... OK')
except: print('  PyQt5 ......... MANQUANT')
try:
    import reportlab
    print('  ReportLab ..... OK')
except: print('  ReportLab ..... MANQUANT')
try:
    from PIL import Image
    print('  Pillow ........ OK')
except: print('  Pillow ........ MANQUANT')
"
```

### Problemes courants

| Probleme                             | Solution                                                 |
|--------------------------------------|----------------------------------------------------------|
| `ModuleNotFoundError: PyQt5`         | `pip install PyQt5` ou utiliser `--system-site-packages`  |
| `python` non reconnu (Windows)       | Reinstaller Python en cochant "Add to PATH"               |
| Interface floue sur ecran HiDPI      | `export QT_SCALE_FACTOR=1` avant de lancer                |
| Erreur lors de l'export PDF          | Verifier que `reportlab` et `Pillow` sont installes       |

---

## Mode d'emploi

### Vue d'ensemble de l'interface

L'interface se compose de trois zones principales :

```
+-------------------+-------------------------------+---------------------------+
|                   |   Schema / Parametres         |                           |
|  Arbre projets    |   (onglets)                   |    Vue 2D                 |
|  et amenagements  |                               |    (vue de face)          |
|                   |   - Editeur de schema         |                           |
|                   |   - Parametres (Dimensions,   |                           |
|                   |     Panneaux, Cremailleres,   |                           |
|                   |     Tasseaux)                 |                           |
+-------------------+-------------------------------+---------------------------+
```

La barre d'outils en haut donne acces aux actions principales :
- **Nouveau projet** / **Nouvel amenagement**
- **Actualiser vue** (recalcule la vue 2D)
- **Exporter PDF** (amenagement courant avec debit mixte du projet)
- **Exporter PDF projet** (tous les amenagements + debit mixte)
- **Exporter fiche texte** (fiche de fabrication en texte brut)
- **Optimisation debit** (dialogue multi-projets)

---

### Etape 1 : Creer un projet

1. Cliquer sur **Nouveau projet** dans la barre d'outils
2. Renseigner le nom du chantier, le client, l'adresse et les notes
3. Le projet apparait dans l'arbre a gauche

### Etape 2 : Creer un amenagement

1. Selectionner un projet dans l'arbre
2. Cliquer sur **Nouvel amenagement**
3. Donner un nom a l'amenagement (ex: "Placard chambre 1")
4. L'editeur de schema et l'editeur de parametres s'activent

### Etape 3 : Dessiner le schema compact

Le schema est un dessin ASCII qui decrit la structure du placard.
Il se saisit dans l'onglet **Schema** de la zone centrale.

#### Symboles

| Symbole | Signification                                                  |
|---------|----------------------------------------------------------------|
| `-`     | Rayon haut (uniquement en 1ere ligne)                          |
| `_`     | Rayon de compartiment (1 ligne = 1 rayon)                      |
| `\|`    | Cremaillere encastree (+ panneau mur si bord exterieur)        |
| `/`     | Cremaillere en applique (fixee directement sur le mur)         |
| `*`     | Tasseau sous le rayon a cette position                         |
| espace  | Rien (mur brut, pas de cremaillere)                            |

#### Lecture du schema

- **Ligne 1** : le rayon haut. Les `*` marquent les tasseaux, les `-` le rayon,
  les `|` ou `/` les separations entre compartiments.
- **Lignes suivantes** : chaque ligne contenant `_` represente un rayon.
  Les `|` ou `/` delimitent les compartiments.
- **Derniere ligne** (optionnelle, chiffres) : largeurs en mm par compartiment.

#### Modes de largeur

| Mode         | Description                                     | Exemple derniere ligne      |
|--------------|------------------------------------------------|-----------------------------|
| `egal`       | Tous les compartiments ont la meme largeur      | *(pas de derniere ligne)*   |
| `dimensions` | Largeur fixe pour chaque compartiment           | `300         800         700` |
| `mixte`      | Certains fixes, le reste reparti automatiquement | `300`                       |

---

### Exemples de schemas

**Exemple 1 — 3 compartiments egaux, cremailleres encastrees, tasseaux sous rayon haut**

```
*-----------*-----------*-----------*
|__________|__________|__________|
|__________|__________|__________|
|__________|__________|
```

- 3 compartiments de largeur egale
- Rayon haut sur toute la largeur avec 4 tasseaux
- Compartiment 1 : 3 rayons, C2 : 3 rayons, C3 : 2 rayons
- Cremailleres encastrees partout (`|`)
- Panneaux mur a gauche et a droite (bords exterieurs avec `|`)

**Exemple 2 — 2 compartiments, applique a gauche, largeurs fixes**

```
/-----------*-----------*
/__________|__________|
/__________|__________|
500         800
```

- Cremaillere en applique a gauche (`/`) = fixee directement sur le mur
- Cremaillere encastree entre C1 et C2 (`*`)
- Panneau mur a droite (`*` en fin de ligne)
- C1 = 500 mm, C2 = 800 mm

**Exemple 3 — Largeur mixte (C1 fixe, reste auto)**

```
*-----------*-----------*-----------*
|__________|__________|__________|
300
```

- C1 = 300 mm impose
- C2 et C3 se partagent le reste de la largeur disponible

**Exemple 4 — Schema simple sans rayon haut**

```
|__________|__________|
|__________|__________|
|__________|
```

- Pas de rayon haut (pas de premiere ligne avec `-`)
- 2 compartiments
- C1 : 3 rayons, C2 : 2 rayons

---

### Etape 4 : Regler les parametres

Basculer sur l'onglet **Parametres** dans la zone centrale. Quatre sous-onglets :

#### Dimensions
- **Hauteur** : hauteur totale du placard (sol au plafond), en mm
- **Largeur** : largeur totale entre murs, en mm
- **Profondeur** : profondeur du placard, en mm
- **Position rayon haut** : distance entre le plafond et le rayon haut, en mm

#### Panneaux
Pour chaque type (Separation, Rayon, Rayon haut, Panneau mur) :
- **Epaisseur** : epaisseur du panneau en mm
- **Couleur fab.** : reference couleur du fabricant (ex: "Chene clair", "W980 ST12")
- **Epaisseur chant** : epaisseur du chant colle sur la face visible
- **Sens du fil** : case a cocher — si coche, le panneau ne pourra pas etre pivote
  lors de l'optimisation de debit (important pour les decors bois avec veinage)
- **Retrait avant / arriere** (rayons uniquement) : espace libre devant/derriere

#### Cremailleres
- **Encastree** : dimensions et jeux de la cremaillere encastree dans une rainure
- **En applique** : dimensions de la cremaillere vissee en surface

#### Tasseaux
- Dimensions de section et biseau des tasseaux en bois

> Les parametres sont sauvegardes automatiquement. Vous pouvez sauvegarder une
> **configuration type** (bouton "Sauver config type...") pour la reutiliser
> sur d'autres amenagements.

---

### Etape 5 : Visualiser

La vue 2D a droite se met a jour automatiquement quand vous modifiez le schema
ou les parametres. Elle affiche :

- Les murs (gris) en contexte
- Les panneaux de separation (couleur bois)
- Les rayons et le rayon haut
- Les cremailleres (gris metallique)
- Les tasseaux
- Les cotes de chaque compartiment

Cliquer sur **Actualiser vue** pour forcer le rafraichissement si necessaire.

---

### Etape 6 : Exporter en PDF

#### Export amenagement (PDF)

Bouton **Exporter PDF** — genere un PDF contenant :

1. **Page de l'amenagement** :
   - Cartouche avec informations projet
   - Vue de face avec cotes et dimensions
   - Fiche de fabrication (liste des panneaux, dimensions, chants)
   - Liste de quincaillerie (cremailleres, tasseaux)
   - Resume des materiaux
2. **Pages plan de debit** :
   - Debit mixte : les pieces de **tous les amenagements du projet** sont
     regroupees pour optimiser la decoupe (moins de panneaux, moins de chutes)
   - Filigrane semi-transparent affichant la couleur et l'epaisseur du panneau
   - Chaque piece est identifiee par sa reference (P1/A1/N01, P1/A2/N03, etc.)

#### Export projet (PDF)

Bouton **Exporter PDF projet** — genere un PDF multi-pages :

1. Une page par amenagement (vue + fiche)
2. Pages plan de debit mixte pour tout le projet

#### Export fiche texte

Bouton **Exporter fiche texte** — fichier `.txt` avec la nomenclature des panneaux
et la quincaillerie.

---

### Etape 7 : Optimisation de debit avancee

Bouton **Optimisation debit** — ouvre un dialogue permettant de :

1. **Selectionner des amenagements** a travers plusieurs projets (cases a cocher)
2. **Configurer les parametres de decoupe** :
   - Dimensions du panneau brut (standard : 2800 x 2070 mm)
   - Trait de scie (largeur de lame, standard : 4 mm)
   - Surcote par cote (marge de securite, standard : 2 mm)
   - Delignage (redressage d'un bord, standard : 10 mm)
   - Sens du fil global (empeche toute rotation si coche)
3. **Exporter le plan de debit en PDF**

Le PDF genere contient :
- Un plan de decoupe par panneau de stock
- Les pieces placees avec leurs references et dimensions
- Le pourcentage de chute par panneau
- Un filigrane indiquant couleur et epaisseur
- Une page de synthese

#### Sens du fil

Le sens du fil controle si une piece peut etre pivotee a 90 degres lors du placement
sur le panneau de stock :

- **Par type de panneau** : dans les parametres de l'amenagement, onglet Panneaux,
  chaque type a sa propre case "Respecter le sens du fil". Les panneaux avec decor
  bois (veinage visible) doivent etre coches. Les panneaux unis peuvent etre decoches
  pour permettre une meilleure optimisation.
- **Global** : dans le dialogue d'optimisation de debit, la case "Respecter le sens du fil"
  agit comme un interrupteur global. Si elle est decochee, toutes les pieces peuvent
  pivoter quelle que soit leur reglage individuel.

---

## Structure du projet

```
PlacardCAD/
├── run.py                          # Point d'entree
├── requirements.txt                # Dependances Python
├── README.md                       # Ce fichier
├── CLAUDE.md                       # Specifications techniques
│
├── placardcad/
│   ├── __init__.py
│   ├── app.py                      # Lancement application PyQt5
│   ├── database.py                 # Modele SQLite + PARAMS_DEFAUT
│   ├── schema_parser.py            # Parser schema compact -> config dict
│   ├── placard_builder.py          # Geometrie 2D + fiche de fabrication
│   ├── optimisation_debit.py       # Algorithme guillotine bin packing
│   ├── pdf_export.py               # Export PDF (fiches + debit + vues)
│   ├── resources/
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py          # Fenetre principale + actions
│       ├── project_panel.py        # Arbre projets/amenagements
│       ├── schema_editor.py        # Editeur de schema compact
│       ├── params_editor.py        # Formulaire parametres a onglets
│       ├── viewer_3d.py            # Widget vue 2D de face
│       └── debit_dialog.py         # Dialogue optimisation multi-projets
│
└── tests/
```

## Elements d'un placard

```
     Plafond
  ╔══════════════════════════════════════════╗
  ║  tasseau *      tasseau *     tasseau * ║  <- Tasseaux rayon haut
  ║▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓║  <- Rayon haut
  ║                  │                      ║
  ║  ┃  ___________  ┃  _________________  ┃║  <- Rayons sur cremailleres
  ║  ┃              ┃                     ┃║
  ║  ┃  ___________  ┃  _________________  ┃║
  ║  ┃              ┃                     ┃║
  ║  ┃  ___________  ┃                     ┃║
  ║  ┃              ┃                     ┃║
  ║  panneau mur    separation      panneau mur
  ║  + cremaillere   + cremailleres   + cremaillere
  ╚══════════════════════════════════════════╝
     Sol
```

- **Panneau mur** : panneau fixe au mur lateral, recoit les cremailleres encastrees
- **Separation** : panneau vertical divisant l'espace en compartiments
- **Rayon haut** : etagere pleine largeur en haut, posee sur tasseaux
- **Rayons** : etageres reglables en hauteur via cremailleres
- **Cremaillere encastree** (`|`) : rail metallique dans une rainure
- **Cremaillere en applique** (`/`) : rail metallique visse sur le mur
- **Tasseau** (`*`) : support en bois sous un rayon, biseaute en bout

## Convention d'axes

- **X** = largeur (gauche vers droite)
- **Y** = profondeur (face avant vers mur du fond)
- **Z** = hauteur (sol vers plafond)

## Base de donnees

La base SQLite est creee automatiquement dans `~/.placardcad/placardcad.db`.
Elle contient les tables `projets`, `amenagements` et `configurations` (presets).

## Licence

Projet prive.
