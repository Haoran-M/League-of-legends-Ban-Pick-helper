"""Canonical names and punctuation-insensitive search, with no numeric IDs."""

import json
import unicodedata
from importlib.resources import files


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).casefold()
    return "".join(c for c in value if c.isalnum())


class Roster:
    def __init__(self, names: list[str], aliases: dict[str, str] | None = None):
        if not names or len(set(names)) != len(names):
            raise ValueError("Roster must contain unique names.")
        self.names = tuple(sorted(names, key=str.casefold))
        self._lookup = {normalize(name): name for name in names}
        if len(self._lookup) != len(names):
            raise ValueError("Ambiguous normalized champion names.")
        for alias, name in (aliases or {}).items():
            if name not in names or not normalize(alias):
                raise ValueError("Invalid roster alias.")
            key = normalize(alias)
            if key in self._lookup and self._lookup[key] != name:
                raise ValueError("Ambiguous roster alias.")
            self._lookup[key] = name

    def resolve(self, name: str) -> str:
        try:
            return self._lookup[normalize(name)]
        except KeyError:
            raise ValueError(f"Unknown champion: {name!r}.") from None

    def search(self, query: str) -> tuple[str, ...]:
        key = normalize(query)
        matches = {name for alias, name in self._lookup.items() if key in alias}
        return tuple(name for name in self.names if name in matches)


def load_roster() -> tuple[Roster, dict]:
    resource = files("league_draft").joinpath("resources/champions.json")
    document = json.loads(resource.read_text(encoding="utf-8"))
    return Roster(document["names"], document["aliases"]), document["metadata"]
