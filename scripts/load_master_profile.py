"""Charge le profil maître de référence (tests/fixtures/profile_emmanuel.json) dans Supabase.

Usage : .venv/bin/python scripts/load_master_profile.py [--dry-run]
Incrémente la version du profil actif ou crée le premier profil.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.schemas.candidate import CandidateProfile  # noqa: E402
from app.services.storage import supabase_service  # noqa: E402

dry_run = "--dry-run" in sys.argv
profile = CandidateProfile.model_validate(json.loads((ROOT / "tests/fixtures/profile_emmanuel.json").read_text()))

current = supabase_service.get_active_candidate_profile() if supabase_service.client else None
record = {
    "name": profile.name,
    "profile": profile.model_dump(exclude={"preferences"}),
    "preferences": profile.preferences.model_dump(),
    "version": (current.get("version", 1) + 1) if current else 1,
    "is_active": True,
    "updated_at": datetime.now(timezone.utc).isoformat(),
}
print(f"Profil valide : {profile.name} - {len(profile.experiences)} expériences, {len(profile.projects)} projets "
      f"-> version {record['version']}")

if dry_run or not supabase_service.client:
    print("Dry-run ou Supabase non configuré : aucune écriture.")
    sys.exit(0)

table = supabase_service.client.table("candidate_profiles")
res = table.update(record).eq("id", current["id"]).execute() if current else table.insert(record).execute()
print("Enregistré :", res.data[0]["id"] if res.data else "(sans retour)")
