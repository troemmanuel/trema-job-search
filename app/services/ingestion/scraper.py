import json
import re
import logging
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import httpx
from app.services.ai.gemini import gemini_service
from app.schemas.job import JobNormalizedData

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

CONTRACT_MAPPING = {
    "FULL_TIME": "CDI",
    "PERMANENT": "CDI",
    "TEMPORARY": "CDD",
    "APPRENTICESHIP": "Alternance",
    "INTERNSHIP": "Stage",
    "FREELANCE": "Freelance"
}

class JobScraper:
    """Scraper intelligent et léger pour extraire les offres d'emploi depuis leur URL."""

    @classmethod
    def fetch_html(cls, url: str) -> str:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        with httpx.Client(timeout=15.0, follow_redirects=True, headers=headers) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.text

    @classmethod
    def extract_from_next_data(cls, soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
        """Extraction chirurgicale pour Welcome to the Jungle et sites Next.js (SSR)."""
        next_tag = soup.find("script", id="__NEXT_DATA__")
        if not next_tag or not next_tag.string:
            return None

        try:
            data = json.loads(next_tag.string)
            page_props = data.get("props", {}).get("pageProps", {})
            # WTTJ stocke souvent l'offre sous pageProps.job ou pageProps.initialState.job
            job = page_props.get("job")
            if not job:
                # Chercher récursivement un dictionnaire contenant 'name' et 'organization'
                for val in page_props.values():
                    if isinstance(val, dict) and "name" in val and "organization" in val:
                        job = val
                        break

            if not job:
                return None

            title = job.get("name") or job.get("title")
            org = job.get("organization", {})
            company = org.get("name") if isinstance(org, dict) else str(org)
            
            # Localisation
            office = job.get("office") or {}
            location = office.get("city") or office.get("country") or "France"

            # Contrat & Salaire
            raw_contract = job.get("contract_type", "")
            contract_type = CONTRACT_MAPPING.get(raw_contract, raw_contract or "CDI")

            salary_min = job.get("salary_minimum")
            salary_max = job.get("salary_maximum")
            salary_curr = job.get("salary_currency") or "EUR"

            # Descriptions assemblées (présentation + missions + profil recherché)
            desc_parts = []
            if job.get("description"):
                desc_parts.append(BeautifulSoup(job["description"], "html.parser").get_text(separator="\n").strip())
            if job.get("profile"):
                desc_parts.append("\n--- Profil recherché ---\n" + BeautifulSoup(job["profile"], "html.parser").get_text(separator="\n").strip())

            full_desc = "\n\n".join(desc_parts)

            return {
                "source": "WTTJ",
                "source_job_id": str(job.get("id") or job.get("slug") or ""),
                "title": title,
                "company": company,
                "location": location,
                "contract_type": contract_type,
                "salary_min": salary_min,
                "salary_max": salary_max,
                "salary_currency": salary_curr,
                "url": url,
                "description": full_desc,
                "raw_data": {"next_data_job": job}
            }
        except Exception as e:
            logger.warning(f"Impossible de parser __NEXT_DATA__: {e}")
            return None

    @classmethod
    def extract_from_json_ld(cls, soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
        """Extraction via le standard SEO JobPosting (présent sur 90% des sites d'emploi)."""
        script_tags = soup.find_all("script", type="application/ld+json")
        for tag in script_tags:
            if not tag.string:
                continue
            try:
                data = json.loads(tag.string)
                # Gérer si c'est une liste ou un graphe
                items = data if isinstance(data, list) else data.get("@graph", [data])
                for item in items:
                    if isinstance(item, dict) and item.get("@type") == "JobPosting":
                        title = item.get("title")
                        org = item.get("hiringOrganization", {})
                        company = org.get("name") if isinstance(org, dict) else str(org)
                        
                        # Localisation
                        loc = item.get("jobLocation", {})
                        location = None
                        if isinstance(loc, dict):
                            addr = loc.get("address", {})
                            if isinstance(addr, dict):
                                location = addr.get("addressLocality") or addr.get("addressRegion")
                            elif isinstance(addr, str):
                                location = addr

                        # Contrat
                        emp_type = item.get("employmentType", "")
                        contract = CONTRACT_MAPPING.get(emp_type, emp_type or "CDI")

                        # Salaire
                        salary_info = item.get("baseSalary", {})
                        s_min = None
                        s_max = None
                        if isinstance(salary_info, dict):
                            val = salary_info.get("value", {})
                            if isinstance(val, dict):
                                s_min = val.get("minValue")
                                s_max = val.get("maxValue")

                        # Description (souvent du HTML)
                        raw_desc = item.get("description", "")
                        clean_desc = BeautifulSoup(raw_desc, "html.parser").get_text(separator="\n").strip()

                        # Source
                        netloc = urlparse(url).netloc.lower()
                        source = "WTTJ" if "welcometothejungle" in netloc else netloc.replace("www.", "").split(".")[0].upper()

                        return {
                            "source": source,
                            "source_job_id": str(item.get("identifier", {}).get("value") or ""),
                            "title": title,
                            "company": company,
                            "location": location or "Non précisé",
                            "contract_type": contract,
                            "salary_min": int(s_min) if s_min else None,
                            "salary_max": int(s_max) if s_max else None,
                            "salary_currency": "EUR",
                            "url": url,
                            "description": clean_desc,
                            "raw_data": {"json_ld": item}
                        }
            except Exception as e:
                logger.debug(f"Erreur tentative JSON-LD: {e}")
                continue
        return None

    @classmethod
    def extract_with_gemini_fallback(cls, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Fallback IA : extrait les champs essentiels à partir du texte nettoyé."""
        # Supprimer balises inutiles
        for s in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            s.decompose()

        text = soup.get_text(separator="\n")
        # Nettoyer les sauts de ligne multiples
        cleaned_text = re.sub(r'\n{3,}', '\n\n', text).strip()
        truncated_text = cleaned_text[:12000] # Limiter la taille pour l'API

        prompt = f"""
Voici le texte brut extrait d'une page Web d'offre d'emploi (URL: {url}) :

---
{truncated_text}
---

Extrais les informations de l'offre d'emploi sous forme strictement structurée.
"""
        extracted = gemini_service.generate_structured(
            prompt=prompt,
            response_schema=JobNormalizedData,
            system_instruction="Tu es un extracteur d'offres d'emploi précis. Extrais titre, entreprise, lieu, remote, contract_type, seniority, skills, requirements.",
            operation="SCRAPE_FALLBACK"
        )

        netloc = urlparse(url).netloc.lower()
        source = netloc.replace("www.", "").split(".")[0].upper()

        if extracted:
            return {
                "source": source,
                "source_job_id": None,
                "title": extracted.title,
                "company": extracted.company,
                "location": extracted.location,
                "contract_type": extracted.contract_type or "CDI",
                "salary_min": None,
                "salary_max": None,
                "salary_currency": "EUR",
                "url": url,
                "description": truncated_text[:3000],
                "normalized_data": extracted.model_dump()
            }
        else:
            return {
                "source": source,
                "source_job_id": None,
                "title": "Offre sans titre",
                "company": "Entreprise inconnue",
                "location": "France",
                "contract_type": "CDI",
                "url": url,
                "description": truncated_text[:2000]
            }

    @classmethod
    def scrape(cls, url: str) -> Dict[str, Any]:
        """Méthode principale : tente __NEXT_DATA__, puis JSON-LD, puis fallback Gemini."""
        html = cls.fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")

        # 1. Tentative Next.js (__NEXT_DATA__)
        data = cls.extract_from_next_data(soup, url)
        if data and data.get("title") and data.get("description"):
            logger.info(f"Offre extraite via __NEXT_DATA__ : {data['title']} ({data['company']})")
            return data

        # 2. Tentative JSON-LD (Standard SEO)
        data = cls.extract_from_json_ld(soup, url)
        if data and data.get("title"):
            logger.info(f"Offre extraite via JSON-LD : {data['title']} ({data['company']})")
            return data

        # 3. Fallback Gemini
        logger.info(f"Extraction via Fallback Gemini pour {url}")
        return cls.extract_with_gemini_fallback(soup, url)

job_scraper = JobScraper()
