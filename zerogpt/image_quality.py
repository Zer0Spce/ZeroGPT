from PySide6.QtWidgets import QComboBox, QLabel

from .config import DEFAULT_IMAGE_CFG, DEFAULT_IMAGE_STEPS


_PRESETS = {
    "Fast": {"steps": 8, "cfg": 2.0},
    "Balanced": {"steps": 22, "cfg": 5.5},
    "High Quality": {"steps": DEFAULT_IMAGE_STEPS, "cfg": DEFAULT_IMAGE_CFG},
}


def install_image_quality_presets(MainWindow):
    """Add simple quality presets to the Image Studio without duplicating the whole UI."""
    original_image_page = MainWindow._image_page

    def image_page(self):
        page = original_image_page(self)

        # Better defaults for SDXL Base.
        self.steps.setValue(DEFAULT_IMAGE_STEPS)
        self.cfg.setValue(DEFAULT_IMAGE_CFG)

        combo = QComboBox()
        combo.addItems(["Fast", "Balanced", "High Quality"])
        combo.setCurrentText("High Quality")
        combo.setToolTip("Fast = quick draft, Balanced = moderate quality, High Quality = best default output")
        self.quality_preset_box = combo

        def apply_preset(name: str):
            preset = _PRESETS.get(name, _PRESETS["High Quality"])
            self.steps.setValue(preset["steps"])
            self.cfg.setValue(preset["cfg"])

        combo.currentTextChanged.connect(apply_preset)

        try:
            panel = page.layout().itemAt(0).widget()
            layout = panel.layout()
            index = layout.indexOf(self.generate_btn)
            if index < 0:
                index = layout.count()
            layout.insertWidget(index, QLabel("Quality preset"))
            layout.insertWidget(index + 1, combo)
        except Exception:
            pass

        return page

    MainWindow._image_page = image_page
