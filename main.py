"""
main.py — COMPLETE APPLICATION
API endpoints + LLM chat + Beautiful Web UI
All in ONE server, ONE deployment
"""

from fastapi import FastAPI, Request, Depends, HTTPException, Query, Header
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import time
import json
import re

from config import APP_NAME, APP_VERSION, TIERS, OPENAI_API_KEY, LLM_MODEL, LLM_MAX_TOKENS
from database import db, create_user, check_and_increment_usage, save_cache, get_cache, log_request
from collector import collect_intelligence

# =====================
# CREATE APP
# =====================
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="BizIntel API - Business Intelligence on ANY Website",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await db.connect()

@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()


# ==========================================
# AUTH DEPENDENCY
# ==========================================

async def verify_key(x_api_key: str = Header(..., alias="X-API-Key")):
    result = await check_and_increment_usage(x_api_key)
    if not result["allowed"]:
        raise HTTPException(status_code=429, detail=result)
    return result


# ==========================================
# PUBLIC ENDPOINTS (No auth needed)
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def home_page():
    return get_html_ui()

@app.get("/api")
async def api_home():
    return {
        "api": APP_NAME,
        "version": APP_VERSION,
        "endpoints": {
            "register": "POST /v1/register?email=you@email.com",
            "analyze": "POST /v1/analyze (requires API key)",
            "quick_scan": "POST /v1/quick-scan?url=example.com (requires API key)",
            "tech_stack": "POST /v1/tech-stack?url=example.com (Pro+)",
            "seo": "POST /v1/seo?url=example.com (Pro+)",
            "usage": "GET /v1/usage (requires API key)",
            "plans": "GET /v1/plans",
            "chat": "POST /chat (AI-powered)",
        },
        "docs": "/docs",
    }

@app.get("/v1/plans")
async def get_plans():
    return {
        "plans": TIERS,
        "popular": "Pro ($49/mo)",
        "best_value": "Business ($199/mo)",
    }

