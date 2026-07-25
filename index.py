from fastapi import FastAPI, Query, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
import httpx
import re
import time
import secrets
from bs4 import BeautifulSoup
from typing import Dict
from urllib.parse import urlparse

# === APP ===
app = FastAPI(title="BizIntel API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# === PRICING ===
TIERS = {
    "free": {"price": 0, "requests_per_month": 50, "data_depth": "basic"},
    "pro": {"price": 49, "requests_per_month": 2000, "data_depth": "full"},
    "business": {"price": 199, "requests_per_month": 10000, "data_depth": "deep"},
    "enterprise": {"price": 999, "requests_per_month": -1, "data_depth": "maximum"},
}

# === API KEY CHECK ===
async def verify_key(x_api_key: str = Header(..., alias="X-API-Key")):
    if not x_api_key or not x_api_key.startswith("biz_"):
        raise HTTPException(status_code=401, detail="Invalid API key. Register at /v1/register")
    return {"plan": "free", "data_depth": "basic"}

# ==========================================
# PUBLIC ENDPOINTS
# ==========================================

@app.get("/")
async def home():
    return {
        "api": "BizIntel API", 
        "version": "1.0.0", 
        "status": "working!",
        "docs": "/docs", 
        "plans": "/v1/plans",
        "register": "/v1/register?email=you@email.com"
    }

@app.get("/v1/plans")
async def get_plans():
    return {"plans": TIERS, "popular": "Pro ($49/mo)"}

@app.post("/v1/register")
async def register(email: str = Query(...)):
    api_key = f"biz_{secrets.token_urlsafe(32)}"
    return {
        "success": True,
        "data": {
            "api_key": api_key,
            "plan": "free",
            "requests_limit": 50,
        },
        "next_step": "Use X-API-Key header with this key"
    }

# ==========================================
# CORE ENDPOINTS
# ==========================================

@app.post("/v1/quick-scan")
async def quick_scan(url: str = Query(...), auth: dict = Depends(verify_key)):
    start_time = time.time()
    result = await analyze_website(url, "basic")
    elapsed = round(time.time() - start_time, 2)
    result["response_time"] = f"{elapsed}s"
    return result

@app.post("/v1/analyze")
async def full_analyze(url: str = Query(...), auth: dict = Depends(verify_key)):
    start_time = time.time()
    result = await analyze_website(url, "full")
    elapsed = round(time.time() - start_time, 2)
    result["response_time"] = f"{elapsed}s"
    return result

@app.get("/v1/usage")
async def usage(auth: dict = Depends(verify_key)):
    return {"plan": auth["plan"], "remaining": "unlimited on this version"}

# ==========================================
# MAIN ANALYSIS ENGINE
# ==========================================

async def analyze_website(url: str, depth: str = "basic") -> Dict:
    url = url.strip().lower()
    url = re.sub(r'^https?://', '', url)
    url = re.sub(r'^www\.', '', url)
    url = url.rstrip("/")
    
    result = {
        "url": url,
        "status": "success",
        "basic_info": {},
        "contact_info": {},
        "social_media": {},
        "technologies": {},
        "seo": {},
        "business_signals": {},
        "overall_score": 0,
        "intelligence_summary": "",
    }
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
        }
        response = httpx.get(f"https://{url}", headers=headers, timeout=8, follow_redirects=True)
        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        html_lower = html.lower()
        text_content = soup.get_text(separator=" ", strip=True)
        
        # === 1. BASIC INFO ===
        basic = {}
        title_tag = soup.find("title")
        basic["title"] = title_tag.string.strip() if title_tag and title_tag.string else None
        
        meta_desc = soup.find("meta", attrs={"name": "description"})
        basic["description"] = meta_desc["content"].strip() if meta_desc and meta_desc.get("content") else None
        
        og_site = soup.find("meta", attrs={"property": "og:site_name"})
        basic["site_name"] = og_site["content"] if og_site and og_site.get("content") else None
        
        parsed = urlparse(f"https://{url}")
        basic["domain"] = parsed.netloc
        basic["tld"] = parsed.netloc.split(".")[-1]
        html_tag = soup.find("html")
        basic["language"] = html_tag.get("lang", "unknown") if html_tag else "unknown"
        
        desc_text = (basic.get("description") or "") + " " + html_lower
        industries = {
            "Technology/SaaS": ["software", "platform", "api", "cloud", "saas", "app", "ai"],
            "E-Commerce": ["shop", "store", "buy", "sell", "cart", "product", "marketplace"],
            "Finance": ["bank", "finance", "invest", "payment", "crypto", "fintech"],
            "Healthcare": ["health", "medical", "doctor", "hospital", "wellness"],
            "Education": ["learn", "course", "education", "school", "training"],
            "Marketing": ["marketing", "advertising", "seo", "brand", "campaign"],
        }
        best_industry = "Other"
        best_score = 0
        for ind, kws in industries.items():
            score = sum(1 for kw in kws if kw in desc_text)
            if score > best_score:
                best_score = score
                best_industry = ind
        basic["industry_guess"] = best_industry if best_score > 0 else "Other"
        
        result["basic_info"] = basic
        
        # === 2. CONTACT INFO ===
        contact = {}
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        all_emails = re.findall(email_pattern, html)
        junk = ["example", "test", "w3.org", "schema.org", "localhost", "noreply", "yourdomain"]
        clean_emails = [e for e in all_emails if not any(j in e.lower() for j in junk)]
        contact["emails"] = list(set(clean_emails))[:5]
        contact["email_count"] = len(set(clean_emails))
        result["contact_info"] = contact
        
        # === 3. SOCIAL MEDIA ===
        social = {}
        all_links = [a.get("href", "") for a in soup.find_all("a", href=True)]
        social_map = {
            "twitter": ["twitter.com/", "x.com/"],
            "facebook": ["facebook.com/"],
            "instagram": ["instagram.com/"],
            "linkedin": ["linkedin.com/"],
            "youtube": ["youtube.com/"],
            "github": ["github.com/"],
            "tiktok": ["tiktok.com/@"],
        }
        for platform, patterns in social_map.items():
            for link in all_links:
                for pattern in patterns:
                    if pattern in link.lower():
                        handle = link.lower().split(pattern)[-1].split("?")[0].split("/")[0]
                        if handle and len(handle) > 1:
                            social[platform] = {"handle": handle, "url": link}
                            break
        social["platform_count"] = len(social)
        result["social_media"] = social
        
        # === 4. TECHNOLOGIES ===
        if depth in ["full", "deep", "maximum"]:
            techs = detect_tech_simple(html_lower)
            result["technologies"] = techs
        else:
            result["technologies"] = {"note": "Upgrade to Pro for tech detection"}
        
        # === 5. SEO ===
        if depth in ["full", "deep", "maximum"]:
            seo = analyze_seo_simple(soup, html)
            result["seo"] = seo
        else:
            result["seo"] = {"note": "Upgrade to Pro for SEO audit"}
        
        # === 6. BUSINESS SIGNALS ===
        signals = {}
        fund_words = ["funded", "series a", "investment", "raised", "backed by", "venture"]
        signals["funding_signals"] = [w for w in fund_words if w in html_lower]
        signals["likely_funded"] = len(signals["funding_signals"]) > 0
        
        hire_words = ["hiring", "careers", "join our team", "open positions"]
        signals["hiring_signals"] = [w for w in hire_words if w in html_lower]
        signals["is_hiring"] = len(signals["hiring_signals"]) > 0
        
        revenue_words = ["pricing", "plans", "subscription", "free trial", "per month"]
        signals["revenue_signals"] = [w for w in revenue_words if w in html_lower]
        signals["likely_saas"] = len(signals["revenue_signals"]) > 0
        
        result["business_signals"] = signals
        
        # === 7. SCORE ===
        score = 50
        if contact.get("email_count", 0) > 0: score += 10
        if len(social) > 0: score += 10
        if signals.get("likely_funded"): score += 10
        if signals.get("is_hiring"): score += 5
        if signals.get("likely_saas"): score += 5
        result["overall_score"] = min(100, score)
        
        # === 8. SUMMARY ===
        name = basic.get("site_name") or basic.get("title") or url
        summary = f"Business: {name} | Industry: {basic.get('industry_guess', 'Unknown')}"
        if contact.get("emails"): summary += f" | Emails: {contact['email_count']}"
        if len(social) > 0: summary += f" | Social: {len(social)} platforms"
        summary += f" | Score: {result['overall_score']}/100"
        result["intelligence_summary"] = summary
        
    except httpx.TimeoutException:
        result["status"] = "timeout"
        result["error"] = "Website took too long to respond (8s limit)"
    except httpx.ConnectError:
        result["status"] = "connection_failed" 
        result["error"] = "Could not connect to website"
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)[:200]
    
    return result


