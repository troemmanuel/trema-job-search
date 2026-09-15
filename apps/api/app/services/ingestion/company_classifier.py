import re
import logging
from typing import Optional, Dict, Any, Tuple, List

logger = logging.getLogger(__name__)

# Référentiel des entreprises récurrentes aligné sur la base Notion
KNOWN_COMPANIES = {
    "infomil": (
        "Grand groupe / Filiale IT (E.Leclerc)",
        "Grande distribution & E-commerce / Logiciels"
    ),
    "euro protection surveillance": (
        "Grand groupe (Bancassurance / Sécurité)",
        "Télésurveillance & Sécurité des biens / Banque"
    ),
    "eps": (
        "Grand groupe (Bancassurance / Sécurité)",
        "Télésurveillance & Sécurité des biens / Banque"
    ),
    "groupe sii": (
        "Grand groupe — ESN / conseil en technologies",
        "Conseil en technologies / ESN"
    ),
    "sii": (
        "Grand groupe — ESN / conseil en technologies",
        "Conseil en technologies / ESN"
    ),
    "sqli": (
        "ESN / Digital Commerce & Technology",
        "Conseil en technologies & Transformation digitale"
    ),
    "capgemini": (
        "Grand groupe (ESN/Conseil)",
        "Conseil en systèmes et logiciels informatiques"
    ),
    "sopra steria": (
        "Grand groupe (ESN/Conseil)",
        "Conseil en technologies & Services numériques"
    ),
    "thales": (
        "Grand groupe — Défense & Aéronautique",
        "Défense — systèmes critiques et embarqués"
    ),
    "doctolib": (
        "Scale-up / MedTech",
        "Santé / MedTech & Plateforme de soins"
    ),
    "qonto": (
        "Scale-up / Fintech",
        "Fintech / Néobanque B2B"
    ),
    "payfit": (
        "Scale-up / HR-Tech",
        "HR-Tech / Paie et gestion RH en SaaS"
    ),
    "cyberwatch": (
        "Éditeur de logiciels (Cybersécurité)",
        "Cybersécurité / Gestion des vulnérabilités et conformité"
    ),
    "stormshield": (
        "ETI — éditeur logiciel de cybersécurité (groupe Airbus)",
        "Cybersécurité — chiffrement de données & firewall"
    ),
    "idakto": (
        "Scale-up / Éditeur de logiciels (Identité numérique & Cybersécurité)",
        "Identité numérique / Sécurité & Microservices"
    ),
    "mistral ai": (
        "Scaleup / IA",
        "Intelligence Artificielle / DeepTech"
    ),
    "scaleway": (
        "Scaleup / Cloud",
        "Cloud / Hébergement & Infrastructure"
    ),
    "leboncoin": (
        "Grand groupe / Marketplace",
        "Marketplace C2C / E-commerce"
    ),
    "neosoft": (
        "ESN / Conseil en ingénierie informatique",
        "Conseil en technologies & ESN"
    ),
    "néosoft": (
        "ESN / Conseil en ingénierie informatique",
        "Conseil en technologies & ESN"
    ),
    "scalian": (
        "Grand groupe de conseil / ingénierie",
        "Conseil en ingénierie et transformation digitale"
    ),
    "aubay": (
        "ESN",
        "Conseil / Services numériques"
    ),
    "sfeir": (
        "ESN / Communauté d'experts",
        "Conseil / Services numériques & Cloud"
    ),
    "inetum": (
        "Grand groupe",
        "ESN / Conseil IT & Transformation digitale"
    ),
    "berger-levrault": (
        "Éditeur de logiciels métiers (secteur public & santé)",
        "Éditeur de logiciels / Numérique public & santé"
    ),
    "accenture": (
        "Grand groupe (Conseil & ESN)",
        "Conseil en technologies & SI / Cloud & Data"
    ),
    "crédit agricole technologies et services": (
        "Grand groupe (DSI bancaire)",
        "Banque / IT bancaire & Monétique"
    ),
    "sanofi": (
        "Grand groupe",
        "Pharmaceutique / Santé"
    ),
    "siemens mobility": (
        "Grand groupe",
        "Ferroviaire / transport — logiciel embarqué"
    )
}

