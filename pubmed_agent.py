import os
import requests
import xml.etree.ElementTree as ET
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# 1. Määritetään rakenne Pydanticilla structured outputia varten
class ArticleSummary(BaseModel):
    title: str = Field(description="Tutkimuksen otsikko suomeksi käännettynä")
    original_title: str = Field(description="Tutkimuksen alkuperäinen englanninkielinen otsikko")
    pub_date: str = Field(description="Julkaisupäivämäärä")
    summary: str = Field(description="Ydinlöydökset tiiviisti suomeksi (2-3 virkettä)")
    relevance: str = Field(description="Miksi tämä on tärkeää kätilötyön/perinatologian kannalta")

class ResearchReport(BaseModel):
    weekly_summary: str = Field(description="Yleiskatsaus viikon tutkimustrendeistä")
    articles: list[ArticleSummary]

def fetch_pubmed_articles(query, days=7):
    """Hakee PubMedistä viimeisimmät artikkelit XML-muodossa."""
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    
    # 1. Haku (esearch)
    search_url = f"{base_url}esearch.fcgi?db=pubmed&term={query}&reldate={days}&datetype=edat&retmode=json&retmax=10"
    res = requests.get(search_url).json()
    id_list = res.get("esearchresult", {}).get("idlist", [])
    
    if not id_list:
        return []
    
    # 2. Tiedot (efetch)
    ids = ",".join(id_list)
    fetch_url = f"{base_url}efetch.fcgi?db=pubmed&id={ids}&retmode=xml"
    fetch_res = requests.get(fetch_url)
    
    # Parsitaan XML
    root = ET.fromstring(fetch_res.content)
    articles_data = []
    
    for article in root.findall(".//PubmedArticle"):
        title = article.findtext(".//ArticleTitle", default="Ei otsikkoa")
        abstract = "".join([elem.text for elem in article.findall(".//AbstractText") if elem.text])
        pub_date = article.findtext(".//Journal/JournalIssue/PubDate/Year", default="Tuntematon")
        
        articles_data.append({
            "title": title,
            "abstract": abstract if abstract else "Ei tiivistelmää saatavilla.",
            "pub_date": pub_date
        })
        
    return articles_data

def process_articles_with_gemini(articles):
    """Analysoi artikkelit Gemini API:lla ja palauttaa rakenteellisen JSON-raportin."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY puuttuu ympäristömuuttujista!")
        
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    Olet kätilötyön ja perinatologian erikoisalojen tekoälyagentti. 
    Tehtäväsi on analysoida seuraavat PubMed-tietokannasta haetut uusimmat tutkimusartikkelit.
    Käännä otsikot ja tiivistelmät selkeälle suomen kielelle ja tee jokaisesta ytimekäs synteesi.
    
    Lähdedata:
    {articles}
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ResearchReport,
        ),
    )
    
    return response.text

if __name__ == "__main__":
    # Hakusana: raskauteen, synnytykseen ja välilihaan liittyvät aiheet
    search_query = "(pregnancy OR childbirth OR perineal) AND (midwifery OR perinatology)"
    
    print("Haetaan artikkeleita PubMedistä...")
    raw_articles = fetch_pubmed_articles(search_query)
    
    if not raw_articles:
        print("Uusia artikkeleita ei löytynyt kuluneen viikon ajalta.")
    else:
        print(f"Löytyi {len(raw_articles)} artikkelia. Analysoidaan Geminillä...")
        report = process_articles_with_gemini(raw_articles)
        
        print("\n--- VIIKOITTAINEN TIEDERAPORTTI ---\n")
        print(report)
        
        # Tallennetaan raportti tiedostoon
        with open("latest_report.json", "w", encoding="utf-8") as f:
            f.write(report)
        print("\nRaportti tallennettu tiedostoon latest_report.json")
