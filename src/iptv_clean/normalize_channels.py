import re
import unicodedata


def clean_label(name):
    name = unicodedata.normalize("NFKC", name).upper().strip()
    name = re.sub(r"[\s_·－—-]", "", name)
    name = re.sub(r"(?:超高清|超清|高清|标清|HD|FHD|SD|1080P|720P|\(HD\))$", "", name)
    return name


class Channels:
    def __init__(self, rows):
        self.rows = {r["name"]: r for r in rows}
        self.aliases = {}
        for row in rows:
            for alias in [row["name"]] + row.get("aliases", []):
                self.aliases[clean_label(alias)] = row["name"]

    def normalize(self, *names):
        # Prefer the actual display label. Never reinterpret a conflicting ID.
        for name in names:
            key = clean_label(name)
            if key in self.aliases:
                return self.aliases[key]
        return None
