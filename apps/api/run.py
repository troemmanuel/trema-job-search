"""Point d'entrée CLI de Trema Job Search (API FastAPI + tâches batch).

Usage :
    uv run python run.py serve [--port 8000] [--reload]     Démarre l'API (uvicorn)
    uv run python run.py collect [24h|3j|7j] [--query …] [--limit N] [--no-prepare]
    uv run python run.py urls <url> [<url> …] | --file urls.txt [--no-prepare] [--min-score 75]
    uv run python run.py sync-notion                         Réconciliation Notion ↔ Supabase
    uv run python run.py cron-job                            Passage quotidien non interactif (launchd / cron)

Les commandes batch appellent directement les services métier, sans serveur HTTP.
"""
import argparse
import json
import os
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(API_ROOT))


def _print_json(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("main:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    from app.services.ingestion.collector import job_collector_service

    summary = job_collector_service.run_collection(
        duration=args.duration,
        query=args.query,
        limit=max(1, min(args.limit, 20)),
        auto_prepare=not args.no_prepare,
    )
    _print_json(summary)
    return 0


def cmd_urls(args: argparse.Namespace) -> int:
    from app.services.ingestion.collector import job_collector_service

    urls = list(args.urls or [])
    if args.file:
        urls += [line.strip() for line in Path(args.file).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not urls:
        print("Aucune URL fournie (arguments ou --file).", file=sys.stderr)
        return 2

    if len(urls) == 1:
        result = job_collector_service.import_and_process_url(
            url=urls[0], auto_prepare=not args.no_prepare, min_match_score=args.min_score
        )
    else:
        result = job_collector_service.import_and_process_urls(
            urls=urls, auto_prepare=not args.no_prepare, min_match_score=args.min_score
        )
    _print_json(result)
    return 0 if result.get("success", False) else 1


def cmd_sync_notion(args: argparse.Namespace) -> int:
    from app.services.notion.sync import notion_sync_service

    report = notion_sync_service.reconcile()
    _print_json(report)
    return 0 if report.get("success", False) else 1


def cmd_cron_job(args: argparse.Namespace) -> int:
    """Passage quotidien : collecte 24h (limite 10, auto-préparation) puis réconciliation Notion."""
    from app.services.ingestion.collector import job_collector_service
    from app.services.notion.sync import notion_sync_service

    summary = job_collector_service.run_collection(duration="24h", limit=10, auto_prepare=True)
    _print_json(summary)
    try:
        _print_json(notion_sync_service.reconcile())
    except Exception as e:  # noqa: BLE001 - la collecte a réussi, la sync ne doit pas faire échouer le cron
        print(f"Réconciliation Notion échouée : {e}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Trema Job Search — agent IA de recherche d'emploi")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Démarre l'API FastAPI")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    serve.add_argument("--reload", action="store_true", help="Rechargement à chaud (développement)")
    serve.set_defaults(func=cmd_serve)

    collect = sub.add_parser("collect", help="Collecte automatique des offres récentes")
    collect.add_argument("duration", nargs="?", default="24h", help="24h, 3j ou 7j")
    collect.add_argument("--query", default=None, help="Mot-clé de recherche (défaut : intitulés du profil)")
    collect.add_argument("--limit", type=int, default=5, help="Offres maximum (1-20)")
    collect.add_argument("--no-prepare", action="store_true", help="Ne pas générer les dossiers ni synchroniser Notion")
    collect.set_defaults(func=cmd_collect)

    urls = sub.add_parser("urls", help="Importe et traite des offres par URL")
    urls.add_argument("urls", nargs="*", help="URLs d'offres (LinkedIn, WTTJ, …)")
    urls.add_argument("--file", default=None, help="Fichier avec une URL par ligne")
    urls.add_argument("--no-prepare", action="store_true")
    urls.add_argument("--min-score", type=int, default=75, help="Seuil de qualification automatique")
    urls.set_defaults(func=cmd_urls)

    sub.add_parser("sync-notion", help="Réconciliation bidirectionnelle Notion ↔ Supabase").set_defaults(func=cmd_sync_notion)
    sub.add_parser("cron-job", help="Passage quotidien non interactif").set_defaults(func=cmd_cron_job)
    return parser


def main(argv=None) -> int:
    # Les commandes batch ne doivent pas démarrer le planificateur en arrière-plan.
    args = build_parser().parse_args(argv)
    if args.command != "serve":
        os.environ.setdefault("ENABLE_SCHEDULER", "0")
    from app.logging_config import setup_logging

    setup_logging()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
