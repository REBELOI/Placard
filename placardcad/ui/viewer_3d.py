"""
Widget de vue de face (2D filaire) du placard.
Dessine la geometrie calculee par placard_builder.generer_geometrie_2d().
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush, QFont, QFontMetrics


class PlacardViewer(QWidget):
    """Widget de visualisation du placard en vue de face."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rects = []         # list[Rect] depuis placard_builder
        self._placard_w = 3000   # largeur du placard en mm
        self._placard_h = 2500   # hauteur du placard en mm
        self._marge = 40         # marge en pixels
        self._show_labels = True
        self._show_dimensions = True

        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("background-color: white;")

    def set_geometrie(self, rects: list, largeur: float, hauteur: float):
        """Met a jour la geometrie a afficher."""
        self._rects = rects
        self._placard_w = largeur
        self._placard_h = hauteur
        self.update()

    def clear(self):
        """Efface la vue."""
        self._rects = []
        self.update()

    def _get_transform(self) -> tuple:
        """Calcule l'echelle et le decalage pour le dessin."""
        if self._placard_w <= 0 or self._placard_h <= 0:
            return 1.0, self._marge, self._marge

        # Zone de dessin disponible
        view_w = self.width() - 2 * self._marge
        view_h = self.height() - 2 * self._marge

        if view_w <= 0 or view_h <= 0:
            return 1.0, self._marge, self._marge

        # Prendre en compte les murs
        mur_ep = 50
        total_w = self._placard_w + 2 * mur_ep
        total_h = self._placard_h + 2 * mur_ep

        scale_x = view_w / total_w
        scale_y = view_h / total_h
        scale = min(scale_x, scale_y)

        # Centrer
        offset_x = self._marge + (view_w - total_w * scale) / 2 + mur_ep * scale
        offset_y = self._marge + (view_h - total_h * scale) / 2 + mur_ep * scale

        return scale, offset_x, offset_y

    def _to_screen(self, x: float, z: float, scale: float,
                   offset_x: float, offset_y: float) -> QPointF:
        """Convertit coordonnees placard (mm) en pixels ecran.
        Z est inverse (Z=0 en bas -> en bas de l'ecran)."""
        sx = offset_x + x * scale
        sy = offset_y + (self._placard_h - z) * scale
        return QPointF(sx, sy)

    def paintEvent(self, event):
        if not self._rects:
            painter = QPainter(self)
            painter.setPen(QColor("#999"))
            font = QFont()
            font.setPointSize(12)
            painter.setFont(font)
            painter.drawText(
                self.rect(), Qt.AlignCenter,
                "Editez le schema pour voir l'apercu"
            )
            painter.end()
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        scale, ox, oy = self._get_transform()

        # Couleurs de type d'element
        type_pens = {
            "mur": (QColor("#D5D5D0"), QColor("#E8E8E4"), 1),
            "separation": (QColor("#8B7355"), QColor("#D2B48C"), 2),
            "rayon_haut": (QColor("#8B7355"), QColor("#DEB887"), 1),
            "rayon": (QColor("#8B7355"), QColor("#D2B48C"), 1),
            "cremaillere": (QColor("#708090"), QColor("#A0A0A0"), 1),
            "panneau_mur": (QColor("#8B7355"), QColor("#D2B48C"), 1),
            "tasseau": (QColor("#8B6914"), QColor("#DAA520"), 1),
        }

        # Dessiner les rectangles par ordre de couche
        ordre = ["mur", "panneau_mur", "separation", "rayon_haut", "rayon", "cremaillere", "tasseau"]
        rects_par_type = {}
        for r in self._rects:
            rects_par_type.setdefault(r.type_elem, []).append(r)

        for type_elem in ordre:
            if type_elem not in rects_par_type:
                continue
            pen_color, fill_color, pen_width = type_pens.get(
                type_elem, (QColor("#333"), QColor("#CCC"), 1)
            )

            for r in rects_par_type[type_elem]:
                p1 = self._to_screen(r.x, r.y + r.h, scale, ox, oy)
                p2 = self._to_screen(r.x + r.w, r.y, scale, ox, oy)

                rect_screen = QRectF(p1, p2)

                # Remplissage
                if type_elem == "mur":
                    painter.setBrush(QBrush(fill_color, Qt.Dense4Pattern))
                else:
                    painter.setBrush(QBrush(fill_color))

                painter.setPen(QPen(pen_color, pen_width))
                painter.drawRect(rect_screen)

        # --- Cotations ---
        if self._show_dimensions:
            self._dessiner_cotations(painter, scale, ox, oy)

        painter.end()

    def _dessiner_cotations(self, painter: QPainter, scale: float,
                            ox: float, oy: float):
        """Dessine les cotations (hauteur, largeur, compartiments)."""
        pen = QPen(QColor("#333333"), 1, Qt.DashLine)
        painter.setPen(pen)

        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        fm = QFontMetrics(font)

        H = self._placard_h
        L = self._placard_w

        # Cotation largeur totale (en bas)
        y_cot = -30
        p_left = self._to_screen(0, y_cot, scale, ox, oy)
        p_right = self._to_screen(L, y_cot, scale, ox, oy)

        painter.setPen(QPen(QColor("#333"), 1))
        painter.drawLine(p_left, p_right)
        # Traits de rappel
        p_top_l = self._to_screen(0, 0, scale, ox, oy)
        p_top_r = self._to_screen(L, 0, scale, ox, oy)
        painter.setPen(QPen(QColor("#999"), 1, Qt.DotLine))
        painter.drawLine(p_top_l, p_left)
        painter.drawLine(p_top_r, p_right)

        # Texte largeur
        painter.setPen(QPen(QColor("#333"), 1))
        text_l = f"{L:.0f}"
        text_w = fm.horizontalAdvance(text_l)
        mid_x = (p_left.x() + p_right.x()) / 2 - text_w / 2
        painter.drawText(QPointF(mid_x, p_left.y() + fm.height()), text_l)

        # Cotation hauteur (a gauche)
        x_cot = -30
        p_bottom = self._to_screen(x_cot, 0, scale, ox, oy)
        p_top = self._to_screen(x_cot, H, scale, ox, oy)

        painter.setPen(QPen(QColor("#333"), 1))
        painter.drawLine(p_bottom, p_top)
        # Traits de rappel
        p_orig_b = self._to_screen(0, 0, scale, ox, oy)
        p_orig_t = self._to_screen(0, H, scale, ox, oy)
        painter.setPen(QPen(QColor("#999"), 1, Qt.DotLine))
        painter.drawLine(p_orig_b, p_bottom)
        painter.drawLine(p_orig_t, p_top)

        # Texte hauteur
        painter.setPen(QPen(QColor("#333"), 1))
        text_h = f"{H:.0f}"
        mid_y = (p_bottom.y() + p_top.y()) / 2 + fm.height() / 2
        painter.save()
        painter.translate(p_top.x() - 5, mid_y)
        painter.rotate(-90)
        painter.drawText(0, 0, text_h)
        painter.restore()
