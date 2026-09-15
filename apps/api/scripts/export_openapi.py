"""Exporte le schéma OpenAPI de l'API FastAPI sans démarrer de serveur.

Usage :
    uv run python scripts/export_openapi.py [chemin/de/sortie.json]

Par défaut, écrit dans `packages/api-client/openapi.json` (source de vérité du SDK TypeScript).
Le fichier n'est réécrit que s'il a changé, pour ne pas invalider inutilement les caches Turborepo.
"""
import json
import os
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
MONOREPO_ROOT = API_ROOT.parents[1]
DEFAULT_OUTPUT = MONOREPO_ROOT / "packages" / "api-client" / "openapi.json"

# Le planificateur ne doit pas démarrer pendant un simple export de schéma.
os.environ.setdefault("ENABLE_SCHEDULER", "0")
sys.path.insert(0, str(API_ROOT))


def main() -> int:
    from main import app  # import tardif : après configuration de l'environnement

    output = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)

    content = json.dumps(app.openapi(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if output.exists() and output.read_text(encoding="utf-8") == content:
        print(f"OpenAPI inchangé : {output}")
        return 0

    output.write_text(content, encoding="utf-8")
    schema_count = len(app.openapi().get("components", {}).get("schemas", {}))
    path_count = len(app.openapi().get("paths", {}))
    print(f"OpenAPI exporté : {output} ({path_count} routes, {schema_count} schémas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
