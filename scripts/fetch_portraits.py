"""Development-only download of a pinned Riot Data Dragon portrait snapshot.

Never imported by the application. Run explicitly when refreshing bundled assets.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.request import urlopen

from PySide6.QtGui import QImage

from league_draft.domain.roster import normalize


ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "src" / "league_draft" / "resources"


def fetch(url: str) -> bytes:
    with urlopen(url, timeout=30) as response:
        payload = response.read(2_000_001)
    if len(payload) > 2_000_000:
        raise ValueError(f"Unexpected response size from {url}")
    return payload


def main() -> None:
    roster = json.loads((RESOURCES / "champions.json").read_text(encoding="utf-8"))
    version = roster["metadata"]["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Invalid snapshot version")
    base = f"https://ddragon.leagueoflegends.com/cdn/{version}"
    source = f"{base}/data/en_US/champion.json"
    champions = json.loads(fetch(source))
    if champions["version"] != version:
        raise ValueError("Unexpected roster snapshot")
    by_name = {champion["name"]: champion for champion in champions["data"].values()}
    if set(by_name) != set(roster["names"]):
        raise ValueError("Remote roster does not match the bundled canonical names")
    directory = RESOURCES / "icons"
    directory.mkdir(exist_ok=True)

    def download(name: str) -> tuple[str, dict]:
        filename = by_name[name]["image"]["full"]
        if not re.fullmatch(r"[A-Za-z0-9]+\.png", filename):
            raise ValueError(f"Unsafe portrait filename for {name}")
        url = f"{base}/img/champion/{filename}"
        payload = fetch(url)
        image = QImage.fromData(payload, "PNG")
        if not payload.startswith(b"\x89PNG\r\n\x1a\n") or image.isNull() or image.width() != image.height() or not 64 <= image.width() <= 512:
            raise ValueError(f"Invalid square PNG portrait for {name}")
        local_name = f"{normalize(name)}.png"
        destination = directory / local_name
        temporary = destination.with_suffix(".tmp")
        temporary.write_bytes(payload)
        temporary.replace(destination)
        return name, {"file": f"icons/{local_name}", "source": url,
                      "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload),
                      "width": image.width(), "height": image.height()}

    with ThreadPoolExecutor(max_workers=4) as executor:
        entries = dict(executor.map(download, roster["names"]))
    manifest = {
        "metadata": {
            "version": version,
            "roster_source": source,
            "retrieved_at": datetime.now(timezone.utc).date().isoformat(),
            "source_documentation": "https://developer.riotgames.com/docs/lol#data-dragon",
            "terms": "https://www.riotgames.com/en/legal",
            "copyright": "Champion portraits © Riot Games. Not relicensed by this project.",
            "scope": "Champion square portraits only; bundled for offline display.",
        },
        "portraits": entries,
    }
    (RESOURCES / "portraits.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Bundled {len(entries)} portraits for Data Dragon {version}; {sum(e['bytes'] for e in entries.values()):,} bytes.")


if __name__ == "__main__":
    main()
