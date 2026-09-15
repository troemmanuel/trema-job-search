"""Helpers partagés par les templates CV et lettre."""
import re
from typing import Optional, Tuple

_LOCATION_SPLIT = re.compile(r"\s+-\s+|\s*[—–]\s*")


def split_location(location: Optional[str]) -> Tuple[str, str]:
    """« Rennes - mobile sur la France » → ("Rennes", "mobile sur la France") ; « Rennes, France » → ("Rennes, France", "")."""
    if not location:
        return "", ""
    parts = _LOCATION_SPLIT.split(location.strip(), maxsplit=1)
    city = parts[0].strip()
    mobility = parts[1].strip() if len(parts) > 1 else ""
    return city, mobility


def location_line(location: Optional[str], mobility: Optional[str] = None) -> str:
    """Ligne de localisation affichée : ville du profil + mobilité adaptée à l'offre (ou celle du profil par défaut)."""
    city, default_mobility = split_location(location)
    mobility = (mobility or default_mobility).strip()
    if city and mobility:
        return f"{city} - {mobility}"
    return city or mobility


def sender_city(location: Optional[str]) -> str:
    """Ville seule pour la ligne de date : « Rennes, France » → « Rennes »."""
    city, _ = split_location(location)
    return re.split(r",|\(", city)[0].strip()
