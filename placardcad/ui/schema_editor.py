"""
Editeur de schema compact avec coloration syntaxique.
"""

from PyQt5.QtWidgets import QPlainTextEdit, QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import pyqtSignal, Qt, QRect
from PyQt5.QtGui import (
    QSyntaxHighlighter, QTextCharFormat, QColor, QFont,
    QPainter, QTextFormat
)


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
    """Editeur de schema compact avec coloration syntaxique et numeros de ligne."""

    schema_modifie = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Titre
        label = QLabel("Schema compact")
        label.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(label)

        # Legende
        legende = QLabel(
            '<span style="color:#2196F3">|</span> crem. encastree  '
            '<span style="color:#FF9800">/</span> crem. applique  '
            '<span style="color:#4CAF50">*</span> tasseau  '
            '<span style="color:#795548">-_</span> rayon  '
            '<span style="color:#E91E63">123</span> largeurs mm'
        )
        legende.setStyleSheet("padding: 2px 4px; font-size: 9pt;")
        layout.addWidget(legende)

        # Editeur
        self.editor = _SchemaTextEdit()
        self.highlighter = SchemaHighlighter(self.editor.document())

        font = QFont("Courier New", 12)
        font.setStyleHint(QFont.Monospace)
        self.editor.setFont(font)
        self.editor.setTabStopDistance(40)
        self.editor.setLineWrapMode(QPlainTextEdit.NoWrap)

        self.editor.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.editor)

    def _on_text_changed(self):
        self.schema_modifie.emit(self.editor.toPlainText())

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