@app.post("/v1/register")
async def register_user(email: str = Query(..., description="Your email")):
    try:
        result = await create_user(email)
        return {
            "success": True,
            "message": "Welcome to BizIntel!",
            "data": result,
            "next_steps": [
                "1. Save your API key",
                "2. Try: curl -H 'X-API-Key: YOUR_KEY' -X POST /v1/analyze?url=stripe.com",
                "3. Or chat with AI at homepage",
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# CORE API ENDPOINTS (THE $$$)
# ==========================================

class AnalyzeRequest(BaseModel):
    url: str
    include_seo: bool = True
    include_technologies: bool = True

@app.post("/v1/analyze")
async def full_analyze(request: AnalyzeRequest, auth: dict = Depends(verify_key)):
    start_time = time.time()
    url = request.url
    depth = auth["data_depth"]

    # Check cache
    cached = await get_cache(url, depth)
    if cached:
        cached["from_cache"] = True
        cached["plan"] = auth["plan"]
        cached["requests_remaining"] = auth["remaining"]
        return cached

    # Collect intelligence
    result = await collect_intelligence(url, depth)
    elapsed = int((time.time() - start_time) * 1000)

    result["plan"] = auth["plan"]
    result["requests_remaining"] = auth["remaining"]
    result["response_time_ms"] = elapsed
    result["from_cache"] = False

    # Free tier limits
    if auth["plan"] == "free":
        result = apply_free_limits(result)

    await save_cache(url, result, depth)
    await log_request(auth["plan"], url, "analyze", elapsed, "success")

    return result

@app.post("/v1/quick-scan")
async def quick_scan(url: str = Query(...), auth: dict = Depends(verify_key)):
    start_time = time.time()
    result = await collect_intelligence(url, "basic")
    elapsed = int((time.time() - start_time) * 1000)

    quick = {
        "url": result["url"],
        "basic_info": result.get("basic_info", {}),
        "contact_info": result.get("contact_info", {}),
        "social_media": result.get("social_media", {}),
        "overall_score": result.get("overall_score", 0),
        "quick_facts": result.get("quick_facts", []),
        "intelligence_summary": result.get("intelligence_summary", ""),
        "plan": auth["plan"],
        "requests_remaining": auth["remaining"],
        "response_time_ms": elapsed,
        "upgrade_for_full": "Pro plan includes tech stack, SEO, business signals",
    }

    await log_request(auth["plan"], url, "quick_scan", elapsed, "success")
    return quick

@app.post("/v1/tech-stack")
async def tech_stack_only(url: str = Query(...), auth: dict = Depends(verify_key)):
    if "tech_detection" not in auth.get("features", []):
        raise HTTPException(status_code=403, detail={
            "error": "Tech detection requires Pro plan ($49/mo)",
            "current_plan": auth["plan"],
        })

    from tech_detector import detect_technologies
    result = await detect_technologies(url)
    result["plan"] = auth["plan"]
    result["requests_remaining"] = auth["remaining"]
    return result

@app.post("/v1/seo")
async def seo_audit(url: str = Query(...), auth: dict = Depends(verify_key)):
    if "seo_analysis" not in auth.get("features", []):
        raise HTTPException(status_code=403, detail={
            "error": "SEO analysis requires Pro plan ($49/mo)",
            "current_plan": auth["plan"],
        })

    from seo_analyzer import analyze_seo
    result = await analyze_seo(url)
    result["plan"] = auth["plan"]
    result["requests_remaining"] = auth["remaining"]
    return result

@app.get("/v1/usage")
async def check_usage(auth: dict = Depends(verify_key)):
    return {
        "plan": auth["plan"],
        "requests_remaining": auth["remaining"],
        "features": auth.get("features", []),
        "data_depth": auth.get("data_depth", "basic"),
        "plan_details": TIERS.get(auth["plan"], {}),
    }

@app.post("/v1/upgrade")
async def upgrade_plan(plan: str = Query(...), auth: dict = Depends(verify_key)):
    if plan not in TIERS:
        raise HTTPException(400, f"Invalid plan. Choose: {list(TIERS.keys())}")
    return {
        "message": "Email billing@bizintel.api to upgrade manually",
        "selected_plan": plan,
        "price": TIERS[plan]["price"],
        "features": TIERS[plan]["features"],
    }


# ==========================================
# LLM CHAT ENDPOINT
# ==========================================

@app.post("/chat")
async def chat_with_ai(request: Request):
    body = await request.json()
    message = body.get("message", "")
    url = extract_url(message)

    # Get real data from own API
    api_data = None
    if url:
        api_data = await collect_intelligence(url, "deep")

    # No OpenAI key = simple format
    if not OPENAI_API_KEY:
        if api_data:
            return {
                "response": format_data_simple(api_data),
                "analyzed_url": url,
                "data_source": "BizIntel API",
                "overall_score": api_data.get("overall_score"),
            }
        return {"response": "Mention a website URL to analyze. Example: 'Tell me about stripe.com'"}

    # Call LLM
    try:
        import openai
        client = openai.OpenAI(api_key=OPENAI_API_KEY)

        system_prompt = """You are BizIntel AI, a world-class business intelligence consultant.
You have REAL DATA from the BizIntel API. Present it beautifully:
- Start with executive summary
- Use clear sections with headers
- Include specific numbers from the data
- Add strategic insights
- End with actionable next steps"""

        context = ""
        if api_data:
            context = f"\n\nREAL API DATA:\n{json.dumps(api_data, indent=2, default=str)[:3000]}"

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt + context},
                {"role": "user", "content": message}
            ],
            max_tokens=LLM_MAX_TOKENS,
            temperature=0.7,
        )

        return {
            "response": response.choices[0].message.content,
            "analyzed_url": url,
            "data_source": "BizIntel API + AI",
            "overall_score": api_data.get("overall_score") if api_data else None,
        }

    except Exception as e:
        if api_data:
            return {"response": format_data_simple(api_data), "analyzed_url": url}
        return {"response": f"Error: {str(e)}", "analyzed_url": url}


