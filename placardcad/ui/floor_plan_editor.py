"""Editeur de plan d'etage pour positionner les meubles.

Affiche une vue de dessus (plan) de la piece avec le contour des murs
et les meubles positionnes. Permet de deplacer et tourner les meubles
par drag-and-drop.

Fonctionnalites:
    - Contour de piece complexe (L, U, etc.) defini par un polygone.
    - Meubles affiches comme rectangles (largeur x profondeur).
    - Drag pour deplacer, molette sur selection pour tourner.
    - Sauvegarde du placement dans les params de chaque amenagement.
    - Sauvegarde du contour dans plan_json du projet.
"""

import json
import math

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QDoubleSpinBox,
    QLabel, QSizePolicy, QMenu, QInputDialog, QMessageBox, QDialog,
    QFormLayout, QDialogButtonBox, QSpinBox,
)
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt5.QtGui import (
    QPainter, QPen, QColor, QBrush, QFont, QFontMetrics,
    QPolygonF, QTransform,
)

from ..meuble_schema_parser import est_schema_meuble, meuble_schema_vers_config


# Couleurs distinctes pour les meubles (palette)
_COULEURS_MEUBLES = [
    "#8B7355", "#4682B4", "#6B8E23", "#CD853F",
    "#708090", "#B8860B", "#5F9EA0", "#A0522D",
    "#7B68EE", "#D2691E", "#2E8B57", "#BC8F8F",
]


