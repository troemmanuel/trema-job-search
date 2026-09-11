import json
import re
import logging
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import httpx
from app.services.ai.gemini import gemini_service
from app.services.ai.prompt_loader import prompt_loader
from app.schemas.job import JobNormalizedData

from urllib.parse import urlparse, parse_qs, urlunparse, urlencode

logger = logging.getLogger(__name__)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
}

CONTRACT_MAPPING = {
    "FULL_TIME": "CDI",
    "PERMANENT": "CDI",
    "TEMPORARY": "CDD",
    "APPRENTICESHIP": "Alternance",
    "INTERNSHIP": "Stage",
    "FREELANCE": "Freelance"
}

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "refId", "trackingId", "trk", "midToken", "trkInfo", "src", "fbclid", "gclid"
}


class JobScraper:
    """Scraper intelligent et léger pour extraire les offres d'emploi depuis leur URL."""

    @classmethod
    def extract_from_wttj_api(cls, url: str) -> Optional[Dict[str, Any]]:
        """Extraction via l'API publique Welcome to the Jungle (robuste, rapide et sans blocage Cloudflare/WAF)."""
        if "welcometothejungle.com" not in url:
            return None

        m = re.search(r'/(?:companies|entreprises)/([^/?#]+)/jobs/([^/?#]+)', url)
        if not m:
            return None

        org_slug, job_slug = m.group(1), m.group(2)
        api_url = f"https://api.welcometothejungle.com/api/v1/organizations/{org_slug}/jobs/{job_slug}"

        try:
            headers = {
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
                "Origin": "https://www.welcometothejungle.com",
                "Referer": "https://www.welcometothejungle.com/"
            }
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(api_url, headers=headers)
                if resp.status_code != 200:
                    logger.warning(f"WTTJ API a retourné le status {resp.status_code} pour {api_url}")
                    return None
                data = resp.json()
                job = data.get("job")
                if not job:
                    return None

                title = job.get("name") or job.get("title")
                org = job.get("organization", {})
                company = org.get("name") if isinstance(org, dict) else str(org)

                office = job.get("office") or {}
                location = office.get("city") or office.get("country") or "France"

                raw_contract = (job.get("contract_type") or "").upper()
                contract_type = CONTRACT_MAPPING.get(raw_contract, raw_contract or "CDI")

                salary_min = job.get("salary_minimum")
                salary_max = job.get("salary_maximum")
                salary_curr = job.get("salary_currency") or "EUR"

                desc_parts = []
                if job.get("description"):
                    desc_parts.append(BeautifulSoup(job["description"], "html.parser").get_text(separator="\n").strip())
                if job.get("profile"):
                    desc_parts.append("\n--- Profil recherché ---\n" + BeautifulSoup(job["profile"], "html.parser").get_text(separator="\n").strip())

                skills_list = []
                for s in job.get("skills", []):
                    name_dict = s.get("name", {})
                    skill_name = name_dict.get("fr") or name_dict.get("en") or (s.get("name") if isinstance(s.get("name"), str) else "")
                    if skill_name:
                        skills_list.append(skill_name)

                full_desc = "\n\n".join(desc_parts)

                return {
                    "source": "WTTJ",
                    "source_job_id": str(job.get("id") or job.get("reference") or job_slug),
                    "title": title,
                    "company": company,
                    "location": location,
                    "contract_type": contract_type,
                    "salary_min": salary_min,
                    "salary_max": salary_max,
                    "salary_currency": salary_curr,
                    "url": url,
                    "description": full_desc,
                    "raw_data": {
                        "wttj_job": job,
                        "remote": job.get("remote"),
                        "skills": skills_list
                    }
                }
        except Exception as e:
            logger.warning(f"Erreur extraction via WTTJ API: {e}")
            return None

    @classmethod
    def clean_url(cls, url: str) -> str:
        """Nettoie une URL en supprimant les paramètres de tracking et normalise les URLs spécifiques (LinkedIn, etc.)."""
        if not url:
            return ""
        url = url.strip()

        # Cas spécial LinkedIn: /jobs/view/1234567890/
        linkedin_m = re.search(r'linkedin\.com/jobs/view/([0-9]+)', url)
        if linkedin_m:
            job_id = linkedin_m.group(1)
            return f"https://www.linkedin.com/jobs/view/{job_id}/"

        # Nettoyage générique des paramètres tracking
        try:
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query, keep_blank_values=True)
            cleaned_params = {k: v for k, v in query_params.items() if k not in TRACKING_PARAMS and not k.startswith("utm_")}
            new_query = urlencode(cleaned_params, doseq=True)
            cleaned_url = urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                ""  # fragment supprimé
            ))
            return cleaned_url
        except Exception:
            return url

    @classmethod
    def fetch_html(cls, url: str) -> str:
        with httpx.Client(timeout=20.0, follow_redirects=True, headers=BROWSER_HEADERS) as client:
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
    def extract_from_meta_tags(cls, soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
        """Extraction basée sur OpenGraph et les balises meta standards."""
        og_title = soup.find("meta", property="og:title")
        og_desc = soup.find("meta", property="og:description")
        meta_desc = soup.find("meta", attrs={"name": "description"})

        title_content = og_title.get("content", "").strip() if og_title else ""
        if not title_content and soup.title:
            title_content = soup.title.get_text().strip()

        desc_content = ""
        if og_desc and og_desc.get("content"):
            desc_content = og_desc.get("content").strip()
        elif meta_desc and meta_desc.get("content"):
            desc_content = meta_desc.get("content").strip()

        if not title_content or len(desc_content) < 40:
            return None

        # Tenter d'isoler l'entreprise et le titre si format "Titre - Entreprise" ou "Titre chez Entreprise"
        company = "Entreprise"
        job_title = title_content
        for sep in [" chez ", " at ", " - ", " | "]:
            if sep in title_content:
                parts = title_content.split(sep)
                job_title = parts[0].strip()
                company = parts[-1].strip()
                break

        netloc = urlparse(url).netloc.lower()
        source = "LINKEDIN" if "linkedin" in netloc else (netloc.replace("www.", "").split(".")[0].upper())

        return {
            "source": source,
            "source_job_id": None,
            "title": job_title,
            "company": company,
            "location": "France",
            "contract_type": "CDI",
            "salary_min": None,
            "salary_max": None,
            "salary_currency": "EUR",
            "url": url,
            "description": desc_content,
            "raw_data": {"meta_tags": {"title": title_content, "description": desc_content}}
        }

    @classmethod
    def extract_with_gemini_fallback(cls, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Fallback IA : extrait les champs essentiels à partir du texte nettoyé."""
        # Supprimer balises inutiles
        for s in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            s.decompose()

        text = soup.get_text(separator="\n")
        # Nettoyer les sauts de ligne multiples
        cleaned_text = re.sub(r'\n{3,}', '\n\n', text).strip()
        truncated_text = cleaned_text[:12000]  # Limiter la taille pour l'API

        system_instruction, user_prompt = prompt_loader.load_and_render(
            "scrape_fallback",
            url=url,
            truncated_text=truncated_text
        )
        extracted = gemini_service.generate_structured(
            prompt=user_prompt,
            response_schema=JobNormalizedData,
            system_instruction=system_instruction,
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
        """Méthode principale : tente WTTJ API d'abord (si WTTJ), puis Next.js, JSON-LD, Meta tags, puis fallback Gemini."""
        url = cls.clean_url(url)

        # 1. Tentative API officielle WTTJ (immédiat, propre, sans blocage)
        if "welcometothejungle.com" in url:
            data = cls.extract_from_wttj_api(url)
            if data and data.get("title") and data.get("description"):
                logger.info(f"Offre extraite via WTTJ API : {data['title']} ({data['company']})")
                return data

        # 2. Fetch HTML pour les autres sources
        html = cls.fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")

        # 3. Tentative Next.js (__NEXT_DATA__)
        data = cls.extract_from_next_data(soup, url)
        if data and data.get("title") and data.get("description"):
            logger.info(f"Offre extraite via __NEXT_DATA__ : {data['title']} ({data['company']})")
            return data

        # 4. Tentative JSON-LD (Standard SEO Schema.org JobPosting) -> très efficace sur LinkedIn, Apec, etc.
        data = cls.extract_from_json_ld(soup, url)
        if data and data.get("title") and len(data.get("description", "")) > 100:
            logger.info(f"Offre extraite via JSON-LD : {data['title']} ({data['company']})")
            return data

        # 5. Tentative OpenGraph & Meta Tags
        data = cls.extract_from_meta_tags(soup, url)
        if data and data.get("title") and len(data.get("description", "")) >= 40:
            logger.info(f"Offre extraite via Meta/OpenGraph : {data['title']} ({data['company']})")
            return data

        # 6. Fallback Gemini Flash avec cascade anti-quota
        logger.info(f"Extraction via Fallback Gemini pour {url}")
        return cls.extract_with_gemini_fallback(soup, url)

job_scraper = JobScraper()
clean_url = JobScraper.clean_url
