# CLAUDE.md — Contexte projet PlacardCAD

## Description

PlacardCAD est une application de gestion d'aménagements intérieurs de placards (dressing, rangements).
Elle permet de concevoir des placards via un schéma compact textuel, de générer le modèle 3D dans FreeCAD,
et d'exporter une fiche de débit PDF avec vue filaire.

## Stack technique

- **Python 3.10+**
- **PyQt5** — Interface graphique standalone
- **SQLite** — Base de données locale pour projets/aménagements
- **FreeCAD 0.21+** — Moteur 3D intégré en background (via module Python)
- **ReportLab** — Export PDF (fiche de débit + vue filaire)

## Architecture

```
placardcad/
├── run.py                          # Point d'entrée
├── requirements.txt
├── placardcad/
│   ├── __init__.py
│   ├── app.py                      # Application PyQt5
│   ├── database.py                 # Modèle SQLite (projets, aménagements)
│   ├── schema_parser.py            # Parser schéma compact → config dict
│   ├── placard_builder.py          # Constructeur FreeCAD (génération 3D)
│   ├── pdf_export.py               # Export PDF
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py          # Fenêtre principale
│   │   ├── project_panel.py        # Arbre projets/aménagements
│   │   ├── schema_editor.py        # Éditeur schéma compact avec coloration
│   │   ├── params_editor.py        # Éditeur paramètres généraux
│   │   └── viewer_3d.py            # Widget vue 3D FreeCAD
│   └── resources/
└── tests/
```

## Modèle de données SQLite

### Table `projets`
- id, nom (nom du chantier), client, adresse, date_creation, date_modif, notes

### Table `amenagements`
- id, projet_id (FK), numero, nom, schema_txt, params_json, freecad_path, date_creation, date_modif, notes

## Schéma compact — Syntaxe

Le schéma est un dessin ASCII qui décrit la configuration d'un placard :

```
*-----------*-----------*-----------*
|__________|__________|__________|
|__________|__________|__________|
|__________|__________|__________|
|__________|__________|
300         800
```

### Symboles

| Symbole | Signification |
|---------|---------------|
| `-` | Rayon haut (1ère ligne uniquement) |
| `_` | Rayon de compartiment (1 ligne = 1 rayon) |
| `\|` | Crémaillère encastrée (+ panneau mur si bord extérieur) |
| `/` | Crémaillère en applique |
| `*` | Tasseau sous ce rayon à cette position |
| espace | Rien (mur brut, pas de crémaillère) |

### Lecture

- **Ligne 1** : rayon haut. `*` = tasseau, `-` = rayon, `|`/`/` = séparateur
- **Lignes suivantes** : chaque ligne avec `_` = 1 rayon. Les `|`/`/` délimitent les compartiments
- **Dernière ligne** (optionnelle, chiffres) : largeurs en mm par compartiment
  - Toutes spécifiées → mode `dimensions`
  - Certaines spécifiées → mode `mixte` (reste réparti automatiquement)
  - Absente → mode `egal` (répartition égale)

### Exemples

3 compartiments égaux, crémaillères encastrées, tasseaux rayon haut :
```
*-----------*-----------*-----------*
|__________|__________|__________|
|__________|__________|__________|
|__________|__________|
```

2 compartiments, applique à gauche, largeurs fixées :
```
/-----------*-----------*
/__________|__________|
/__________|__________|
500         800
```

Largeur mixte (C1=300mm, reste auto) :
```
*-----------*-----------*-----------*
|__________|__________|__________|
300
```

## Paramètres généraux (non couverts par le schéma)

Le schéma ne décrit que la topologie. Les paramètres physiques sont dans un dict JSON :

```python
{
    "hauteur": 2500,            # mm
    "largeur": 3000,            # mm
    "profondeur": 600,          # mm
    "rayon_haut_position": 300, # distance plafond → rayon haut

    "panneau_separation": {"epaisseur": 19, "couleur_fab": "Chêne clair", ...},
    "panneau_rayon":      {"epaisseur": 19, ...},
    "panneau_rayon_haut": {"epaisseur": 22, ...},
    "panneau_mur":        {"epaisseur": 19, ...},

    "crem_encastree": {"largeur": 16, "epaisseur": 5, "saillie": 0, ...},
    "crem_applique":  {"largeur": 25, "epaisseur_saillie": 12, ...},

    "tasseau": {"section_h": 30, "section_l": 30, "retrait_avant": 20, "biseau_longueur": 15, ...},
}
```

## Éléments d'un placard

Un placard est composé de :

- **Murs** (gauche, droit, fond) — éléments de contexte
- **Panneau mur** — panneau en bois fixé sur un mur latéral pour y encastrer des crémaillères
- **Séparations** — panneaux verticaux divisant l'espace en compartiments
- **Rayon haut** — étagère pleine largeur en haut, posée sur tasseaux
- **Rayons** — étagères réglables dans chaque compartiment
- **Crémaillères encastrées** — rails métalliques encastrés dans rainures (séparations ou panneaux mur)
- **Crémaillères en applique** — rails métalliques vissés en surface (directement sur le mur)
- **Tasseaux** — supports en bois biseautés, fixés sous le rayon haut ou sous les rayons

## Convention d'axes (FreeCAD)

- **X** = largeur (gauche → droite)
- **Y** = profondeur (0 = face avant visible, P = mur du fond)
- **Z** = hauteur (0 = sol, H = plafond)

## Fonctionnalités par phase

### Phase 1 — Interface et gestion de données
- Fenêtre PyQt5 avec arbre projets/aménagements (gauche)
- CRUD projets (nom, client, adresse, notes)
- CRUD aménagements (numéro, nom, schéma, paramètres)
- Éditeur de schéma compact avec coloration syntaxique
- Éditeur de paramètres généraux (formulaire)
- Sauvegarde automatique en SQLite

### Phase 2 — Intégration FreeCAD
- Génération du modèle 3D en background via FreeCAD Python
- Affichage vue 3D dans un widget intégré (capture ou widget OpenGL)
- Sauvegarde du fichier .FCStd avec l'aménagement
- Regénération automatique à chaque modification du schéma

### Phase 3 — Export PDF
- Vue de face en représentation filaire (projection 2D du modèle)
- Fiche de débit : nomenclature panneaux (dimensions, quantités, chants)
- Fiche quincaillerie : crémaillères, tasseaux
- Cartouche avec infos projet/chantier
- Export PDF multi-pages

## Fichiers existants

Les fichiers `placard_lib.py` et `schema_parser.py` contiennent le code fonctionnel
déjà testé dans FreeCAD. Ils doivent être refactorisés en modules propres dans `placardcad/`.

## Conventions de code

- Python 3.10+, type hints
- Docstrings en français
- Noms de variables/fonctions en snake_case
- Classes en PascalCase
- Commentaires en français
