"""
collector.py — The MAIN intelligence collection engine
Calls tech_detector + seo_analyzer + adds business signals
This is where ALL the value comes together
"""

import httpx
import re
import json
from bs4 import BeautifulSoup
from typing import Dict
from urllib.parse import urlparse
from datetime import datetime

from tech_detector import detect_technologies
from seo_analyzer import analyze_seo


async def collect_intelligence(url: str, depth: str = "full") -> Dict:
    """
    MASTER FUNCTION — Collects EVERYTHING about a business website.
    depth: basic (free), full (pro), deep (business), maximum (enterprise)
    """
    
    # Clean URL
    url = url.strip().lower()
    url = re.sub(r'^https?://', '', url)
    url = re.sub(r'^www\.', '', url)
    url = url.rstrip("/")
    
    result = {
        "url": url,
        "analyzed_at": datetime.now().isoformat(),
        "data_depth": depth,
        
        # Core sections
        "basic_info": {},
        "contact_info": {},
        "social_media": {},
        "technologies": {},
        "seo": {},
        "content_analysis": {},
        "business_signals": {},
        
        # Final scores
        "overall_score": 0,
        "intelligence_summary": "",
        "quick_facts": [],
    }
    
    try:
        # =====================
        # FETCH THE WEBSITE
        # =====================
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        
        response = httpx.get(f"https://{url}", headers=headers, timeout=20, follow_redirects=True)
        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        text_content = soup.get_text(separator=" ", strip=True)
        html_lower = html.lower()
        
        # =====================
        # 1. BASIC BUSINESS INFO
        # =====================
        basic = {}
        
        # Title
        title = soup.find("title")
        basic["title"] = title.string.strip() if title and title.string else None
        
        # Description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        basic["description"] = meta_desc["content"].strip() if meta_desc and meta_desc.get("content") else None
        
        # OG data
        og_title = soup.find("meta", attrs={"property": "og:title"})
        og_desc = soup.find("meta", attrs={"property": "og:description"})
        og_image = soup.find("meta", attrs={"property": "og:image"})
        og_site_name = soup.find("meta", attrs={"property": "og:site_name"})
        og_type = soup.find("meta", attrs={"property": "og:type"})
        
        basic["og_title"] = og_title["content"] if og_title and og_title.get("content") else None
        basic["og_site_name"] = og_site_name["content"] if og_site_name and og_site_name.get("content") else None
        basic["og_type"] = og_type["content"] if og_type and og_type.get("content") else None
        basic["logo_url"] = og_image["content"] if og_image and og_image.get("content") else None
        
        # Language
        html_tag = soup.find("html")
        basic["language"] = html_tag.get("lang", "unknown") if html_tag else "unknown"
        
        # Domain analysis
        parsed = urlparse(f"https://{url}")
        basic["domain"] = parsed.netloc
        tld = parsed.netloc.split(".")[-1]
        basic["tld"] = tld
        
        # Industry guess
        basic["industry_guess"] = guess_industry(basic.get("description", "") + " " + (basic.get("title") or ""), html_lower)
        
        # Company size estimate
        basic["size_estimate"] = estimate_size(html_lower, text_content)
        
        result["basic_info"] = basic
        
        # =====================
        # 2. CONTACT INFORMATION (HIGH VALUE $$$)
        # =====================
        contact = {}
        
        # Emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        all_emails = re.findall(email_pattern, html)
        
        # Filter junk emails
        junk_keywords = ["example", "test", "email.com", "yourdomain", "domain.com",
                        "sentry", "w3.org", "schema.org", "localhost", "placeholder",
                        "sample", "mozilla", "chrome", "webmaster", "noreply@w3"]
        clean_emails = [e for e in all_emails if not any(j in e.lower() for j in junk_keywords)]
        clean_emails = list(set(clean_emails))
        clean_emails.sort()
        
        contact["emails"] = clean_emails[:10]
        contact["email_count"] = len(clean_emails)
        
        # Phone numbers
        phone_pattern = r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        phones = re.findall(phone_pattern, text_content)
        contact["phones"] = list(set([p.strip() for p in phones[:5]]))
        
        # Address hints
        address_words = ["address", "location", "headquarters", "office", "street", 
                        "avenue", "blvd", "suite", "floor", "building"]
        address_blocks = []
        for word in address_words:
            for element in soup.find_all(string=re.compile(word, re.I)):
                parent = element.find_parent()
                if parent and len(parent.get_text().strip()) < 300:
                    address_blocks.append(parent.get_text().strip()[:200])
        contact["address_hints"] = list(set(address_blocks))[:5]
        
        result["contact_info"] = contact
        
        # =====================
        # 3. SOCIAL MEDIA
        # =====================
        social = {}
        all_links = [a.get("href", "") for a in soup.find_all("a", href=True)]
        
        social_map = {
            "twitter": ["twitter.com/", "x.com/"],
            "facebook": ["facebook.com/", "fb.com/"],
            "instagram": ["instagram.com/"],
            "linkedin": ["linkedin.com/"],
            "youtube": ["youtube.com/"],
            "tiktok": ["tiktok.com/@"],
            "github": ["github.com/"],
            "pinterest": ["pinterest.com/"],
            "medium": ["medium.com/@"],
            "discord": ["discord.gg/", "discord.com/"],
            "slack": ["slack.com/"],
            "telegram": ["t.me/"],
            "whatsapp": ["wa.me/", "whatsapp.com/"],
            "threads": ["threads.net/@"],
            "mastodon": ["mastodon.social/"],
            "substack": ["substack.com/"],
        }
        
        for platform, patterns in social_map.items():
            matches = []
            for link in all_links:
                for pattern in patterns:
                    if pattern in link.lower():
                        # Extract handle
                        handle = link.lower().split(pattern)[-1].split("?")[0].split("/")[0].split("#")[0]
                        if handle and handle not in ["share", "intent", "channel", "company"]:
                            matches.append({
                                "url": link,
                                "handle": handle,
                            })
            if matches:
                # Deduplicate by handle
                seen_handles = set()
                unique = []
                for m in matches:
                    if m["handle"] not in seen_handles:
                        seen_handles.add(m["handle"])
                        unique.append(m)
                social[platform] = unique[:2]
        
        social["platform_count"] = len([k for k in social.keys() if k != "platform_count"])
        social["platforms_list"] = [k for k in social.keys() if k != "platform_count"]
        
        result["social_media"] = social
        
        # =====================
        # 4. TECHNOLOGY STACK (if depth >= full)
        # =====================
        if depth in ["full", "deep", "maximum"]:
            result["technologies"] = await detect_technologies(url)
        else:
            result["technologies"] = {"note": "Upgrade to Pro for full tech stack detection"}
        
        # =====================
        # 5. SEO ANALYSIS (if depth >= full)
        # =====================
        if depth in ["full", "deep", "maximum"]:
            result["seo"] = await analyze_seo(url)
        else:
            result["seo"] = {"note": "Upgrade to Pro for complete SEO audit"}
        
        # =====================
        # 6. CONTENT ANALYSIS
        # =====================
        content = {}
        
        # Pages estimate
        internal_links = [a.get("href") for a in soup.find_all("a", href=True)
                         if a.get("href", "").startswith("/") or url in a.get("href", "")]
        content["estimated_pages"] = len(set(internal_links))
        
        # Blog detection
        blog_words = ["blog", "article", "post", "news", "insights", "resources", "stories", "thoughts"]
        content["has_blog"] = any(w in html_lower for w in blog_words)
        
        # Word count
        words = re.findall(r'\b\w+\b', text_content)
        content["word_count"] = len(words)
        
        # Forms (lead generation)
        forms = soup.find_all("form")
        content["form_count"] = len(forms)
        content["has_lead_capture"] = len(forms) > 0
        
        # CTAs
        cta_words = ["sign up", "get started", "try free", "book demo", "contact us",
                     "subscribe", "download", "free trial", "start now", "join now",
                     "schedule", "register", "enroll", "buy now", "add to cart"]
        found_ctas = [c for c in cta_words if c in html_lower]
        content["ctas"] = found_ctas
        content["cta_count"] = len(found_ctas)
        
        # Content freshness
        year_pattern = r'\b(20[2][0-9])\b'
        years_found = re.findall(year_pattern, text_content)
        if years_found:
            latest_year = max(int(y) for y in years_found)
            content["latest_year_mentioned"] = latest_year
            content["freshness"] = "recent" if latest_year >= 2023 else "outdated" if latest_year < 2022 else "moderate"
        else:
            content["freshness"] = "unknown"
        
        # Testimonials/trust
        trust_words = ["testimonial", "review", "customer story", "case study", 
                       "success story", "what our customers", "trusted by"]
        content["has_testimonials"] = any(w in html_lower for w in trust_words)
        
        # Pricing page
        content["has_pricing_page"] = "pricing" in html_lower or "plans" in html_lower
        
        # Documentation
        content["has_docs"] = any(w in html_lower for w in ["documentation", "api docs", "developer", "docs"])
        
        result["content_analysis"] = content
        
        # =====================
        # 7. BUSINESS SIGNALS ($$$ GROWTH INDICATORS)
        # =====================
        signals = {}
        
        # Funding signals
        fund_words = ["funded", "series a", "series b", "series c", "seed round", 
                      "investment", "raised", "backed by", "venture", "angel", "investors",
                      "valuation", "ipo", "acquisition"]
        signals["funding_signals"] = [w for w in fund_words if w in html_lower]
        signals["likely_funded"] = len(signals["funding_signals"]) > 0
        
        # Hiring signals
        hire_words = ["we're hiring", "careers", "job", "join our team", "open positions",
                      "job openings", "work with us", "career page", "now hiring", "talent"]
        signals["hiring_signals"] = [w for w in hire_words if w in html_lower]
        signals["is_hiring"] = len(signals["hiring_signals"]) > 0
        
        # Revenue model
        revenue_words = ["pricing", "plans", "subscription", "free trial", "per month",
                        "starting at", "from $", "enterprise plan", "custom pricing"]
        signals["revenue_model_signals"] = [w for w in revenue_words if w in html_lower]
        signals["likely_saas"] = len(signals["revenue_model_signals"]) > 0
        
        # B2B vs B2C
        b2b_words = ["enterprise", "api", "integration", "workflow", "dashboard", 
                     "team", "business", "organization", "corporate", "b2b"]
        b2c_words = ["personal", "individual", "family", "home", "lifestyle", 
                     "consumer", "b2c", "personal use"]
        b2b_score = sum(1 for w in b2b_words if w in html_lower)
        b2c_score = sum(1 for w in b2c_words if w in html_lower)
        
        if b2b_score > b2c_score:
            signals["business_model"] = "B2B"
        elif b2c_score > b2b_score:
            signals["business_model"] = "B2C"
        else:
            signals["business_model"] = "Hybrid/B2B2C"
        
        # Growth indicators
        growth_words = ["growing", "expanding", "scaling", "new feature", 
                       "launch", "milestone", "million users", "thousand customers"]
        signals["growth_signals"] = [w for w in growth_words if w in html_lower]
        signals["appears_growing"] = len(signals["growth_signals"]) > 0
        
        # Trust/security signals
        trust_signals = ["ssl", "encryption", "privacy", "gdpr", "compliance", 
                        "soc 2", "security", "certified", "iso", "hipaa", "pci"]
        signals["trust_compliance_signals"] = [w for w in trust_signals if w in html_lower]
        signals["trust_level"] = "high" if len(signals["trust_compliance_signals"]) >= 3 else "moderate" if len(signals["trust_compliance_signals"]) >= 1 else "basic"
        
        # Partnership signals
        partner_words = ["partner", "integration", "works with", "compatible with",
                        "connect", "ecosystem", "marketplace", "api partners"]
        signals["partnership_signals"] = [w for w in partner_words if w in html_lower]
        
        # Awards/recognition
        award_words = ["award", "winner", "recognized", "top", "best", "leader",
                      "featured", "featured in", "named", "ranked"]
        signals["recognition_signals"] = [w for w in award_words if w in html_lower]
        
        result["business_signals"] = signals
        
        # =====================
        # 8. OVERALL SCORE
        # =====================
        score_components = []
        
        # SEO contribution
        seo_score = result.get("seo", {}).get("score", 0) if isinstance(result.get("seo"), dict) else 50
        score_components.append(seo_score * 0.25)
        
        # Tech sophistication
        tech_score = result.get("technologies", {}).get("modern_score", 0) if isinstance(result.get("technologies"), dict) else 50
        score_components.append(tech_score * 0.20)
        
        # Social presence (0-30)
        social_count = social.get("platform_count", 0)
        score_components.append(min(social_count * 5, 30) * 0.15)
        
        # Business signals (0-25)
        signal_score = 0
        if signals.get("likely_funded"): signal_score += 8
        if signals.get("is_hiring"): signal_score += 7
        if signals.get("likely_saas"): signal_score += 6
        if signals.get("appears_growing"): signal_score += 4
        if signals.get("trust_level") == "high": signal_score += 5
        elif signals.get("trust_level") == "moderate": signal_score += 2
        score_components.append(signal_score * 0.20)
        
        # Content quality (0-20)
        content_score = 0
        if content.get("has_blog"): content_score += 4
        if content.get("has_lead_capture"): content_score += 4
        if content.get("cta_count", 0) > 0: content_score += 3
        if content.get("has_testimonials"): content_score += 3
        if content.get("freshness") == "recent": content_score += 3
        if content.get("word_count", 0) > 500: content_score += 3
        score_components.append(content_score * 0.20)
        
        overall = round(sum(score_components))
        result["overall_score"] = max(0, min(100, overall))
        
        # =====================
        # 9. SUMMARY + QUICK FACTS
        # =====================
        facts = []
        
        name = basic.get("og_site_name") or basic.get("title") or url
        facts.append(f"🏢 Business: {name}")
        
        if basic.get("industry_guess"):
            facts.append(f"📋 Industry: {basic['industry_guess']}")
        
        if signals.get("business_model"):
            facts.append(f"🎯 Model: {signals['business_model']}")
        
        if signals.get("likely_funded"):
            facts.append(f"💰 Likely funded/invested")
        
        if signals.get("is_hiring"):
            facts.append(f"📈 Currently hiring — growing team")
        
        if signals.get("likely_saas"):
            facts.append(f"💎 SaaS/recurring revenue model")
        
        tech_count = result.get("technologies", {}).get("tech_count", 0) if isinstance(result.get("technologies"), dict) else 0
        if tech_count > 0:
            facts.append(f"⚙️ {tech_count} technologies detected")
        
        if social_count > 0:
            facts.append(f"📱 Active on {social_count} social platforms")
        
        if contact.get("email_count", 0) > 0:
            facts.append(f"📧 {contact['email_count']} contact emails found")
        
        facts.append(f"🏆 Overall score: {result['overall_score']}/100")
        
        result["quick_facts"] = facts
        result["intelligence_summary"] = " | ".join(facts)
        
    except httpx.TimeoutException:
        result["error"] = "Website timeout (20s). May be slow or blocking automated requests."
    except httpx.ConnectError:
        result["error"] = "Could not connect. Website may be down, non-existent, or blocking requests."
    except Exception as e:
        result["error"] = f"Analysis error: {str(e)}"
    
    return result