class FloorPlanEditor(QWidget):
    """Editeur de plan d'etage avec positionnement interactif des meubles.

    Signals:
        placement_modifie(int, float, float, float):
            Emis quand un meuble est deplace ou tourne.
            (amenagement_id, x, y, rotation_deg)
    """

    placement_modifie = pyqtSignal(int, float, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = None
        self._projet_id = None

        # Contour de la piece : liste de (x, y) en mm
        self._contour = []

        # Meubles : liste de dicts
        # {id, nom, largeur, profondeur, x, y, rotation, couleur}
        self._meubles = []

        # Interaction
        self._selected_idx = -1
        self._dragging = False
        self._drag_start_mm = None
        self._drag_meuble_start = None

        # Edition du contour
        self._editing_contour = False
        self._selected_point = -1
        self._dragging_point = False

        # Vue (zoom / pan)
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._panning = False
        self._pan_start = QPointF()
        self._marge = 30

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        # --- Barre d'outils ---
        toolbar = QHBoxLayout()

        self._btn_contour = QPushButton("Editer piece")
        self._btn_contour.setCheckable(True)
        self._btn_contour.setToolTip(
            "Cliquer pour ajouter des points au contour.\n"
            "Glisser un point pour le deplacer.\n"
            "  Shift = angles 90°, Ctrl = angles 45°\n"
            "Double-clic sur un point = saisir coordonnees.\n"
            "Double-clic sur une cotation = saisir longueur.\n"
            "Clic droit sur un point = supprimer.")
        self._btn_contour.toggled.connect(self._toggle_contour_edit)
        toolbar.addWidget(self._btn_contour)

        toolbar.addSpacing(15)

        toolbar.addWidget(QLabel("X:"))
        self._spin_x = QDoubleSpinBox()
        self._spin_x.setRange(-99999, 99999)
        self._spin_x.setSuffix(" mm")
        self._spin_x.setEnabled(False)
        self._spin_x.valueChanged.connect(self._on_spin_x)
        toolbar.addWidget(self._spin_x)

        toolbar.addWidget(QLabel("Y:"))
        self._spin_y = QDoubleSpinBox()
        self._spin_y.setRange(-99999, 99999)
        self._spin_y.setSuffix(" mm")
        self._spin_y.setEnabled(False)
        self._spin_y.valueChanged.connect(self._on_spin_y)
        toolbar.addWidget(self._spin_y)

        toolbar.addWidget(QLabel("Rot:"))
        self._spin_rot = QDoubleSpinBox()
        self._spin_rot.setRange(0, 360)
        self._spin_rot.setSingleStep(5)
        self._spin_rot.setWrapping(True)
        self._spin_rot.setSuffix("°")
        self._spin_rot.setEnabled(False)
        self._spin_rot.valueChanged.connect(self._on_spin_rot)
        toolbar.addWidget(self._spin_rot)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Canvas (c'est ce widget lui-meme qui dessine sous le toolbar)
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("background-color: #F5F5F0;")
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

    # =================================================================
    #  API publique
    # =================================================================

    def set_projet(self, projet_id: int, db):
        """Charge le plan du projet : contour de piece + meubles positionnes."""
        self.db = db
        self._projet_id = projet_id
        self._selected_idx = -1
        self._editing_contour = False
        self._btn_contour.setChecked(False)

        # Charger le contour de la piece depuis plan_json
        self._contour = []
        if db and projet_id:
            proj = db.get_projet(projet_id)
            if proj:
                plan = _parse_plan_json(proj.get("plan_json", "{}"))
                self._contour = plan.get("contour", [])

        # Charger les meubles du projet
        self._meubles = []
        if db and projet_id:
            amenagements = db.lister_amenagements(projet_id)
            for i, am in enumerate(amenagements):
                schema = am.get("schema_txt", "")
                if not est_schema_meuble(schema):
                    continue
                params = _parse_json(am.get("params_json", "{}"))
                placement = params.get("placement", {})
                try:
                    config = meuble_schema_vers_config(schema, params)
                except Exception:
                    continue
                self._meubles.append({
                    "id": am["id"],
                    "nom": am.get("nom", f"Meuble {i+1}"),
                    "largeur": config.get("largeur", 600),
                    "profondeur": config.get("profondeur", 600),
                    "x": placement.get("x", 0.0),
                    "y": placement.get("y", 0.0),
                    "rotation": placement.get("rotation", 0.0),
                    "couleur": _COULEURS_MEUBLES[i % len(_COULEURS_MEUBLES)],
                })

        self._update_spins()
        self._reset_view()
        self.update()

    def refresh_meuble(self, amenagement_id: int):
        """Met a jour un meuble specifique (apres modif schema/params)."""
        if not self.db:
            return
        am = self.db.get_amenagement(amenagement_id)
        if not am:
            return
        schema = am.get("schema_txt", "")
        if not est_schema_meuble(schema):
            return
        params = _parse_json(am.get("params_json", "{}"))
        try:
            config = meuble_schema_vers_config(schema, params)
        except Exception:
            return

        # Trouver ou ajouter dans la liste
        for m in self._meubles:
            if m["id"] == amenagement_id:
                m["nom"] = am.get("nom", m["nom"])
                m["largeur"] = config.get("largeur", 600)
                m["profondeur"] = config.get("profondeur", 600)
                placement = params.get("placement", {})
                m["x"] = placement.get("x", m["x"])
                m["y"] = placement.get("y", m["y"])
                m["rotation"] = placement.get("rotation", m["rotation"])
                break

        self.update()

    # =================================================================
    #  Gestion du contour
    # =================================================================

    def _toggle_contour_edit(self, checked: bool):
        """Active/desactive le mode d'edition du contour de la piece."""
        self._editing_contour = checked
        if not checked:
            self._selected_point = -1
            self._save_contour()
        self._selected_idx = -1
        self._update_spins()
        self.update()

    def _save_contour(self):
        """Sauvegarde le contour dans plan_json du projet."""
        if not self.db or not self._projet_id:
            return
        plan = {"contour": self._contour}
        self.db.modifier_projet(
            self._projet_id, plan_json=json.dumps(plan, ensure_ascii=False)
        )

    # =================================================================
    #  Spinbox callbacks
    # =================================================================

    def _on_spin_x(self, val):
        if self._selected_idx < 0 or self._selected_idx >= len(self._meubles):
            return
        m = self._meubles[self._selected_idx]
        m["x"] = val
        self._emit_placement(m)
        self.update()

    def _on_spin_y(self, val):
        if self._selected_idx < 0 or self._selected_idx >= len(self._meubles):
            return
        m = self._meubles[self._selected_idx]
        m["y"] = val
        self._emit_placement(m)
        self.update()

    def _on_spin_rot(self, val):
        if self._selected_idx < 0 or self._selected_idx >= len(self._meubles):
            return
        m = self._meubles[self._selected_idx]
        m["rotation"] = val
        self._emit_placement(m)
        self.update()

    def _update_spins(self):
        """Met a jour les spinboxes en fonction de la selection."""
        has_sel = 0 <= self._selected_idx < len(self._meubles)
        self._spin_x.setEnabled(has_sel)
        self._spin_y.setEnabled(has_sel)
        self._spin_rot.setEnabled(has_sel)
        if has_sel:
            m = self._meubles[self._selected_idx]
            self._spin_x.blockSignals(True)
            self._spin_y.blockSignals(True)
            self._spin_rot.blockSignals(True)
            self._spin_x.setValue(m["x"])
            self._spin_y.setValue(m["y"])
            self._spin_rot.setValue(m["rotation"])
            self._spin_x.blockSignals(False)
            self._spin_y.blockSignals(False)
            self._spin_rot.blockSignals(False)

    def _emit_placement(self, m: dict):
        """Emet le signal placement_modifie."""
        self.placement_modifie.emit(m["id"], m["x"], m["y"], m["rotation"])

    # =================================================================
    #  Transformations vue -> mm et mm -> vue
    # =================================================================

    def _scene_bounds(self) -> tuple[float, float, float, float]:
        """Retourne (min_x, min_y, max_x, max_y) en mm englobant tout."""
        pts = list(self._contour)
        for m in self._meubles:
            corners = self._meuble_corners(m)
            pts.extend(corners)
        if not pts:
            return 0, 0, 4000, 3000  # defaut
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)

    def _meuble_corners(self, m: dict) -> list[tuple[float, float]]:
        """Retourne les 4 coins du meuble en coordonnees monde (mm)."""
        cx, cy = m["x"], m["y"]
        L, P = m["largeur"], m["profondeur"]
        angle_rad = math.radians(m["rotation"])
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        # Coins relatifs au centre (0,0) du meuble
        corners_local = [
            (0, 0), (L, 0), (L, P), (0, P)
        ]
        result = []
        for lx, ly in corners_local:
            rx = cx + lx * cos_a - ly * sin_a
            ry = cy + lx * sin_a + ly * cos_a
            result.append((rx, ry))
        return result

    def _get_transform(self) -> tuple[float, float, float]:
        """Retourne (scale, offset_x, offset_y) pour mm -> pixels."""
        bx0, by0, bx1, by1 = self._scene_bounds()
        scene_w = max(bx1 - bx0, 100)
        scene_h = max(by1 - by0, 100)

        # Zone dessin = widget sous le toolbar (environ 50px de haut)
        view_w = self.width() - 2 * self._marge
        view_h = self.height() - 2 * self._marge - 40  # toolbar

        if view_w <= 0 or view_h <= 0:
            return 0.1, self._marge, self._marge + 40

        padding = max(scene_w, scene_h) * 0.1
        total_w = scene_w + 2 * padding
        total_h = scene_h + 2 * padding

        scale = min(view_w / total_w, view_h / total_h) * self._zoom

        # Centrage
        ox = self._marge + (view_w - total_w * scale) / 2 + (padding - bx0) * scale
        oy = self._marge + 40 + (view_h - total_h * scale) / 2 + (padding - by0) * scale

        ox += self._pan_x
        oy += self._pan_y

        return scale, ox, oy

    def _mm_to_px(self, x_mm: float, y_mm: float) -> QPointF:
        """Convertit mm -> pixels ecran."""
        scale, ox, oy = self._get_transform()
        return QPointF(ox + x_mm * scale, oy + y_mm * scale)

    def _px_to_mm(self, px: float, py: float) -> tuple[float, float]:
        """Convertit pixels ecran -> mm."""
        scale, ox, oy = self._get_transform()
        if scale < 1e-9:
            return 0, 0
        return (px - ox) / scale, (py - oy) / scale

    def _reset_view(self):
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0

    # =================================================================
    #  Hit-testing
    # =================================================================

    def _hit_meuble(self, mx_mm: float, my_mm: float) -> int:
        """Retourne l'index du meuble sous le point (mm), ou -1."""
        # Parcourir en ordre inverse (dernier dessine = au-dessus)
        for i in range(len(self._meubles) - 1, -1, -1):
            if self._point_in_meuble(mx_mm, my_mm, self._meubles[i]):
                return i
        return -1

    def _point_in_meuble(self, px: float, py: float, m: dict) -> bool:
        """Teste si un point (mm) est dans le rectangle tourne du meuble."""
        # Transformer le point dans le repere local du meuble
        dx = px - m["x"]
        dy = py - m["y"]
        angle_rad = -math.radians(m["rotation"])
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        lx = dx * cos_a - dy * sin_a
        ly = dx * sin_a + dy * cos_a
        return 0 <= lx <= m["largeur"] and 0 <= ly <= m["profondeur"]

    def _hit_contour_point(self, mx_mm: float, my_mm: float) -> int:
        """Retourne l'index du point de contour sous le curseur, ou -1."""
        scale, _, _ = self._get_transform()
        seuil = max(8 / scale, 20)  # rayon en mm
        for i, (cx, cy) in enumerate(self._contour):
            if math.hypot(mx_mm - cx, my_mm - cy) < seuil:
                return i
        return -1

    # =================================================================
    #  Evenements souris
    # =================================================================

    def wheelEvent(self, event):
        """Zoom centre sur le curseur. Si meuble selectionne: molette = rotation."""
        # Rotation du meuble selectionne avec Ctrl+molette
        if (event.modifiers() & Qt.ControlModifier) and self._selected_idx >= 0:
            delta = event.angleDelta().y()
            step = 5.0 if not (event.modifiers() & Qt.ShiftModifier) else 1.0
            m = self._meubles[self._selected_idx]
            if delta > 0:
                m["rotation"] = (m["rotation"] + step) % 360
            elif delta < 0:
                m["rotation"] = (m["rotation"] - step) % 360
            self._emit_placement(m)
            self._update_spins()
            self.update()
            return

        # Zoom de la vue
        pos = event.pos()
        old_zoom = self._zoom
        delta = event.angleDelta().y()
        if delta > 0:
            factor = 1.15
        elif delta < 0:
            factor = 1 / 1.15
        else:
            return

        new_zoom = max(0.1, min(old_zoom * factor, 30.0))
        ratio = new_zoom / old_zoom
        self._pan_x = pos.x() - ratio * (pos.x() - self._pan_x)
        self._pan_y = pos.y() - ratio * (pos.y() - self._pan_y)
        self._zoom = new_zoom
        self.update()

    def mousePressEvent(self, event):
        mx, my = self._px_to_mm(event.pos().x(), event.pos().y())

        # --- Mode edition contour ---
        if self._editing_contour:
            if event.button() == Qt.LeftButton:
                idx = self._hit_contour_point(mx, my)
                if idx >= 0:
                    # Commencer a deplacer ce point
                    self._selected_point = idx
                    self._dragging_point = True
                else:
                    # Ajouter un nouveau point
                    # Inserer apres le point le plus proche du segment
                    insert_idx = self._best_insert_index(mx, my)
                    self._contour.insert(insert_idx, (round(mx), round(my)))
                    self._selected_point = insert_idx
                    self._dragging_point = True
                self.update()
                return
            elif event.button() == Qt.MiddleButton:
                self._panning = True
                self._pan_start = event.pos()
                self.setCursor(Qt.ClosedHandCursor)
                return
            return

        # --- Mode normal ---
        if event.button() == Qt.LeftButton:
            idx = self._hit_meuble(mx, my)
            if idx >= 0:
                # Selectionner et commencer le drag
                self._selected_idx = idx
                self._dragging = True
                m = self._meubles[idx]
                self._drag_start_mm = (mx, my)
                self._drag_meuble_start = (m["x"], m["y"])
                self._update_spins()
                self.update()
            else:
                # Deselectionner
                self._selected_idx = -1
                self._update_spins()
                self.update()
        elif event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.pos() - self._pan_start
            self._pan_x += delta.x()
            self._pan_y += delta.y()
            self._pan_start = event.pos()
            self.update()
            return

        mx, my = self._px_to_mm(event.pos().x(), event.pos().y())

        # Drag point de contour (avec contraintes d'angle)
        if self._dragging_point and self._selected_point >= 0:
            n = len(self._contour)
            if n >= 2:
                # Point de reference = point precedent
                ref_idx = (self._selected_point - 1) % n
                ref_x, ref_y = self._contour[ref_idx]
                mods = event.modifiers()
                if mods & Qt.ShiftModifier:
                    # Contrainte 90° (horizontal / vertical)
                    mx, my = _snap_to_angles(ref_x, ref_y, mx, my, 4)
                elif mods & Qt.ControlModifier:
                    # Contrainte 45°
                    mx, my = _snap_to_angles(ref_x, ref_y, mx, my, 8)
            self._contour[self._selected_point] = (round(mx), round(my))
            self.update()
            return

        # Drag meuble
        if self._dragging and self._selected_idx >= 0:
            m = self._meubles[self._selected_idx]
            dx = mx - self._drag_start_mm[0]
            dy = my - self._drag_start_mm[1]
            m["x"] = round(self._drag_meuble_start[0] + dx)
            m["y"] = round(self._drag_meuble_start[1] + dy)
            self._update_spins()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            return

        if self._dragging_point:
            self._dragging_point = False
            self._save_contour()
            return

        if self._dragging and self._selected_idx >= 0:
            self._dragging = False
            m = self._meubles[self._selected_idx]
            self._emit_placement(m)
            self._update_spins()

    def mouseDoubleClickEvent(self, event):
        if event.button() != Qt.LeftButton:
            return

        # --- Mode edition contour : double-clic sur point ou cotation ---
        if self._editing_contour and self._contour:
            mx, my = self._px_to_mm(event.pos().x(), event.pos().y())

            # Double-clic sur un point -> editer coordonnees
            idx = self._hit_contour_point(mx, my)
            if idx >= 0:
                self._edit_point_coords(idx)
                return

            # Double-clic pres d'un segment -> editer longueur
            seg_idx = self._hit_segment_midpoint(mx, my)
            if seg_idx >= 0:
                self._edit_segment_length(seg_idx)
                return

        # Sinon : reset vue
        self._reset_view()
        self.update()

    def contextMenuEvent(self, event):
        """Menu contextuel: supprimer point de contour."""
        if self._editing_contour:
            mx, my = self._px_to_mm(event.pos().x(), event.pos().y())
            idx = self._hit_contour_point(mx, my)
            if idx >= 0:
                menu = QMenu(self)
                act_del = menu.addAction("Supprimer ce point")
                action = menu.exec_(event.globalPos())
                if action == act_del:
                    del self._contour[idx]
                    self._selected_point = -1
                    self._save_contour()
                    self.update()
            return

        # Menu sur meuble selectionne
        if self._selected_idx >= 0:
            m = self._meubles[self._selected_idx]
            menu = QMenu(self)
            act_90 = menu.addAction("Rotation 90°")
            act_180 = menu.addAction("Rotation 180°")
            act_270 = menu.addAction("Rotation 270°")
            act_0 = menu.addAction("Rotation 0°")
            action = menu.exec_(event.globalPos())
            if action == act_90:
                m["rotation"] = 90
            elif action == act_180:
                m["rotation"] = 180
            elif action == act_270:
                m["rotation"] = 270
            elif action == act_0:
                m["rotation"] = 0
            else:
                return
            self._emit_placement(m)
            self._update_spins()
            self.update()

    def keyPressEvent(self, event):
        """Fleches pour deplacer finement le meuble selectionne."""
        if self._selected_idx < 0:
            return
        m = self._meubles[self._selected_idx]
        step = 10 if not (event.modifiers() & Qt.ShiftModifier) else 1
        moved = False
        if event.key() == Qt.Key_Left:
            m["x"] -= step
            moved = True
        elif event.key() == Qt.Key_Right:
            m["x"] += step
            moved = True
        elif event.key() == Qt.Key_Up:
            m["y"] -= step
            moved = True
        elif event.key() == Qt.Key_Down:
            m["y"] += step
            moved = True
        if moved:
            self._emit_placement(m)
            self._update_spins()
            self.update()

    # =================================================================
    #  Utilitaires contour
    # =================================================================

    def _hit_segment_midpoint(self, mx_mm: float, my_mm: float) -> int:
        """Retourne l'index du segment dont le milieu est proche du curseur, ou -1."""
        n = len(self._contour)
        if n < 2:
            return -1
        scale, _, _ = self._get_transform()
        seuil = max(15 / scale, 40)  # rayon en mm
        for i in range(n):
            ax, ay = self._contour[i]
            bx, by = self._contour[(i + 1) % n]
            mid_x = (ax + bx) / 2
            mid_y = (ay + by) / 2
            if math.hypot(mx_mm - mid_x, my_mm - mid_y) < seuil:
                return i
        return -1

    def _edit_point_coords(self, idx: int):
        """Ouvre un dialogue pour saisir les coordonnees X,Y d'un point."""
        cx, cy = self._contour[idx]
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Coordonnees du point {idx + 1}")
        form = QFormLayout(dlg)

        spin_px = QSpinBox()
        spin_px.setRange(-99999, 99999)
        spin_px.setSuffix(" mm")
        spin_px.setValue(int(cx))
        form.addRow("X :", spin_px)

        spin_py = QSpinBox()
        spin_py.setRange(-99999, 99999)
        spin_py.setSuffix(" mm")
        spin_py.setValue(int(cy))
        form.addRow("Y :", spin_py)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec_() == QDialog.Accepted:
            self._contour[idx] = (spin_px.value(), spin_py.value())
            self._save_contour()
            self.update()

    def _edit_segment_length(self, seg_idx: int):
        """Ouvre un dialogue pour saisir la longueur d'un segment.

        Deplace le point d'arrivee pour atteindre la longueur demandee
        tout en gardant la meme direction.
        """
        n = len(self._contour)
        ax, ay = self._contour[seg_idx]
        bx, by = self._contour[(seg_idx + 1) % n]
        longueur_actuelle = math.hypot(bx - ax, by - ay)

        val, ok = QInputDialog.getInt(
            self,
            f"Longueur du segment {seg_idx + 1}",
            "Nouvelle longueur (mm) :",
            int(round(longueur_actuelle)),
            1, 99999,
        )
        if not ok:
            return

        if longueur_actuelle < 1:
            return

        # Garder la direction, ajuster le point d'arrivee
        dx = bx - ax
        dy = by - ay
        ratio = val / longueur_actuelle
        new_bx = ax + dx * ratio
        new_by = ay + dy * ratio
        self._contour[(seg_idx + 1) % n] = (round(new_bx), round(new_by))
        self._save_contour()
        self.update()

    def _best_insert_index(self, mx: float, my: float) -> int:
        """Trouve le meilleur index d'insertion pour un nouveau point."""
        if len(self._contour) < 2:
            return len(self._contour)
        best_dist = float("inf")
        best_idx = len(self._contour)
        n = len(self._contour)
        for i in range(n):
            ax, ay = self._contour[i]
            bx, by = self._contour[(i + 1) % n]
            d = _dist_point_segment(mx, my, ax, ay, bx, by)
            if d < best_dist:
                best_dist = d
                best_idx = (i + 1) % (n + 1)
                if best_idx == 0:
                    best_idx = n
        return best_idx

    # =================================================================
    #  Dessin
    # =================================================================

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Zone de dessin commence sous le toolbar (~40px)
        if not self._contour and not self._meubles:
            painter.setPen(QColor("#999"))
            font = QFont()
            font.setPointSize(11)
            painter.setFont(font)
            painter.drawText(
                self.rect(), Qt.AlignCenter,
                "Cliquez 'Editer piece' pour tracer le contour\n"
                "puis positionnez les meubles par glisser-deposer"
            )
            painter.end()
            return

        scale, ox, oy = self._get_transform()

        # --- Dessiner le contour de la piece ---
        if self._contour and len(self._contour) >= 2:
            pen_mur = QPen(QColor("#333333"), 2)
            brush_sol = QBrush(QColor("#F0EDE6"))
            painter.setPen(pen_mur)
            painter.setBrush(brush_sol)

            poly = QPolygonF()
            for cx, cy in self._contour:
                poly.append(QPointF(ox + cx * scale, oy + cy * scale))
            if len(self._contour) >= 3:
                painter.drawPolygon(poly)
            else:
                painter.drawPolyline(poly)

            # Dessiner les points si en mode edition
            if self._editing_contour:
                for i, (cx, cy) in enumerate(self._contour):
                    px_pt = ox + cx * scale
                    py_pt = oy + cy * scale
                    r = 5
                    if i == self._selected_point:
                        painter.setBrush(QBrush(QColor("#FF4444")))
                        r = 7
                    else:
                        painter.setBrush(QBrush(QColor("#4488FF")))
                    painter.setPen(QPen(QColor("#222"), 1))
                    painter.drawEllipse(QPointF(px_pt, py_pt), r, r)

                    # Afficher les coordonnees du point
                    painter.setPen(QColor("#666"))
                    font_sm = QFont()
                    font_sm.setPointSize(7)
                    painter.setFont(font_sm)
                    painter.drawText(
                        int(px_pt + 10), int(py_pt - 5),
                        f"({cx}, {cy})"
                    )

            # Cotations des segments du contour (affichees dans les 2 modes)
            painter.setPen(QColor("#888"))
            font_cot = QFont()
            font_cot.setPointSize(7)
            painter.setFont(font_cot)
            n = len(self._contour)
            for i in range(n):
                ax, ay = self._contour[i]
                bx, by = self._contour[(i + 1) % n]
                longueur = math.hypot(bx - ax, by - ay)
                if longueur < 50:
                    continue
                mid_px = ox + (ax + bx) / 2 * scale
                mid_py = oy + (ay + by) / 2 * scale
                # Decaler le texte perpendiculairement au segment
                dx_s, dy_s = bx - ax, by - ay
                norm = math.hypot(dx_s, dy_s)
                if norm > 0:
                    nx, ny = -dy_s / norm, dx_s / norm
                    offset_px = 12  # pixels de decalage
                    mid_px += nx * offset_px
                    mid_py += ny * offset_px
                painter.drawText(
                    int(mid_px - 20), int(mid_py - 5),
                    f"{longueur:.0f}"
                )

        # --- Dessiner les meubles ---
        font_meuble = QFont()
        font_meuble.setPointSize(8)
        fm = QFontMetrics(font_meuble)

        for i, m in enumerate(self._meubles):
            self._draw_meuble(painter, m, scale, ox, oy,
                              selected=(i == self._selected_idx),
                              font=font_meuble, fm=fm)

        painter.end()

    def _draw_meuble(self, painter: QPainter, m: dict,
                     scale: float, ox: float, oy: float,
                     selected: bool, font: QFont, fm: QFontMetrics):
        """Dessine un meuble (rectangle tourne) sur le plan."""
        L = m["largeur"] * scale
        P = m["profondeur"] * scale
        cx = ox + m["x"] * scale
        cy = oy + m["y"] * scale

        painter.save()
        painter.translate(cx, cy)
        painter.rotate(m["rotation"])

        # Rectangle du meuble
        couleur = QColor(m["couleur"])
        if selected:
            pen = QPen(QColor("#FF0000"), 2.5)
            brush_col = QColor(couleur)
            brush_col.setAlpha(160)
        else:
            pen = QPen(couleur.darker(130), 1.5)
            brush_col = QColor(couleur)
            brush_col.setAlpha(80)

        painter.setPen(pen)
        painter.setBrush(QBrush(brush_col))
        painter.drawRect(QRectF(0, 0, L, P))

        # Indicateur de face avant (trait rouge cote Y=0)
        painter.setPen(QPen(QColor("#CC0000"), 3))
        painter.drawLine(QPointF(0, 0), QPointF(L, 0))

        # Label du meuble
        painter.setPen(QColor("#222"))
        painter.setFont(font)
        label = m["nom"]
        tw = fm.horizontalAdvance(label)
        th = fm.height()
        # Centrer le texte dans le rectangle
        if L > tw + 4 and P > th + 4:
            painter.drawText(
                QRectF(0, 0, L, P),
                Qt.AlignCenter,
                label
            )
        elif L > 20 and P > 10:
            # Texte plus petit
            small_font = QFont()
            small_font.setPointSize(6)
            painter.setFont(small_font)
            painter.drawText(QRectF(0, 0, L, P), Qt.AlignCenter, label)

        # Dimensions
        painter.setPen(QColor("#666"))
        dim_font = QFont()
        dim_font.setPointSize(6)
        painter.setFont(dim_font)
        dim_text = f"{m['largeur']}x{m['profondeur']}"
        painter.drawText(
            QRectF(0, P * 0.6, L, P * 0.4),
            Qt.AlignCenter,
            dim_text
        )

        painter.restore()


# =================================================================
#  Fonctions utilitaires
# =================================================================

def _parse_json(s: str) -> dict:
    """Parse JSON en dict, retourne {} en cas d'erreur."""
    try:
        return json.loads(s) if s else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _parse_plan_json(s: str) -> dict:
    """Parse plan_json, retourne {} en cas d'erreur."""
    return _parse_json(s)


def _dist_point_segment(px, py, ax, ay, bx, by):
    """Distance d'un point (px, py) a un segment (ax,ay)-(bx,by)."""
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def _snap_to_angles(ref_x: float, ref_y: float,
                    raw_x: float, raw_y: float,
                    divisions: int) -> tuple[float, float]:
    """Contraint un point sur les angles reguliers depuis un point de reference.

    Args:
        ref_x, ref_y: Point de reference (point precedent du contour).
        raw_x, raw_y: Position brute de la souris.
        divisions: Nombre de divisions du cercle (4 = 90°, 8 = 45°).

    Returns:
        (x, y) contraint sur l'angle le plus proche.
    """
    dx = raw_x - ref_x
    dy = raw_y - ref_y
    dist = math.hypot(dx, dy)
    if dist < 1:
        return raw_x, raw_y

    raw_angle = math.atan2(dy, dx)
    step = 2 * math.pi / divisions

    # Trouver l'angle autorise le plus proche
    best_angle = round(raw_angle / step) * step

    snapped_x = ref_x + dist * math.cos(best_angle)
    snapped_y = ref_y + dist * math.sin(best_angle)
    return snapped_x, snapped_y