@app.post("/analyze-chat")
async def analyze_and_chat(url: str = Query(...)):
    api_data = await collect_intelligence(url, "deep")

    if not OPENAI_API_KEY:
        return {
            "response": format_data_simple(api_data),
            "raw_data": api_data,
            "url": url,
            "score": api_data.get("overall_score", 0),
        }

    try:
        import openai
        client = openai.OpenAI(api_key=OPENAI_API_KEY)

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are BizIntel AI. Present business intelligence data beautifully."},
                {"role": "user", "content": f"Report on {url}.\nDATA:\n{json.dumps(api_data, indent=2, default=str)[:3000]}"},
            ],
            max_tokens=LLM_MAX_TOKENS,
            temperature=0.7,
        )

        return {
            "response": response.choices[0].message.content,
            "raw_data": api_data,
            "url": url,
            "score": api_data.get("overall_score", 0),
        }
    except Exception as e:
        return {
            "response": format_data_simple(api_data),
            "raw_data": api_data,
            "url": url,
            "score": api_data.get("overall_score", 0),
        }


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def extract_url(message: str) -> str:
    url_pattern = r'(?:https?://)?(?:www\.)?([a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})?)'
    match = re.search(url_pattern, message.lower())
    if match:
        return match.group(1).rstrip("/")

    triggers = ["analyze", "tell me about", "check", "research", "look up",
               "what about", "how about", "investigate", "scan", "intelligence on",
               "report on", "info on", "details about", "audit"]

    msg_lower = message.lower()
    for trigger in triggers:
        if trigger in msg_lower:
            after = msg_lower.split(trigger)[-1].strip()
            after = after.replace("'s website", "").replace("'s site", "")
            after = after.replace(" website", "").replace(" site", "")
            after = after.replace("the ", "").replace("company ", "")
            match = re.search(url_pattern, after)
            if match:
                return match.group(1).rstrip("/")

    return None


def format_data_simple(data: dict) -> str:
    lines = []
    lines.append("🔍 BIZINTEL BUSINESS INTELLIGENCE REPORT")
    lines.append("=" * 50)

    basic = data.get("basic_info", {})
    lines.append(f"\n🏢 Company: {basic.get('og_site_name') or basic.get('title') or data.get('url')}")
    if basic.get('description'):
        lines.append(f"📝 Description: {basic['description'][:200]}")
    if basic.get('industry_guess'):
        lines.append(f"📋 Industry: {basic['industry_guess']}")
    if basic.get('size_estimate'):
        lines.append(f"👥 Size: {basic['size_estimate']}")

    contact = data.get("contact_info", {})
    if contact.get("emails"):
        lines.append(f"\n📧 Emails Found: {len(contact['emails'])}")
        for email in contact["emails"][:5]:
            lines.append(f"   → {email}")

    social = data.get("social_media", {})
    if social.get("platforms_list"):
        lines.append(f"\n📱 Social Media ({social['platform_count']} platforms):")
        for platform in social["platforms_list"]:
            handles = social[platform]
            for h in handles[:1]:
                lines.append(f"   {platform}: @{h['handle']}")

    tech = data.get("technologies", {})
    if isinstance(tech, dict) and tech.get("technologies"):
        lines.append(f"\n⚙️ Technologies ({tech['tech_count']} detected):")
        categories = tech.get("categories", {})
        for cat, techs in categories.items():
            names = [t["name"] for t in techs[:5]]
            lines.append(f"   {cat}: {', '.join(names)}")

    seo = data.get("seo", {})
    if isinstance(seo, dict) and seo.get("score"):
        lines.append(f"\n🔍 SEO Score: {seo['score']}/100 (Grade: {seo.get('grade', 'N/A')})")
        if seo.get("critical_issues"):
            lines.append("   Critical Issues:")
            for issue in seo["critical_issues"][:3]:
                lines.append(f"   {issue}")

    signals = data.get("business_signals", {})
    if signals:
        lines.append(f"\n📈 Business Signals:")
        if signals.get("likely_funded"):
            lines.append("   💰 Likely funded")
        if signals.get("is_hiring"):
            lines.append("   📈 Currently hiring")
        if signals.get("likely_saas"):
            lines.append("   💎 SaaS model")
        if signals.get("business_model"):
            lines.append(f"   🎯 Model: {signals['business_model']}")

    lines.append(f"\n🏆 OVERALL SCORE: {data.get('overall_score', 0)}/100")
    lines.append("=" * 50)

    return "\n".join(lines)