# =====================
# HELPER FUNCTIONS
# =====================

def guess_industry(text: str, html_lower: str) -> str:
    """Guess business industry from content"""
    text = (text or "").lower() + " " + html_lower
    
    industries = {
        "Technology/SaaS": ["software", "platform", "api", "cloud", "saas", "app", 
                            "digital", "tech", "ai", "machine learning", "data", "automation"],
        "E-Commerce/Retail": ["shop", "store", "buy", "sell", "cart", "product", 
                              "retail", "marketplace", "order", "checkout", "shopping"],
        "Finance/Fintech": ["bank", "finance", "invest", "trading", "payment", 
                           "crypto", "money", "fintech", "wealth", "insurance"],
        "Healthcare": ["health", "medical", "doctor", "hospital", "pharma",
                       "therapy", "wellness", "fitness", "care", "clinical"],
        "Education": ["learn", "course", "education", "school", "university",
                      "training", "academy", "teaching", "student", "certification"],
        "Marketing/Advertising": ["marketing", "advertising", "seo", "content",
                                  "brand", "campaign", "analytics", "growth", "social media"],
        "Real Estate": ["real estate", "property", "housing", "rent", "mortgage",
                        "apartment", "home", "commercial property"],
        "Food & Beverage": ["food", "restaurant", "cafe", "recipe", "menu",
                            "delivery", "catering", "cook", "dining"],
        "Travel/Tourism": ["travel", "hotel", "flight", "vacation", "booking",
                          "tourism", "destination", "airline", "cruise"],
        "Entertainment/Media": ["entertainment", "game", "music", "video", "stream",
                               "media", "film", "podcast", "content platform"],
        "Legal": ["law", "legal", "attorney", "lawyer", "compliance", 
                  "regulation", "contract", "justice"],
        "Consulting": ["consulting", "advisory", "strategy", "professional services",
                      "management", "expertise", "advisor"],
        "Logistics/Transport": ["logistics", "shipping", "freight", "delivery",
                               "transport", "warehouse", "supply chain"],
        "Construction": ["construction", "building", "architecture", "engineering",
                        "infrastructure", "renovation"],
    }
    
    best_industry = "Unknown"
    best_score = 0
    
    for industry, keywords in industries.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_industry = industry
    
    return best_industry if best_score > 0 else "General/Other"


def estimate_size(html_lower: str, text_content: str) -> str:
    """Estimate company size from website signals"""
    
    large_signals = ["enterprise", "global presence", "fortune", "worldwide", 
                    "thousands of", "million", "international offices", "public company"]
    medium_signals = ["growing team", "expanding", "100+", "50+", "hundreds of", 
                     "offices in", "established"]
    small_signals = ["startup", "small team", "founded", "bootstrap", "indie", 
                    "solo", "family-owned", "local business", "boutique"]
    
    large = sum(1 for s in large_signals if s in html_lower)
    medium = sum(1 for s in medium_signals if s in html_lower)
    small = sum(1 for s in small_signals if s in html_lower)
    
    if large > medium and large > small:
        return "Large (500+ employees likely)"
    elif medium > small:
        return "Medium (50-500 employees likely)"
    elif small > 0:
        return "Small/Startup (1-50 employees likely)"
    else:
        return "Size unknown"