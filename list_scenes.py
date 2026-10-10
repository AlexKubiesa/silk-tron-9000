import argparse
import os
import re
from pathlib import Path

from dotenv import load_dotenv

CATALOG_RELATIVE_PATH = Path("Hollow Knight Silksong_Data/StreamingAssets/aa/catalog.bin")


def list_scenes(catalog_path: Path) -> list[str]:
    data = catalog_path.read_bytes()
    names = {m.group(1).decode() for m in re.finditer(rb"([\x20-\x7e]{1,80})\.unity(?![\x20-\x7e])", data)}
    return sorted(names)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="List the scene names in Silksong's Addressables catalog, for use with the plugin's F6 jump."
    )
    parser.add_argument(
        "filter",
        nargs="?",
        default="",
        help="Only list scenes containing this text (case-insensitive)",
    )
    args = parser.parse_args()

    load_dotenv(Path(__file__).parent / ".env")
    silksong_path = os.getenv("SILKSONG_PATH")
    if not silksong_path:
        parser.error("SILKSONG_PATH is not set (see .env)")

    catalog_path = Path(silksong_path).parent / CATALOG_RELATIVE_PATH
    for scene in list_scenes(catalog_path):
        if args.filter.lower() in scene.lower():
            print(scene)
