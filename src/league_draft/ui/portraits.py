"""Cached, local-only champion portraits with an empty-icon fallback."""

from importlib.resources import files

from PySide6.QtGui import QIcon, QImage, QPixmap

from league_draft.domain.roster import normalize


class Portraits:
    def __init__(self):
        self._cache: dict[str, QIcon] = {}
        self._grayscale: dict[str, QIcon] = {}

    def icon(self, name: str | None, *, grayscale: bool = False) -> QIcon:
        if not name:
            return QIcon()
        if name not in self._cache:
            icon = QIcon()
            resource = files("league_draft").joinpath("resources", "icons", f"{normalize(name)}.png")
            try:
                payload = resource.read_bytes()
            except OSError:
                payload = b""
            pixmap = QPixmap()
            if payload and pixmap.loadFromData(payload, "PNG"):
                icon = QIcon(pixmap)
            self._cache[name] = icon
        if grayscale:
            if name not in self._grayscale:
                image = self._cache[name].pixmap(128, 128).toImage()
                if image.isNull():
                    self._grayscale[name] = QIcon()
                else:
                    image = image.convertToFormat(QImage.Format.Format_Grayscale8)
                    self._grayscale[name] = QIcon(QPixmap.fromImage(image))
            return self._grayscale[name]
        return self._cache[name]
