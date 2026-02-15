"""
Editeur de schema compact avec coloration syntaxique et aide contextuelle.
"""

from PyQt5.QtWidgets import (
    QPlainTextEdit, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextBrowser, QSplitter,
)
from PyQt5.QtCore import pyqtSignal, Qt, QRect
from PyQt5.QtGui import (
    QSyntaxHighlighter, QTextCharFormat, QColor, QFont,
    QPainter, QTextFormat
)


# --- Textes d'aide contextuelle ---

AIDE_PLACARD = """\
<h3>Syntaxe schema Placard</h3>
<p>Le schema est un dessin ASCII qui decrit la configuration du placard :</p>
<pre style="background:#f5f5f5; padding:6px;">
*-----------*-----------*-----------*
|__________|__________|__________|
|__________|__________|__________|
|__________|__________|
300         800
</pre>

<h4>Symboles</h4>
<table cellpadding="4" style="border-collapse:collapse;">
<tr><td style="color:#2196F3;font-weight:bold;font-size:14px;">|</td>
    <td>Cremaillere encastree (+ panneau mur si bord exterieur)</td></tr>
<tr><td style="color:#FF9800;font-weight:bold;font-size:14px;">/</td>
    <td>Cremaillere en applique (vissee sur le mur)</td></tr>
<tr><td style="color:#4CAF50;font-weight:bold;font-size:14px;">*</td>
    <td>Tasseau sous le rayon haut a cette position</td></tr>
<tr><td style="color:#795548;font-weight:bold;font-size:14px;">-</td>
    <td>Rayon haut (1ere ligne uniquement)</td></tr>
<tr><td style="color:#795548;font-weight:bold;font-size:14px;">_</td>
    <td>Rayon de compartiment (1 ligne = 1 rayon)</td></tr>
<tr><td style="color:#E91E63;font-weight:bold;font-size:14px;">123</td>
    <td>Largeurs en mm (derniere ligne, optionnelle)</td></tr>
<tr><td style="font-size:14px;">(espace)</td>
    <td>Mur brut, pas de cremaillere</td></tr>
</table>

<h4>Lecture du schema</h4>
<ul>
<li><b>Ligne 1</b> : rayon haut. <code>*</code> = tasseau, <code>-</code> = rayon,
    <code>|</code>/<code>/</code> = separateur</li>
<li><b>Lignes suivantes</b> : chaque ligne avec <code>_</code> = 1 rayon par compartiment</li>
<li><b>Derniere ligne</b> (optionnelle) : largeurs en mm</li>
</ul>

<h4>Modes de largeur</h4>
<ul>
<li><b>Egal</b> : pas de ligne de largeurs &rarr; repartition egale</li>
<li><b>Dimensions</b> : toutes les largeurs specifiees &rarr; dimensions exactes</li>
<li><b>Mixte</b> : certaines largeurs specifiees &rarr; reste reparti automatiquement</li>
</ul>

<h4>Exemples</h4>
<p><i>3 compartiments egaux, cremailleres encastrees :</i></p>
<pre style="background:#f5f5f5; padding:4px;">*-----------*-----------*-----------*
|__________|__________|__________|
|__________|__________|__________|
|__________|__________|</pre>

<p><i>2 compartiments, applique a gauche, largeurs fixees :</i></p>
<pre style="background:#f5f5f5; padding:4px;">/-----------*-----------*
/__________|__________|
/__________|__________|
500         800</pre>
"""

