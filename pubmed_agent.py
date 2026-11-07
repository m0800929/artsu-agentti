import datetime
import os
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
import requests
from google import genai
from google.genai import types
from pydantic import BaseModel

# 1. API-AVAIMEN TARKISTUS
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY-ympäristömuuttuja puuttuu!")

client = genai.Client(api_key=GEMINI_API_KEY)

# 2. HAKULOGIIKKA PUBMEDISSA
SEARCH_QUERY = (
    "(Midwif*[Title/Abstract] OR birth[Title/Abstract] OR childbirth[Title/Abstract] "
    "OR labour[Title/Abstract] OR childbearing[Title/Abstract] OR pregnan*[Title/Abstract] "
    "OR oetus[Title/Abstract] OR fetus[Title/Abstract] OR perineal tear*[Title/Abstract] "
    "OR OASIS[Title/Abstract] OR perineal[Title/Abstract])"
)

# 3. TYYPPIMÄÄRITTELYT TEKOÄLYN STRUKTUROIDULLE REPOORTILLE
class ArticleSummary(BaseModel):
    title_fi: str
    original_title: str
    pmid: str
    relevance_score: int
    is_relevant: bool
    summary: str
    key_takeaways: List[str]

class WeeklyDigest(BaseModel):
    selected_articles: List[ArticleSummary]


# 4. PUBMED-FUNKTIOT
def fetch_pubmed_ids(days: int = 7, max_results: int = 40) -> List[str]:
    """Hakee PubMedistä viimeisen N päivän julkaisujen ID:t."""
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": SEARCH_QUERY,
        "reldate": days,
        "datetype": "pdat",
        "retmode": "json",
        "retmax": max_results,
    }
    response = requests.get(base_url, params=params)
    response.raise_for_status()
    data = response.json()
    return data.get("esearchresult", {}).get("idlist", [])


def fetch_article_details(pmids: List[str]) -> List[Dict[str, str]]:
    """Lataa julkaisujen otsikot ja abstraktit XML-muodossa."""
    if not pmids:
        return []

    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
    }
    response = requests.get(base_url, params=params)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    articles = []

    for article_node in root.findall(".//PubmedArticle"):
        pmid = article_node.findtext(".//PMID")
        title = article_node.findtext(".//ArticleTitle")

        abstract_parts = []
        for elem in article_node.findall(".//AbstractText"):
            if elem.text:
                label = elem.attrib.get("Label", "")
                prefix = f"{label}: " if label else ""
                abstract_parts.append(f"{prefix}{elem.text}")
        
        abstract = "\n".join(abstract_parts) if abstract_parts else "Ei abstraktia saatavilla."

        articles.append({
            "pmid": pmid,
            "title": title or "Ei otsikkoa",
            "abstract": abstract,
            "link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        })

    return articles


# 5. TIIVISTÄMINEN GEMINI API:LLA
def process_articles_with_gem
