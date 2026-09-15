"""
Restauration d'accents pour les textes français produits par un modèle qui les a supprimés (repli flash-lite).

Principe : ne s'active que si le texte est manifestement dépourvu d'accents ; ne réaccentue qu'un mot dont
la forme accentuée est UNIQUE dans le vocabulaire de référence (profil maître, offre, lexique CV). Les mots
courts (≤ 3 lettres : a/à, ou/où, des/dès) ne sont jamais touchés.
"""
import re
import unicodedata
from typing import Dict, Iterable, Optional, Set

_ACCENTED = re.compile(r"[àâäáãåçéèêëíìîïñóòôöõúùûüýÿÀÂÄÁÃÅÇÉÈÊËÍÌÎÏÑÓÒÔÖÕÚÙÛÜÝ]")
_WORD = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'-]*")

# Lexique de base des CV / lettres : formes accentuées fréquentes que le profil maître peut ne pas contenir
LEXICON = """
développé développée développer développement déployé déployée déploiement conçu conçue réalisé réalisée réalisation
réalisations expérience expériences expérimenté ingénieur ingénieure compétence compétences qualité données équipe
équipes requête requêtes opération opérations récurrent récurrente récurrentes sécurité réduit amélioré améliorée
amélioration résolu intégration intégrations intégré intégrée environnement environnements évolutif évolutive
évolutives spécialisé spécialisée diplômé diplômée université création créé créée géré gérée gérer gestion cumulée
orienté orientée architecturé conteneurisé conteneurisée conteneurisation supervisé supervisée éditeur édition
contravention contestation modèle modèles modélisation implémenté implémentée implémentation industrialisé
industrialisation exécuté exécution automatisé automatisée automatisation observabilité fiabilisé fiabilisation
traçabilité historisation échec réparé livré livrée livrés documenté documentée préparé préparée animé animée
métier métiers problématique problématiques intérêt réel réelle stratégie stratégique dédié dédiée mené menée
piloté pilotée coordonné coordonnée participé contribué assuré assurée analysé analysée optimisé optimisée
migré migrée sécurisé sécurisée testé testée validé validée défini définie mis mise élaboré élaborée rédigé rédigée
appliqué appliquée maîtrise maîtrisé maîtrisée solide dernière dernières première premières année années
précédent précédente présent présente référence références différent différente différents différentes
généré générée générique générale général régulier régulière régulièrement itératif itérative méthode méthodes
méthodologie méthodologies agilité prédictif prédictive systèmes système écosystème télétravail mobilité
Île-de-France éligible fédéral décisionnel pérenne pérennité efficacité productivité clé clés élément éléments
évènement événement événements dépôt dépôts déclaratif déclarative planifié planifiée programmé programmée
supérieur supérieure inférieur inférieure numérique numériques électronique électroniques téléphone
""".split()


def _strip(word: str) -> str:
    return unicodedata.normalize("NFKD", word).encode("ASCII", "ignore").decode()


def _has_accent(text: str) -> bool:
    return bool(_ACCENTED.search(text))


def build_vocabulary(*sources: Iterable[str]) -> Dict[str, Set[str]]:
    """{forme sans accent (minuscule) → {formes rencontrées (minuscule)}}.

    Un mot vu SANS accent dans les sources compte aussi comme une forme : « marche » et « marché » présents
    tous deux → deux formes → jamais réaccentué (ambigu).
    """
    vocab: Dict[str, Set[str]] = {}
    for source in sources:
        for text in source:
            for word in _WORD.findall(text or ""):
                if len(word) > 3:
                    vocab.setdefault(_strip(word).lower(), set()).add(word.lower())
    return {k: v for k, v in vocab.items() if any(_has_accent(f) for f in v)}


def _iter_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _iter_strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _iter_strings(v)


def vocabulary_from(*objects) -> Dict[str, Set[str]]:
    """Vocabulaire à partir de dicts / listes / chaînes (profil maître, offre) + lexique."""
    return build_vocabulary(LEXICON, *(list(_iter_strings(o)) for o in objects))


def looks_stripped(text: str) -> bool:
    """Vrai si un texte français d'une certaine longueur ne contient (presque) aucun accent."""
    letters = len(re.findall(r"[A-Za-zÀ-ÿ]", text or ""))
    if letters < 80:
        return False
    return len(_ACCENTED.findall(text)) / letters < 0.004  # le français courant est à ~2-3 %


def restore_accents(text: Optional[str], vocab: Dict[str, Set[str]], force: bool = False) -> Optional[str]:
    """Réaccentue les mots à forme accentuée unique ; conserve la capitale initiale. No-op si le texte est sain."""
    if not text or (not force and not looks_stripped(text)):
        return text

    def fix(m: re.Match) -> str:
        word = m.group(0)
        if len(word) <= 3 or _has_accent(word):
            return word
        forms = vocab.get(word.lower())
        if not forms or len(forms) != 1:
            return word
        fixed = next(iter(forms))
        if word.isupper():
            return fixed.upper()
        if word[0].isupper():
            return fixed[0].upper() + fixed[1:]
        return fixed

    return _WORD.sub(fix, text)