AIDE_MEUBLE = """\
<h3>Syntaxe schema Meuble</h3>
<p>Le schema meuble commence obligatoirement par <code>#MEUBLE</code> :</p>
<pre style="background:#f5f5f5; padding:6px;">
#MEUBLE
| PP  | TTT |
| --  |     |
| --  |     |
  600   400
</pre>

<h4>Symboles</h4>
<table cellpadding="4" style="border-collapse:collapse;">
<tr><td style="font-weight:bold;">P</td>
    <td>Porte (PP = 2 portes)</td></tr>
<tr><td style="font-weight:bold;">T</td>
    <td>Tiroir hauteur par defaut (TT = 2, TTT = 3...)</td></tr>
<tr><td style="font-weight:bold;">F</td>
    <td>Tiroir LEGRABOX hauteur F (257 mm)</td></tr>
<tr><td style="font-weight:bold;">K</td>
    <td>Tiroir LEGRABOX hauteur K (128.5 mm)</td></tr>
<tr><td style="font-weight:bold;">C</td>
    <td>Tiroir LEGRABOX hauteur C (193 mm)</td></tr>
<tr><td style="font-weight:bold;">M</td>
    <td>Tiroir LEGRABOX hauteur M (90.5 mm)</td></tr>
<tr><td style="font-weight:bold;">N</td>
    <td>Niche (sans facade)</td></tr>
<tr><td style="font-weight:bold;">-- ou ==</td>
    <td>Etagere</td></tr>
<tr><td style="font-weight:bold;">+</td>
    <td>Combine des groupes (de bas en haut)</td></tr>
<tr><td style="color:#E91E63;font-weight:bold;">123</td>
    <td>Largeurs en mm (derniere ligne)</td></tr>
</table>

<h4>Lecture du schema</h4>
<ul>
<li>Chaque colonne entre <code>|</code> est un compartiment</li>
<li>Les lettres a l'interieur definissent les facades/tiroirs</li>
<li><code>--</code> ou <code>==</code> represente une etagere</li>
<li>Utiliser <code>+</code> pour combiner des elements verticalement</li>
</ul>

<h4>Exemple complet</h4>
<pre style="background:#f5f5f5; padding:4px;">#MEUBLE
| PP  | TTT |
| --  |     |
| --  |     |
  600   400</pre>
<p>= 1 compartiment 600mm avec 2 portes + 2 etageres,
1 compartiment 400mm avec 3 tiroirs.</p>
"""


class SchemaHighlighter(QSyntaxHighlighter):
    """Coloration syntaxique pour le schema compact de placard."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Format pour les cremailleres encastrees |
        self.fmt_encastree = QTextCharFormat()
        self.fmt_encastree.setForeground(QColor("#2196F3"))
        self.fmt_encastree.setFontWeight(QFont.Bold)

        # Format pour les cremailleres applique /
        self.fmt_applique = QTextCharFormat()
        self.fmt_applique.setForeground(QColor("#FF9800"))
        self.fmt_applique.setFontWeight(QFont.Bold)

        # Format pour les tasseaux *
        self.fmt_tasseau = QTextCharFormat()
        self.fmt_tasseau.setForeground(QColor("#4CAF50"))
        self.fmt_tasseau.setFontWeight(QFont.Bold)

        # Format pour les rayons - et _
        self.fmt_rayon = QTextCharFormat()
        self.fmt_rayon.setForeground(QColor("#795548"))

        # Format pour les largeurs (chiffres)
        self.fmt_largeur = QTextCharFormat()
        self.fmt_largeur.setForeground(QColor("#E91E63"))
        self.fmt_largeur.setFontWeight(QFont.Bold)

    def highlightBlock(self, text):
        # Detecter si c'est une ligne de largeurs (contient des chiffres et espaces uniquement)
        stripped = text.strip()
        is_width_line = bool(stripped) and all(c.isdigit() or c.isspace() for c in stripped)

        if is_width_line:
            for i, c in enumerate(text):
                if c.isdigit():
                    self.setFormat(i, 1, self.fmt_largeur)
        else:
            for i, c in enumerate(text):
                if c == "|":
                    self.setFormat(i, 1, self.fmt_encastree)
                elif c == "/":
                    self.setFormat(i, 1, self.fmt_applique)
                elif c == "*":
                    self.setFormat(i, 1, self.fmt_tasseau)
                elif c in ("-", "_"):
                    self.setFormat(i, 1, self.fmt_rayon)


class LineNumberArea(QWidget):
    """Zone de numeros de ligne pour l'editeur."""

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return self.editor._line_number_area_width()

    def paintEvent(self, event):
        self.editor._paint_line_numbers(event)