def apply_free_limits(result: dict) -> dict:
    # Limit emails to 1
    if result.get("contact_info", {}).get("emails"):
        emails = result["contact_info"]["emails"]
        if len(emails) > 1:
            result["contact_info"]["emails_shown"] = 1
            result["contact_info"]["emails_hidden"] = len(emails) - 1
            result["contact_info"]["emails"] = [emails[0]]
            result["contact_info"]["upgrade_message"] = f"{len(emails)-1} more emails on Pro plan"

    # Limit tech to 5
    if isinstance(result.get("technologies"), dict):
        techs = result["technologies"].get("technologies", [])
        if len(techs) > 5:
            result["technologies"]["technologies"] = techs[:5]
            result["technologies"]["hidden_count"] = len(techs) - 5
            result["technologies"]["upgrade_message"] = f"{len(techs)-5} more on Pro plan"

    # Remove detailed SEO
    if isinstance(result.get("seo"), dict) and result["seo"].get("score"):
        result["seo"] = {
            "score": result["seo"].get("score"),
            "grade": result["seo"].get("grade"),
            "upgrade_message": "Full SEO audit on Pro plan",
        }

    # Remove detailed business signals
    if result.get("business_signals"):
        result["business_signals"] = {
            "signal_count": len(result["business_signals"]),
            "upgrade_message": "Full analysis on Pro plan",
        }

    result["upgrade_prompt"] = {
        "message": "You're seeing LIMITED data on FREE plan",
        "upgrade_to": "Pro ($49/mo)",
        "benefits": ["Full SEO audit", "Complete tech stack", "All emails", "Business signals", "2,000 requests"],
    }

    return result


# ==========================================
# BEAUTIFUL WEB UI (HTML)
# ==========================================

