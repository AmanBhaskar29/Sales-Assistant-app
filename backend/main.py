from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HEADERS = {"User-Agent": "Mozilla/5.0"}

# -------------------- SEARCH UTILS --------------------
def duckduckgo_search(query, max_results=5):
    url = f"https://duckduckgo.com/html/?q={query}"
    res = requests.get(url, headers=HEADERS, timeout=10)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    results = []
    anchors = soup.select("a.result__a")
    snippets = soup.select(".result__snippet")
    for i, a in enumerate(anchors[:max_results]):
        href = a.get("href")
        title = a.get_text(strip=True)
        snippet = snippets[i].get_text(strip=True) if i < len(snippets) else ""
        results.append({"title": title, "url": href, "snippet": snippet})
    return results


def get_official_website(company_name):
    results = duckduckgo_search(f"{company_name} official site")
    for r in results:
        if "linkedin.com" not in r["url"]:
            return r["url"]
    return None


# -------------------- NEWS FETCHING --------------------
def fetch_company_news(company_name):
    """
    Fetch top 4 news results.
    Priority: GNews API -> fallback to DuckDuckGo
    """
    articles = []

    # 1️⃣ Try GNews first
    if GNEWS_API_KEY:
        try:
            gnews_url = (
                f"https://gnews.io/api/v4/search?q={company_name}"
                f"&lang=en&max=4&token={GNEWS_API_KEY}"
            )
            resp = requests.get(gnews_url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for a in data.get("articles", [])[:4]:
                    articles.append({
                        "title": a.get("title"),
                        "description": a.get("description"),
                        "url": a.get("url"),
                        "publishedAt": a.get("publishedAt"),
                        "source": (a.get("source") or {}).get("name")
                    })
        except Exception as e:
            print(f"GNews API error: {e}")

    # 2️⃣ Fallback to DuckDuckGo
    if not articles:
        try:
            ddg = duckduckgo_search(f"{company_name} news", max_results=4)
            for r in ddg:
                articles.append({
                    "title": r["title"],
                    "description": r["snippet"],
                    "url": r["url"],
                    "publishedAt": None,
                    "source": "DuckDuckGo"
                })
        except Exception as e:
            print(f"DuckDuckGo news fallback error: {e}")

    return articles


# -------------------- GEMINI SUMMARY --------------------
def summarize_with_gemini(company_name, website, news_text):
    prompt = f"""
You are a sales assistant. Summarize the company "{company_name}" using the info below.
Include:
- Official website: {website}
- Recent news (headlines + short notes): {news_text}

Return as plain English text ONLY. No markdown, no asterisks, no bullets, no headings.
Keep it concise and useful for an IT sales representative.
"""
    model = genai.GenerativeModel("gemini-2.5-flash")
    try:
        response = model.generate_content(prompt)
        return (response.text or "").replace("*", "").strip()
    except Exception as e:
        return f"Error generating summary: {e}"


# -------------------- ROUTES --------------------
@app.get("/")
def root():
    return {"message": "Backend is running with Gemini AI + News API 🚀"}


@app.get("/search_companies")
def search_companies(query: str = Query(..., description="Company name to search")):
    candidate_queries = [
        f"{query} site:linkedin.com",
        f"{query} site:crunchbase.com"
    ]
    candidates = []
    for q in candidate_queries:
        try:
            results = duckduckgo_search(q, max_results=3)
            for r in results:
                if len(candidates) < 5 and r["url"] not in [c["url"] for c in candidates]:
                    candidates.append(r)
        except Exception as e:
            print(f"Search error: {e}")
    return {"candidates": candidates}


@app.get("/company_info")
def company_info(selected_name: Optional[str] = Query(None, description="Selected company name")):
    if not selected_name or selected_name.strip() == "":
        return {"error": "Please provide a valid selected_name query parameter."}

    website = get_official_website(selected_name) or "Unknown"

    # Fetch top 4 news
    news_list = fetch_company_news(selected_name)
    news_text = " | ".join(
        [f"{n.get('title', '')}. {n.get('description', '')}" for n in news_list if n.get("title")]
    ) or "No recent news found."

    summary = summarize_with_gemini(selected_name, website, news_text)

    return {
        "company": selected_name,
        "website": website,
        "summary": summary,
        "news": news_list  # top 4 only
    }

