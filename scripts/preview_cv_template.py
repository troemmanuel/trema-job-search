"""Rend le template CV sur le profil maître de référence, pour validation visuelle.

Usage : .venv/bin/python scripts/preview_cv_template.py [dossier_sortie]
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.documents.templates.cv_classic import render_cv  # noqa: E402

out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "instance" / "preview"
out_dir.mkdir(parents=True, exist_ok=True)

profile = json.loads((ROOT / "tests/fixtures/profile_emmanuel.json").read_text())
tailored = json.loads((ROOT / "tests/fixtures/tailored_cv_itrust.json").read_text())

pdf_path = out_dir / "cv_template_preview.pdf"
pdf_path.write_bytes(render_cv(profile, tailored))
print(f"PDF : {pdf_path}")

try:
    subprocess.run(["pdftoppm", "-png", "-r", "70", str(pdf_path), str(out_dir / "cv_template_preview")], check=True)
    print(f"PNG : {out_dir}/cv_template_preview-*.png")
except (FileNotFoundError, subprocess.CalledProcessError):
    pass