class SchemaEditor(QWidget):
    """Editeur de schema compact avec coloration syntaxique, numeros de ligne et aide contextuelle."""

    schema_modifie = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._aide_visible = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Barre du haut : titre + legende + bouton aide
        header = QHBoxLayout()

        label = QLabel("Schema compact")
        label.setStyleSheet("font-weight: bold; padding: 4px;")
        header.addWidget(label)

        legende = QLabel(
            '<span style="color:#2196F3">|</span> crem. encastree  '
            '<span style="color:#FF9800">/</span> crem. applique  '
            '<span style="color:#4CAF50">*</span> tasseau  '
            '<span style="color:#795548">-_</span> rayon  '
            '<span style="color:#E91E63">123</span> largeurs mm'
        )
        legende.setStyleSheet("padding: 2px 4px; font-size: 9pt;")
        header.addWidget(legende)

        header.addStretch()

        self._btn_aide = QPushButton("? Aide")
        self._btn_aide.setToolTip(
            "Afficher/masquer le panneau d'aide sur la syntaxe du schema")
        self._btn_aide.setCheckable(True)
        self._btn_aide.setMaximumWidth(80)
        self._btn_aide.clicked.connect(self._toggle_aide)
        header.addWidget(self._btn_aide)

        layout.addLayout(header)

        # Splitter : editeur (gauche) | aide (droite)
        self._splitter = QSplitter(Qt.Horizontal)

        # Editeur
        self.editor = _SchemaTextEdit()
        self.highlighter = SchemaHighlighter(self.editor.document())

        font = QFont("Courier New", 12)
        font.setStyleHint(QFont.Monospace)
        self.editor.setFont(font)
        self.editor.setTabStopDistance(40)
        self.editor.setLineWrapMode(QPlainTextEdit.NoWrap)

        self.editor.textChanged.connect(self._on_text_changed)
        self._splitter.addWidget(self.editor)

        # Panneau d'aide contextuelle
        self._aide_browser = QTextBrowser()
        self._aide_browser.setOpenExternalLinks(False)
        self._aide_browser.setStyleSheet(
            "QTextBrowser { background-color: #fafafa; border-left: 1px solid #ddd; "
            "font-size: 10pt; padding: 4px; }")
        self._aide_browser.setHtml(AIDE_PLACARD)
        self._aide_browser.setVisible(False)
        self._splitter.addWidget(self._aide_browser)

        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 2)

        layout.addWidget(self._splitter)

    def _on_text_changed(self):
        self.schema_modifie.emit(self.editor.toPlainText())

    def _toggle_aide(self, checked: bool):
        """Affiche ou masque le panneau d'aide contextuelle."""
        self._aide_visible = checked
        self._aide_browser.setVisible(checked)
        self._btn_aide.setText("? Aide" if not checked else "Fermer aide")

    def set_mode_aide(self, mode: str):
        """Met a jour le contenu de l'aide selon le mode (Placard ou Meuble).

        Args:
            mode: 'Placard' ou 'Meuble'.
        """
        if mode == "Meuble":
            self._aide_browser.setHtml(AIDE_MEUBLE)
        else:
            self._aide_browser.setHtml(AIDE_PLACARD)

    def get_schema(self) -> str:
        return self.editor.toPlainText()

    def set_schema(self, text: str):
        self.editor.blockSignals(True)
        self.editor.setPlainText(text)
        self.editor.blockSignals(False)


class _SchemaTextEdit(QPlainTextEdit):
    """QPlainTextEdit avec numeros de ligne."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_number_width)
        self.updateRequest.connect(self._update_line_number_area)
        self._update_line_number_width(0)

    def _line_number_area_width(self):
        digits = max(1, len(str(self.blockCount())))
        return 10 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_line_number_width(self, _):
        self.setViewportMargins(self._line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(),
                                         self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_number_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self._line_number_area_width(), cr.height())
        )

    def _paint_line_numbers(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#f0f0f0"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QColor("#999999"))
                painter.drawText(
                    0, top, self.line_number_area.width() - 4,
                    self.fontMetrics().height(),
                    Qt.AlignRight, str(block_number + 1)
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

        painter.end()
