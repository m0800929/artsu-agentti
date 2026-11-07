import os
import requests
import xml.etree.ElementTree as ET
import json
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# 1. Määritetään rakenne Pydanticilla
class ArticleSummary(BaseModel):
    title: str = Field(description="Tutkimuksen otsikko suomeksi käännettynä")
    original_title: str = Field(description="Tutkimuksen alkuperäinen englanninkielinen otsikko")
    pub_date: str = Field(description="Julkaisupäivämäärä")
    summary: str = Field(description="Ydinlöydökset tiiviisti suomeksi (2-3 virkettä)")
    relevance: str = Field(description="Miksi tämä on tärkeää kätilötyön/perinatologian kannalta")
    url: str = Field(description="Linkki tutkimukseen (PubMed URL)")

class ResearchReport(BaseModel):
    weekly_summary: str = Field(description="Yleiskatsaus viikon tutkimustrendeistä suomeksi")
    articles: list[ArticleSummary]

# 2. Haku PubMedistä ja linkkien muodostaminen
def fetch_pubmed_articles(query, days=7):
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    
    search_url = f"{base_url}esearch.fcgi?db=pubmed&term={query}&reldate={days}&datetype=edat&retmode=json&retmax=10"
    res = requests.get(search_url).json()
    id_list = res.get("esearchresult", {}).get("idlist", [])
    
    if not id_list:
        return []
    
    ids = ",".join(id_list)
    fetch_url = f"{base_url}efetch.fcgi?db=pubmed&id={ids}&retmode=xml"
    fetch_res = requests.get(fetch_url)
    
    root = ET.fromstring(fetch_res.content)
    articles_data = []
    
    for article in root.findall(".//PubmedArticle"):
        pmid = article.findtext(".//PMID", default="")
        title = article.findtext(".//ArticleTitle", default="Ei otsikkoa")
        abstract_elements = article.findall(".//AbstractText")
        abstract = " ".join([elem.text for elem in abstract_elements if elem.text])
        pub_date = article.findtext(".//Journal/JournalIssue/PubDate/Year", default="Tuntematon")
        
        pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "#"
        
        articles_data.append({
            "pmid": pmid,
            "title": title,
            "abstract": abstract if abstract else "Ei tiivistelmää saatavilla.",
            "pub_date": pub_date,
            "url": pubmed_url
        })
        
    return articles_data

# 3. Analyysi Geminillä
def process_articles_with_gemini(articles):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY puuttuu ympäristömuuttujista!")
        
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    Olet kätilötyön ja perinatologian erikoisalojen tekoälyagentti. 
    Tehtäväsi on analysoida seuraavat PubMed-tietokannasta haetut uusimmat tutkimusartikkelit.
    Käännä otsikot ja tiivistelmät selkeälle suomen kielelle ja tee jokaisesta ytimekäs synteesi.
    Säilytä jokaisen artikkelin URL-osoite sellaisenaan 'url'-kentässä.
    
    Lähdedata:
    {articles}
    """
    
    response = client.models.generate_content(
        model='gemini-3.8-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ResearchReport,
        ),
    )
    
    return response.text

# 4. Verkkosivun (HTML) generointi
def generate_html_page(json_data_str):
    data = json.loads(json_data_str)
    weekly_summary = data.get("weekly_summary", "")
    articles = data.get("articles", [])
    
    articles_html = ""
    for art in articles:
        articles_html += f"""
        <div class="card">
            <h2>{art.get('title', '')}</h2>
            <p class="original-title"><em>{art.get('original_title', '')}</em> ({art.get('pub_date', '')})</p>
            <div class="section">
                <strong>💡 Ydinlöydökset:</strong>
                <p>{art.get('summary', '')}</p>
            </div>
            <div class="section relevance">
                <strong>🩺 Merkitsevyys kätilötyölle & perinatologialle:</strong>
                <p>{art.get('relevance', '')}</p>
            </div>
            <a href="{art.get('url', '#')}" target="_blank" class="btn">Avaa alkuperäinen tutkimus (PubMed) ↗</a>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="fi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kätilötyön ja Perinatologian Tutkimuskatsaus</title>
    <style>
        :root {{
            --primary: #2c7a7b;
            --bg: #f7fafc;
            --card-bg: #ffffff;
            --text: #2d3748;
            --accent: #e6fffa;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            line-height: 1.6;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
        }}
        header {{
            background: var(--primary);
            color: white;
            padding: 30px 20px;
            border-radius: 12px;
            margin-bottom: 30px;
            text-align: center;
        }}
        header h1 {{ margin: 0; font-size: 1.8rem; }}
        header p {{ margin: 10px 0 0 0; opacity: 0.9; }}
        .weekly-summary {{
            background: #ebf8ff;
            border-left: 5px solid #3182ce;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
        }}
        .card {{
            background: var(--card-bg);
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 25px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            border: 1px solid #e2e8f0;
        }}
        .card h2 {{ color: var(--primary); margin-top: 0; font-size: 1.3rem; }}
        .original-title {{ color: #718096; font-size: 0.9rem; margin-bottom: 15px; }}
        .section {{ margin-bottom: 15px; }}
        .relevance {{ background: var(--accent); padding: 12px; border-radius: 6px; }}
        .btn {{
            display: inline-block;
            background: var(--primary);
            color: white;
            text-decoration: none;
            padding: 10px 18px;
            border-radius: 6px;
            font-weight: bold;
            font-size: 0.9rem;
            margin-top: 10px;
        }}
        .btn:hover {{ background: #234e52; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Kätilötyön & Perinatologian Tutkimuskatsaus</h1>
            <p>Automaattinen viikkokatsaus PubMed-tietokannasta</p>
        </header>
        
        <div class="weekly-summary">
            <h3>📌 Viikon yleiskatsaus</h3>
            <p>{weekly_summary}</p>
        </div>

        {articles_html}
    </div>
</body>
</html>
"""
    return html_content

if __name__ == "__main__":
    search_query = "(pregnancy OR childbirth OR perineal) AND (midwifery OR perinatology)"
    
    print("Haetaan artikkeleita PubMedistä...")
    raw_articles = fetch_pubmed_articles(search_query)
    
    if not raw_articles:
        print("Uusia artikkeleita ei löytynyt kuluneen viikon ajalta.")
    else:
        print(f"Löytyi {len(raw_articles)} artikkelia. Analysoidaan Geminillä...")
        report_json = process_articles_with_gemini(raw_articles)
        
        html_page = generate_html_page(report_json)
        
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html_page)
        print("Verkkosivu luotu tiedostoon index.html")