def classify_company(
    company: str,
    title: str = "",
    description: str = "",
    raw_data: Optional[Dict[str, Any]] = None
) -> Tuple[str, str]:
    """
    Détermine de façon fiable et contextuelle le Type et le Domaine d'activité de l'entreprise.
    Retourne (company_type, company_domain).
    """
    clean_company = (company or "").strip()
    company_lower = clean_company.lower()

    # 1. Vérification dans le référentiel des entreprises connues
    for known_name, (k_type, k_domain) in KNOWN_COMPANIES.items():
        if known_name == company_lower or (len(known_name) > 3 and known_name in company_lower):
            return k_type, k_domain

    # 2. Exploitation des métadonnées brutes de l'offre (notamment WTTJ)
    raw = raw_data or {}
    wttj_job = raw.get("wttj_job") or raw.get("job") or raw
    org = wttj_job.get("organization") if isinstance(wttj_job, dict) else {}
    if not isinstance(org, dict):
        org = {}

    wttj_industry = org.get("industry")
    wttj_sectors = org.get("sectors") or []
    nb_employees = org.get("nb_employees")
    org_description = org.get("description") or ""

    domain_candidates: List[str] = []
    if isinstance(wttj_sectors, list):
        for s in wttj_sectors:
            if isinstance(s, dict) and s.get("name"):
                domain_candidates.append(s["name"])

    # 3. Analyse sémantique de la description pour le domaine
    combined_text = f"{clean_company} {title} {description} {org_description}".lower()

    detected_domain = None
    if any(k in combined_text for k in ["cybersécurité", "cybersecurity", "chiffrement", "vulnérabilités", "iam", "soc", "edr", "siem"]):
        detected_domain = "Cybersécurité / Sécurité des SI & Identité"
    elif any(k in combined_text for k in ["fintech", "paiement", "banque", "bancaire", "assurance", "courtage", "trading", "core banking"]):
        detected_domain = "Fintech / Banque & Systèmes financiers"
    elif any(k in combined_text for k in ["santé", "médical", "pharma", "biotech", "e-santé", "medtech", "clinique"]):
        detected_domain = "Santé / MedTech & Dispositifs médicaux"
    elif any(k in combined_text for k in ["e-commerce", "marketplace", "retail", "grande distribution", "achats", "vente"]):
        detected_domain = "E-commerce & Grande distribution"
    elif any(k in combined_text for k in ["défense", "armement", "naval", "aéronautique", "spatial", "systèmes critiques", "radars"]):
        detected_domain = "Défense & Aéronautique / Systèmes critiques"
    elif any(k in combined_text for k in ["ferroviaire", "transport", "mobilité", "logistique", "supply chain"]):
        detected_domain = "Transport & Mobilité / Logistique"
    elif any(k in combined_text for k in ["télécom", "opérateur", "fibre", "5g", "réseaux"]):
        detected_domain = "Télécommunications & Infrastructures réseau"
    elif any(k in combined_text for k in ["énergie", "renouvelable", "électricité", "nucléaire", "eau", "environnement"]):
        detected_domain = "Énergie & Environnement"
    elif any(k in combined_text for k in ["esn", "conseil en technologies", "société de conseil", "prestation", "régie", "ssii"]):
        detected_domain = "Conseil en technologies & ESN"
    elif any(k in combined_text for k in ["éditeur de logiciels", "éditeur saas", "plateforme saas", "software vendor"]):
        detected_domain = "Éditeur de logiciels / SaaS"
    elif domain_candidates:
        detected_domain = " / ".join(domain_candidates[:2])
    elif wttj_industry and isinstance(wttj_industry, str) and wttj_industry.strip():
        detected_domain = wttj_industry.strip()
    else:
        detected_domain = "Conseil en technologies & SI"

    # 4. Analyse de la structure / Type d'entreprise
    detected_type = None
    if any(k in combined_text for k in ["esn", "société de conseil", "cabinet de conseil", "ssii", "prestation de services"]):
        detected_type = "ESN / Conseil en technologies"
    elif any(k in combined_text for k in ["éditeur de logiciels", "éditeur saas", "logiciel saas", "éditeur de logiciel"]):
        detected_type = "Éditeur de logiciels / SaaS"
    elif any(k in combined_text for k in ["scale-up", "scaleup"]):
        detected_type = "Scale-up / Éditeur SaaS"
    elif any(k in combined_text for k in ["startup", "start-up"]):
        detected_type = "Startup tech"
    elif nb_employees and isinstance(nb_employees, (int, float)):
        if nb_employees >= 5000:
            detected_type = "Grand groupe"
        elif nb_employees >= 250:
            detected_type = "ETI"
        elif nb_employees >= 50:
            detected_type = "PME / Scale-up"
        else:
            detected_type = "Startup / PME"
    elif any(k in combined_text for k in ["grand groupe", "multinationale", "groupe international"]):
        detected_type = "Grand groupe"
    else:
        detected_type = "PME / Entreprise tech"

    return detected_type, detected_domain
