"""
Garde-fous déterministes appliqués au CV ciblé produit par l'IA.

Tout ce qui est ajouté ici provient du profil maître : aucune invention possible. Ces règles compensent
les modèles faibles (repli sur flash-lite) qui minimisent le nombre de réalisations, suppriment des
expériences au mépris de la durée annoncée, ou altèrent les libellés de stack.
"""
import logging
import re
from datetime import date
from typing import Dict, List, Optional, Set, Tuple

from app.schemas.application import ExperienceHighlight, TailoredCV
from app.schemas.candidate import CandidateProfile, Experience
from app.services.ai.accents import looks_stripped, restore_accents, vocabulary_from

logger = logging.getLogger(__name__)

MIN_TOTAL_BULLETS = 10
MAX_TOTAL_BULLETS = 14
MAX_BULLETS_PER_EXPERIENCE = 4

# Runtime / langage sous-jacent qu'un framework du profil maître autorise à afficher dans la stack
DERIVED_SKILLS: Dict[str, List[str]] = {
    "nestjs": ["Node.js", "TypeScript"],
    "nuxt.js (vue.js)": ["Vue.js"],
    "nuxt.js": ["Vue.js"],
    "spring boot": ["Java"],
    "spring": ["Java"],
    "fastapi": ["Python"],
    "laravel": ["PHP"],
    "angular": ["TypeScript"],
}


def _months(exp: Experience, today: Optional[date] = None) -> int:
    """Durée en mois à partir de 'AAAA-MM' ou 'AAAA' ; fin absente = aujourd'hui."""
    today = today or date.today()

    def parse(raw: Optional[str], default: Tuple[int, int]) -> Tuple[int, int]:
        m = re.match(r"(\d{4})(?:-(\d{1,2}))?", raw or "")
        if not m:
            return default
        return int(m.group(1)), int(m.group(2) or 1)

    sy, sm = parse(exp.start_date, (today.year, today.month))
    ey, em = parse(exp.end_date, (today.year, today.month)) if exp.end_date else (today.year, today.month)
    return max(0, (ey - sy) * 12 + (em - sm))


def _claimed_years(summary: str) -> Optional[int]:
    """« plus de 4 ans d'expérience » / « over 4 years of experience » → 4."""
    m = re.search(r"(\d+)\s*(?:\+)?\s*(?:ans|années|years?)\b", summary or "", flags=re.IGNORECASE)
    return int(m.group(1)) if m else None


def _words(text: str) -> Set[str]:
    return {w for w in re.findall(r"[a-zà-ÿ0-9]{3,}", (text or "").lower())}


def _covered(candidate: str, existing: List[str]) -> bool:
    """Une réalisation du profil maître est déjà représentée si une réalisation retenue la reprend.

    Mesure de recouvrement (part du plus court vocabulaire partagée) : une reformulation raccourcie par l'IA
    conserve les noms clés de la source, contrairement à une réalisation distincte.
    """
    cw = _words(candidate)
    if not cw:
        return True
    for e in existing:
        ew = _words(e)
        if ew and len(cw & ew) / min(len(cw), len(ew)) >= 0.6:
            return True
    return False


def _strip_parenthetical(item: str) -> str:
    return re.sub(r"\s*\(.*?\)", "", item).strip()


