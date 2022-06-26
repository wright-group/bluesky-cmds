__all__ = ["colors", "set_style"]

from qtpy import QtWidgets
from .._main_window import app
from .colors import colors

def set_style():

    # Style Sheet----------------------------------------------------------------

    StyleSheet = ""

    # main window
    StyleSheet += "QMainWindow{background:custom_color}".replace(
        "custom_color", colors["background"]
    )

    # push button
    # StyleSheet += 'QPushButton{background:custom_color; border-width:0px;  border-radius: 0px; font: bold 14px}'.replace('custom_color', colors['go'])

    # progress bar
    StyleSheet += "QProgressBar:horizontal{border: 0px solid gray; border-radius: 0px; background: custom_color; padding: 0px; height: 30px;}".replace(
        "custom_color", colors["background"]
    )
    StyleSheet += "QProgressBar:chunk{background:custom_color}".replace(
        "custom_color", colors["go"]
    )

    # tab widget
    StyleSheet += "QTabWidget::pane{border-top: 2px solid #C2C7CB;}"
    StyleSheet += "QTabWidget::tab-bar{left: 5px;}"
    StyleSheet += "QTabBar::tab{width: 100px; background: clr1; border: 0px; border-bottom-color: black; border-top-left-radius: 4px; border-top-right-radius: 4px; min-width: 8ex; padding: 2px; font: bold 14px; color: clr2}".replace(
        "clr1", colors["background"]
    ).replace(
        "clr2", colors["heading_0"]
    )
    StyleSheet += "QTabBar::tab:selected{border-color: black; border-bottom-color: black; color: clr1}".replace(
        "clr1", colors["heading_1"]
    )

    # scroll bar
    StyleSheet += "QScrollArea::QWidget::QWidget{backround: transparent;}"

    # group box
    StyleSheet += (
        "QGroupBox{border: 2px solid gray; font: bold 14px; margin-top: 0ex; border-radius: 0 px;}"
    )
    StyleSheet += "QGroupBox::title{subcontrol-origin: margin; padding: 0 0px}"

    app.setStyleSheet(StyleSheet)


def set_background_role(obj):
    palette = QtWidgets.QPalette(obj.palette())
    palette.setColor(obj.backgroundRole(), QtWidgets.QColor(colors["background"]))
    obj.setPalette(palette)
