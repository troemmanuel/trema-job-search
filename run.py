import os
import sys
import argparse
import json
from app import create_app
from app.config import Config

app = create_app()

def handle_cli():
    parser = argparse.ArgumentParser(description="Trema Job Search — Agent IA Personnel de Recherche d'Emploi")
    parser.add_argument(
        "--collect",
        nargs="?",
        const="24h",
        help="Lancer la collecte automatique des offres récentes (ex: 24h, 3j, 7j)"
    )
    parser.add_argument(
        "--cron-job",
        action="store_true",
        help="Exécution quotidienne non interactive pour cron/launchd (durée=24h, limite=10, auto-prep=True)"
    )
    parser.add_argument(
        "--url",
        "--urls",
        nargs="+",
        default=None,
        help="Importer et traiter directement une ou plusieurs offres externes par leurs URLs (LinkedIn, WTTJ, etc.)"
    )
    parser.add_argument(
        "--urls-file",
        type=str,
        default=None,
        help="Fichier contenant une liste d'URLs à importer (une par ligne)"
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Mot-clé de recherche pour la collecte (ex: 'Backend', 'DevOps')"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Nombre maximum d'offres à traiter (défaut: 5, max: 20)"
    )
    parser.add_argument(
        "--no-prepare",
        action="store_true",
        help="Désactiver la génération automatique de CV/Lettre et la sync Notion"
    )

    args = parser.parse_args()

    target_urls = []
    if args.urls_file:
        if os.path.exists(args.urls_file):
            with open(args.urls_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        target_urls.append(line)
        else:
            print(f"❌ Fichier introuvable : {args.urls_file}")
            sys.exit(1)

    if args.url:
        for u in args.url:
            for part in u.replace(",", "\n").splitlines():
                clean_p = part.strip()
                if clean_p and clean_p not in target_urls:
                    target_urls.append(clean_p)

    if target_urls:
        from app.services.ingestion.collector import job_collector_service
        auto_prepare = not args.no_prepare

        if len(target_urls) == 1:
            url = target_urls[0]
            print(f"\n🚀 [CLI] Importation et analyse de l'offre : {url}")
            print(f"📄 Auto-prep & Notion : {'Activé' if auto_prepare else 'Désactivé'}\n")

            with app.app_context():
                res = job_collector_service.import_and_process_url(
                    url=url,
                    auto_prepare=auto_prepare
                )

            if not res.get("success"):
                print(f"❌ Erreur : {res.get('error')}")
                sys.exit(1)

            job = res.get("job", {})
            score = res.get("score")
            print("=" * 60)
            print("📋 RÉSULTAT DU TRAITEMENT D'OFFRE EXTERNE")
            print("=" * 60)
            print(f"• Titre       : {job.get('title')}")
            print(f"• Entreprise  : {job.get('company')}")
            print(f"• Lieu        : {job.get('location')}")
            print(f"• Contrat     : {job.get('contract_type')}")
            print(f"• Score IA    : {score}/100 ({res.get('status')})")
            if res.get("prepared"):
                print(f"• CV PDF      : {res.get('cv_url')}")
                print(f"• Lettre PDF  : {res.get('letter_url')}")
                print(f"• Notion CRM  : {res.get('notion_url')}")
            print("=" * 60 + "\n")
            sys.exit(0)

        else:
            print(f"\n🚀 [CLI] Importation et analyse d'un lot de {len(target_urls)} offres...")
            print(f"📄 Auto-prep & Notion : {'Activé' if auto_prepare else 'Désactivé'}\n")

            with app.app_context():
                summary = job_collector_service.import_and_process_urls(
                    urls=target_urls,
                    auto_prepare=auto_prepare
                )

            print("=" * 65)
            print("📋 RÉCAPITULATIF DE L'IMPORTATION MULTI-URLS")
            print("=" * 65)
            print(f"• URLs demandées       : {summary.get('total_requested')}")
            print(f"• URLs uniques traitées: {summary.get('total_unique')}")
            print(f"• Offres qualifiées    : {summary.get('qualified_count')}")
            print(f"• Dossiers préparés    : {summary.get('prepared_count')}")
            print(f"• Fiches Notion créées : {summary.get('notion_synced_count')}")
            print(f"• Erreurs rencontrées  : {summary.get('error_count')}")
            print("=" * 65)

            for item in summary.get("results", []):
                j = item.get("job", {})
                title = j.get("title") or "Offre"
                company = j.get("company") or "Entreprise"
                score_txt = f"Score: {item['score']}/100" if item.get('score') is not None else "Erreur"
                notion_txt = f"-> Notion: {item['notion_url']}" if item.get('notion_url') else ""
                err_txt = f"({item['error']})" if item.get('error') else ""
                print(f"  [{item.get('status', 'OK')}] {title} chez {company} ({score_txt}) {notion_txt} {err_txt}")

            print("=" * 65 + "\n")
            sys.exit(0)

    if args.cron_job or args.collect:
        from app.services.ingestion.collector import job_collector_service
        from app.services.scheduler.daily_scheduler import daily_scheduler_service, compute_next_run
        from datetime import datetime

        is_cron = bool(args.cron_job)
        duration = "24h" if is_cron else (args.collect or "24h")
        limit = min(args.limit if not is_cron else (args.limit or 10), 20)
        auto_prepare = not args.no_prepare
        
        print(f"\n🚀 [CLI] Lancement de la collecte {'quotidienne (Cron)' if is_cron else 'automatique'} des offres...")
        print(f"⏱️  Période : {duration}")
        print(f"🔍 Mot-clé : {args.query or 'Profil cible (Maître)'}")
        print(f"📊 Limite  : {limit} offres max")
        print(f"📄 Auto-prep & Notion : {'Activé' if auto_prepare else 'Désactivé'}\n")

        with app.app_context():
            res = job_collector_service.run_collection(
                duration=duration,
                query=args.query,
                limit=limit,
                auto_prepare=auto_prepare
            )

            # Mise à jour du statut persistant du scheduler
            try:
                state = daily_scheduler_service.get_status()
                state["last_run"] = datetime.now().isoformat()
                state["last_result"] = {
                    "total_found": res.get("total_found", 0),
                    "processed_count": res.get("processed_count", 0),
                    "new_imported_count": res.get("new_imported_count", 0),
                    "qualified_count": res.get("qualified_count", 0),
                    "prepared_count": res.get("prepared_count", 0),
                    "notion_synced_count": res.get("notion_synced_count", 0)
                }
                state["next_run"] = compute_next_run(state.get("schedule_time", "08:00")).isoformat()
                daily_scheduler_service._save_state(state)
            except Exception as se:
                print(f"⚠️ Impossible de sauvegarder l'état scheduler: {se}")

        print("\n" + "=" * 60)
        print(f"📋 RÉCAPITULATIF DE LA COLLECTE {'QUOTIDIENNE' if is_cron else ''}")
        print("=" * 60)
        print(f"• Offres trouvées sur {res['duration']} : {res['total_found']}")
        print(f"• Offres analysées        : {res['processed_count']}")
        print(f"• Nouvelles offres en base: {res['new_imported_count']}")
        print(f"• Offres qualifiées (IA)  : {res['qualified_count']}")
        print(f"• Dossiers préparés (PDF) : {res['prepared_count']}")
        print(f"• Synchronisées Notion    : {res['notion_synced_count']}")
        print("=" * 60)

        for j in res.get("jobs", []):
            score_txt = f"Score: {j['match_score']}/100" if j.get('match_score') else "N/A"
            notion_txt = f"-> Notion: {j['notion_url']}" if j.get('notion_url') else ""
            print(f"  [{j.get('status', 'OK')}] {j.get('title')} chez {j.get('company')} ({score_txt}) {notion_txt}")
        
        sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) > 1 and ("--collect" in sys.argv or "--cron-job" in sys.argv or "--url" in sys.argv or "--urls" in sys.argv or "--urls-file" in sys.argv or "-h" in sys.argv or "--help" in sys.argv):
        handle_cli()
    else:
        port = Config.PORT
        debug = Config.DEBUG
        print(f"🚀 Serveur Flask démarré sur http://127.0.0.1:{port} (debug={debug})")
        app.run(host="0.0.0.0", port=port, debug=debug)