def get_html_ui() -> str:
    return '''
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BizIntel AI</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0a;font-family:Segoe UI,system-ui,sans-serif;color:#e0e0e0;height:100vh;display:flex;flex-direction:column}
.header{background:linear-gradient(135deg,#1a1a2e,#16213e);padding:20px 30px;display:flex;align-items:center;gap:15px;border-bottom:3px solid #e94560;flex-wrap:wrap}
.header h1{font-size:24px;color:#e94560;font-weight:800}
.header .sub{color:#888;font-size:14px}
.badge{background:#e94560;color:#fff;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:700}
.api-btn{background:#16213e;color:#4ecdc4;border:1px solid #4ecdc4;padding:8px 16px;border-radius:8px;cursor:pointer;font-size:13px;text-decoration:none;transition:all .2s}
.api-btn:hover{background:#4ecdc4;color:#0a0a0a}
.examples{padding:12px 30px;text-align:center;color:#666;font-size:13px;background:#111}
.examples span{color:#e94560;cursor:pointer;text-decoration:underline;margin:0 4px}
.chat-area{flex:1;overflow-y:auto;padding:20px 30px;display:flex;flex-direction:column;gap:12px}
.msg{max-width:85%;padding:15px 20px;border-radius:12px;line-height:1.7;animation:fadeIn .3s ease}
@keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.user{background:#1a1a2e;margin-left:auto;border:1px solid #333;align-self:flex-end}
.ai{background:linear-gradient(135deg,#16213e,#0f3460);border:1px solid #e94560;align-self:flex-start}
.ai strong{color:#e94560}
.score-bar{background:#333;border-radius:8px;height:24px;position:relative;overflow:hidden;margin:8px 0}
.score-fill{height:100%;border-radius:8px;transition:width 1s ease}
.score-text{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-weight:700;font-size:14px;color:#fff}
.input-area{padding:20px 30px;background:#1a1a2e;border-top:2px solid #333;display:flex;gap:10px}
.input-area input{flex:1;padding:15px 20px;background:#0a0a0a;border:1px solid #444;border-radius:10px;color:#e0e0e0;font-size:16px;outline:none;transition:border .2s}
.input-area input:focus{border-color:#e94560}
.input-area button{padding:15px 30px;background:#e94560;color:#fff;border:none;border-radius:10px;font-size:16px;cursor:pointer;font-weight:700;transition:background .2s}
.input-area button:hover{background:#c73650}
.input-area button:disabled{background:#555;cursor:not-allowed}
.loading{display:flex;gap:8px;padding:10px 20px}
.loading .dot{width:10px;height:10px;background:#e94560;border-radius:50%;animation:bounce .6s infinite alternate}
.loading .dot:nth-child(2){animation-delay:.1s}
.loading .dot:nth-child(3){animation-delay:.2s}
@keyframes bounce{to{transform:translateY(-15px);opacity:.3}}
</style>
</head>
<body>

<div class="header">
<h1>🔍 BizIntel AI</h1>
<span class="sub">Your AI Business Intelligence Consultant</span>
<span class="badge">Powered by Real Data</span>
<a href="/docs" class="api-btn">📚 API Docs</a>
<a href="/v1/plans" class="api-btn">💰 Pricing</a>
</div>

<div class="examples">
Try: 
<span onclick="send(\'Tell me about stripe.com\')">stripe.com</span> |
<span onclick="send(\'Analyze shopify.com\')">shopify.com</span> |
<span onclick="send(\'What tech stack does netflix.com use?\')">netflix.com tech</span> |
<span onclick="send(\'SEO audit for github.com\')">github.com SEO</span>
</div>

<div class="chat-area" id="chat"></div>

<div class="input-area">
<input type="text" id="input" placeholder="Ask about any business... e.g. Analyze stripe.com" autocomplete="off">
<button id="btn" onclick="sendMsg()">Analyze →</button>
</div>

<script>
const chat=document.getElementById(\'chat\');
const input=document.getElementById(\'input\');
const btn=document.getElementById(\'btn\');

function addMsg(text,isUser){
const d=document.createElement(\'div\');
d.className=isUser?\'msg user\':\'msg ai\';
d.innerHTML=text;
chat.appendChild(d);
chat.scrollTop=chat.scrollHeight;
}

function showLoading(){
const d=document.createElement(\'div\');
d.className=\'msg ai\';
d.innerHTML=\'<div class="loading"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div><span style="color:#888;margin-left:8px">Analyzing...</span>\';
d.id=\'loadingMsg\';
chat.appendChild(d);
chat.scrollTop=chat.scrollHeight;
}

function removeLoading(){
const l=document.getElementById(\'loadingMsg\');
if(l)chat.removeChild(l);
}

function esc(s){return s.replace(/&/g,\'&amp;\').replace(/</g,\'&lt;\').replace(/>/g,\'&gt;\')}

function formatRes(data){
if(!data.response)return esc(JSON.stringify(data));
let html=\'\';
if(data.analyzed_url)html+=\'<h3>🔍 Analysis: \'+esc(data.analyzed_url)+\'</h3>\';
if(data.overall_score){
const s=data.overall_score;
const c=s>=80?\'#4ecdc4\':s>=60?\'#f9ca24\':s>=40?\'#e94560\':\'#ff3838\';
html+=\'<div class="score-bar"><div class="score-fill" style="width:\'+s+\'%;background:\'+c+\'"></div><span class="score-text">\'+s+\'/100</span></div>\';
}
let text=data.response;
text=text.replace(/\\n\\n/g,\'<br><br>\');
text=text.replace(/\\n/g,\'<br>\');
text=text.replace(/\*\*(.*?)\*\*/g,\'<strong>$1</strong>\');
html+=\'<div>\'+text+\'</div>\';
if(data.data_source)html+=\'<br><small style="color:#666">📊 \'+esc(data.data_source)+\'</small>\';
return html;
}

async function sendMsg(){
const msg=input.value.trim();
if(!msg)return;
addMsg(esc(msg),true);
input.value=\'\';
btn.disabled=true;
showLoading();
try{
const res=await fetch(\'/chat\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({message:msg})});
const data=await res.json();
removeLoading();
addMsg(formatRes(data),false);
}catch(e){removeLoading();addMsg(\'Error. Try again.\',false);}
btn.disabled=false;
}

function send(text){input.value=text;sendMsg();}
input.addEventListener(\'keydown\',e=>{if(e.key===\'Enter\'&&!btn.disabled)sendMsg();});

addMsg(\'👋 <strong>Welcome to BizIntel AI!</strong><br><br>I analyze ANY business website:<br><br>• 🏢 Company info<br>• 📧 Contact emails<br>• 📱 Social media<br>• ⚙️ Tech stack<br>• 🔍 SEO audit<br>• 📈 Business signals<br><br>Just type a website URL!\',false);
</script>
</body>
</html>
'''


# ==========================================
# RUN SERVER
# ==========================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)