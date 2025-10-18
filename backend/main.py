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


def summarize_with_langchain(company_name, website, news_text):
    prompt = f"""
You are a sales assistant. Summarize the company "{company_name}" using the info below.
Include:
- Official website: {website}
- Recent news: {news_text}

Return plain English only. No markdown, no asterisks, no bullets, no headings.
Keep it concise and useful for an IT sales representative.
"""
    model = genai.GenerativeModel("gemini-2.5-flash")
    try:
        resp = model.generate_content(prompt)
        return (resp.text or "").replace("*", "").strip()
    except Exception as e:
        return f"Error generating summary: {e}"

# ---------- routes ----------
@app.get("/")
def root():
    return {"message": "Backend running ✅"}

@app.get("/search_companies")
def search_companies(query: str = Query(..., description="Company name to search")):
    candidates, seen = [], set()
    for q in (f"{query} site:linkedin.com", f"{query} site:crunchbase.com"):
        try:
            for r in duckduckgo_search(q, max_results=3):
                if r["url"] not in seen and len(candidates) < 5:
                    candidates.append(r); seen.add(r["url"])
        except Exception as e:
            print("Search error:", e)
    return {"candidates": candidates}

@app.get("/company_info")
async def company_info(
    selected_name: Optional[str] = Query(None, description="Selected company name"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    if not selected_name or selected_name.strip() == "":
        return {"error": "Please provide a valid selected_name query parameter."}

    website = get_official_website(selected_name) or "Unknown"
    news_list = fetch_company_news(selected_name)

    news_text = " | ".join([
        f"{n.get('title','')}. {n.get('description','')}".strip()
        for n in news_list if n.get("title")
    ]) or "No recent news found."

    summary = summarize_with_gemini(selected_name, website, news_text)

    # persist (associate user if logged in; guest otherwise)
    search = Search(user_id=(user or {}).get("user_id"), query_text=selected_name, selected_name=selected_name)
    db.add(search); db.flush()

    db.add(Summary(search_id=search.id, company_name=selected_name, official_website=website, summary_text=summary))
    for idx, n in enumerate(news_list[:4], start=1):
        db.add(NewsItem(
            search_id=search.id,
            title=n.get("title"),
            description=n.get("description"),
            url=n.get("url"),
            source=n.get("source"),
            published_at=n.get("publishedAt"),
            rank=idx
        ))
    db.commit()

    return {"company": selected_name, "website": website, "summary": summary, "news": news_list}

@app.get("/history")
async def history(limit: int = 10, db: Session = Depends(get_db), user = Depends(get_current_user)):
    if not user or not user.get("user_id"):
        raise HTTPException(status_code=401, detail="Login required")
    uid = user["user_id"]
    rows = (
        db.query(Search)
        .filter(Search.user_id == uid)
        .order_by(Search.created_at.desc())
        .limit(limit)
        .all()
    )
    out = []
    for s in rows:
        summ = db.query(Summary).filter(Summary.search_id == s.id).first()
        news = db.query(NewsItem).filter(NewsItem.search_id == s.id).order_by(NewsItem.rank.asc()).all()
        out.append({
            "query": s.query_text,
            "selected_name": s.selected_name,
            "created_at": s.created_at.isoformat(),
            "summary": getattr(summ, "summary_text", None),
            "website": getattr(summ, "official_website", None),
            "news": [
                {"title": n.title, "description": n.description, "url": n.url, "source": n.source, "publishedAt": n.published_at}
                for n in news
            ]
        })
    return {"items": out}