class TailoredCVPostProcessor:

    def __init__(self, profile: CandidateProfile):
        self.profile = profile
        self.by_id: Dict[str, Experience] = {e.id: e for e in profile.experiences}

    # -- 1. Cohérence durée annoncée / expériences visibles ----------------
    def ensure_duration_coherence(self, cv: TailoredCV) -> None:
        claimed = _claimed_years(cv.summary)
        if not claimed:
            return
        selected = [self.by_id[i] for i in cv.selected_experiences if i in self.by_id]
        total = sum(_months(e) for e in selected)
        if total >= claimed * 12:
            return
        missing = sorted((e for e in self.profile.experiences if e.id not in cv.selected_experiences),
                         key=_months, reverse=True)
        for exp in missing:
            cv.selected_experiences.append(exp.id)
            if not any(h.id == exp.id for h in cv.experience_highlights) and exp.achievements:
                cv.experience_highlights.append(ExperienceHighlight(id=exp.id, achievements=exp.achievements[:1]))
            total += _months(exp)
            cv.changes.append(f"Expérience {exp.id} ({exp.company}) réintégrée pour la cohérence des "
                              f"{claimed} ans annoncés dans le résumé.")
            if total >= claimed * 12:
                break

    # -- 2. Volume minimal de réalisations, complété depuis le profil maître
    def ensure_minimum_bullets(self, cv: TailoredCV) -> None:
        highlights = {h.id: h for h in cv.experience_highlights}
        # Une expérience retenue sans consigne IA affiche ses réalisations maîtres : on la matérialise pour compter
        for exp_id in cv.selected_experiences:
            exp = self.by_id.get(exp_id)
            if exp and exp_id not in highlights:
                highlights[exp_id] = ExperienceHighlight(id=exp_id, achievements=list(exp.achievements))
                cv.experience_highlights.append(highlights[exp_id])

        total = sum(len(h.achievements) for h in cv.experience_highlights)
        if total >= MIN_TOTAL_BULLETS:
            return
        # Ordre de complément : celui des highlights (l'IA place les expériences pertinentes en premier)
        for h in cv.experience_highlights:
            exp = self.by_id.get(h.id)
            if not exp:
                continue
            for ach in exp.achievements:
                if total >= MIN_TOTAL_BULLETS or len(h.achievements) >= MAX_BULLETS_PER_EXPERIENCE:
                    break
                if not _covered(ach, h.achievements):
                    h.achievements.append(ach)
                    total += 1
                    cv.changes.append(f"Réalisation du profil maître ajoutée sur {h.id} pour atteindre le volume minimal.")
            if total >= MIN_TOTAL_BULLETS:
                break

    # -- 3. Stack : réordonnée par l'IA, mais libellés et contenu du profil maître
    def sanitize_stacks(self, cv: TailoredCV) -> None:
        for h in cv.experience_highlights:
            exp = self.by_id.get(h.id)
            if not exp or not h.skills:
                continue
            master = {s.lower(): s for s in exp.skills}
            allowed = dict(master)
            for key, derived in DERIVED_SKILLS.items():
                if key in master:
                    allowed.update({d.lower(): d for d in derived})
            cleaned: List[str] = []
            for item in h.skills:
                label = allowed.get(_strip_parenthetical(item).lower())
                if label and label not in cleaned:
                    cleaned.append(label)
            for s in exp.skills:  # rien du profil maître ne disparaît
                if s not in cleaned:
                    cleaned.append(s)
            h.skills = cleaned

    # -- 0. Accents supprimés par un modèle faible (texte français uniquement)
    def restore_accents(self, cv: TailoredCV, job_context: Optional[dict] = None) -> None:
        if (cv.language or "fr").lower()[:2] != "fr":
            return
        sample = " ".join([cv.summary or "", cv.title or ""] + [a for h in cv.experience_highlights for a in h.achievements])
        if not looks_stripped(sample):
            return
        vocab = vocabulary_from(self.profile.model_dump(), job_context or {})
        cv.title = restore_accents(cv.title, vocab, force=True)
        cv.summary = restore_accents(cv.summary, vocab, force=True)
        cv.mobility = restore_accents(cv.mobility, vocab, force=True)
        for h in cv.experience_highlights:
            h.achievements = [restore_accents(a, vocab, force=True) for a in h.achievements]
        for g in cv.skill_groups:
            g.label = restore_accents(g.label, vocab, force=True)
        cv.changes = [restore_accents(c, vocab, force=True) for c in cv.changes]
        cv.changes.append("Accents restaurés automatiquement (le modèle les avait supprimés).")
        logger.warning("CV ciblé sans accents (modèle de repli) : restauration automatique appliquée")

    def run(self, cv: TailoredCV, job_context: Optional[dict] = None) -> TailoredCV:
        self.restore_accents(cv, job_context)
        self.ensure_duration_coherence(cv)
        self.ensure_minimum_bullets(cv)
        self.sanitize_stacks(cv)
        return cv


def finalize_tailored_cv(cv: TailoredCV, profile: CandidateProfile, job_context: Optional[dict] = None) -> TailoredCV:
    return TailoredCVPostProcessor(profile).run(cv, job_context)