def detect_tech_simple(html_lower: str) -> Dict:
    techs_found = []
    tech_list = {
        "WordPress": ["wp-content", "wp-includes"],
        "Shopify": ["cdn.shopify.com", "shopify"],
        "React": ["react", "react-dom"],
        "Next.js": ["_next/static", "next.js"],
        "Vue.js": ["vue", "vuejs"],
        "Angular": ["ng-app", "angular"],
        "Bootstrap": ["bootstrap"],
        "Tailwind CSS": ["tailwind"],
        "Google Analytics": ["google-analytics.com", "gtag"],
        "Stripe": ["stripe.com", "stripe.js"],
        "PayPal": ["paypal.com"],
        "Cloudflare": ["cloudflare"],
        "HubSpot": ["hubspot.com", "hubspot"],
        "Mailchimp": ["mailchimp.com"],
        "Intercom": ["intercom"],
        "YouTube": ["youtube.com"],
        "Google Fonts": ["fonts.googleapis.com"],
    }
    for tech, patterns in tech_list.items():
        for pattern in patterns:
            if pattern in html_lower:
                techs_found.append(tech)
                break
    return {"technologies": techs_found, "count": len(techs_found)}


def analyze_seo_simple(soup, html: str) -> Dict:
    score = 100
    details = {}
    title = soup.find("title")
    if title and title.string:
        details["title"] = title.string.strip()
    else:
        score -= 20
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        details["meta_description"] = meta["content"][:160]
    else:
        score -= 15
    h1 = soup.find_all("h1")
    details["h1_count"] = len(h1)
    if len(h1) == 0:
        score -= 10
    viewport = soup.find("meta", attrs={"name": "viewport"})
    details["mobile_friendly"] = viewport is not None
    if not viewport:
        score -= 10
    images = soup.find_all("img")
    missing_alt = sum(1 for img in images if not img.get("alt"))
    details["images"] = len(images)
    details["missing_alt"] = missing_alt
    if missing_alt > 0:
        score -= min(10, missing_alt * 2)
    details["page_size_kb"] = round(len(html) / 1024, 1)
    return {"score": max(0, min(100, score)), "details": details}


# === VERCEL HANDLER ===
handler = Mangum(app, lifespan="off")