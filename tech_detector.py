"""
tech_detector.py — Detect 50+ technologies from any website
THIS IS YOUR $$$ VALUE. Companies pay $1000s for this data.
"""

import httpx
import re
from typing import Dict
from bs4 import BeautifulSoup


# ============================================
# TECHNOLOGY SIGNATURES DATABASE
# Each tech has patterns found in HTML/headers/JS
# ============================================

TECH_DB = {
    # === CMS PLATFORMS ===
    "WordPress": {
        "patterns": ["wp-content", "wp-includes", "wp-json", "wordpress", "/wp-admin"],
        "meta": ["generator=WordPress"],
        "headers": [],
        "category": "CMS",
        "icon": "📝",
    },
    "Shopify": {
        "patterns": ["cdn.shopify.com", "shopify.com", "Shopify.theme", "shopify-section"],
        "meta": ["generator=Shopify"],
        "headers": ["x-shopid"],
        "category": "E-Commerce",
        "icon": "🛒",
    },
    "Squarespace": {
        "patterns": ["squarespace", "cdn.squarespace.net", "static1.squarespace"],
        "meta": ["generator=Squarespace"],
        "headers": [],
        "category": "CMS",
        "icon": "⬛",
    },
    "Wix": {
        "patterns": ["wix.com", "wixpress", "wixcdn", "wix-dynamic-pages"],
        "meta": ["generator=Wix"],
        "headers": ["x-wix-request-id"],
        "category": "CMS",
        "icon": "🔷",
    },
    "Ghost": {
        "patterns": ["ghost.org", "ghost-content", "ghost-"],
        "meta": ["generator=Ghost"],
        "headers": ["x-ghost"],
        "category": "CMS",
        "icon": "👻",
    },
    "Webflow": {
        "patterns": ["webflow.com", "webflow.io", "wf-module"],
        "meta": ["generator=Webflow"],
        "headers": [],
        "category": "CMS",
        "icon": "🌊",
    },
    "Joomla": {
        "patterns": ["joomla", "/media/jui", "content component"],
        "meta": ["generator=Joomla"],
        "headers": [],
        "category": "CMS",
        "icon": "🟡",
    },
    "Drupal": {
        "patterns": ["drupal", "sites/all", "sites/default", "Drupal.settings"],
        "meta": ["generator=Drupal", "X-Drupal-Cache"],
        "headers": ["x-drupal-cache"],
        "category": "CMS",
        "icon": "🔵",
    },
    
    # === FRONTEND FRAMEWORKS ===
    "React": {
        "patterns": ["react", "react-dom", "__reactInternalInstance", "reactjs"],
        "meta": [],
        "headers": [],
        "category": "Frontend",
        "icon": "⚛️",
    },
    "Next.js": {
        "patterns": ["_next/static", "_next/image", "next.js", "nextjs", "__NEXT_DATA__"],
        "meta": ["generator=Next.js"],
        "headers": ["x-nextjs-cache"],
        "category": "Frontend",
        "icon": "▲",
    },
    "Vue.js": {
        "patterns": ["vue", "vuejs", "v-app", "v-model", "vue-router", "Vue"],
        "meta": [],
        "headers": [],
        "category": "Frontend",
        "icon": "💚",
    },
    "Nuxt.js": {
        "patterns": ["nuxt", "__nuxt", "nuxtjs", "/_nuxt/"],
        "meta": ["generator=Nuxt"],
        "headers": ["x-nuxt-rendered"],
        "category": "Frontend",
        "icon": "💚",
    },
    "Angular": {
        "patterns": ["ng-app", "ng-controller", "angular", "ng-version", "Angular"],
        "meta": [],
        "headers": ["x-powered-by=Angular"],
        "category": "Frontend",
        "icon": "🅰️",
    },
    "Svelte": {
        "patterns": ["svelte", "sveltekit", "__svelte"],
        "meta": [],
        "headers": [],
        "category": "Frontend",
        "icon": "🔥",
    },
    "Gatsby": {
        "patterns": ["gatsby", "gatsbyjs", "/gatsby/"],
        "meta": ["generator=Gatsby"],
        "headers": [],
        "category": "Frontend",
        "icon": "💜",
    },
    "Tailwind CSS": {
        "patterns": ["tailwind", "tailwindcss"],
        "meta": [],
        "headers": [],
        "category": "CSS Framework",
        "icon": "🎨",
    },
    "Bootstrap": {
        "patterns": ["bootstrap", "bootstrap.min.css", "bootstrap.min.js"],
        "meta": [],
        "headers": [],
        "category": "CSS Framework",
        "icon": "🅱️",
    },
    
    # === BACKEND / SERVER ===
    "Express.js": {
        "patterns": ["express", "expressjs"],
        "meta": [],
        "headers": ["x-powered-by=Express"],
        "category": "Backend",
        "icon": "🚂",
    },
    "Django": {
        "patterns": ["csrfmiddlewaretoken", "django", "Django"],
        "meta": [],
        "headers": [],
        "category": "Backend",
        "icon": "🐍",
    },
    "Laravel": {
        "patterns": ["laravel", "csrf-token", "Laravel"],
        "meta": [],
        "headers": [],
        "category": "Backend",
        "icon": "🔴",
    },
    "FastAPI": {
        "patterns": ["fastapi", "FastAPI"],
        "meta": [],
        "headers": [],
        "category": "Backend",
        "icon": "⚡",
    },
    "Ruby on Rails": {
        "patterns": ["rails", "csrf-param=authenticity_token", "Rails"],
        "meta": [],
        "headers": ["x-powered-by=Phusion", "x-request-id"],
        "category": "Backend",
        "icon": "💎",
    },
    "Spring Boot": {
        "patterns": ["spring", "Spring Boot"],
        "meta": [],
        "headers": ["x-application-context"],
        "category": "Backend",
        "icon": "🍃",
    },
    "Flask": {
        "patterns": ["flask", "Flask"],
        "meta": [],
        "headers": [],
        "category": "Backend",
        "icon": "🧪",
    },
    
    # === ANALYTICS ===
    "Google Analytics": {
        "patterns": ["google-analytics.com", "GoogleAnalytics", "gtag(", "ga(", "_gaq"],
        "meta": [],
        "headers": [],
        "category": "Analytics",
        "icon": "📊",
    },
    "Google Analytics 4": {
        "patterns": ["gtag(", "G-", "GA-"],
        "meta": [],
        "headers": [],
        "category": "Analytics",
        "icon": "📊",
    },
    "Mixpanel": {
        "patterns": ["mixpanel.com", "mixpanel", "mp.track"],
        "meta": [],
        "headers": [],
        "category": "Analytics",
        "icon": "📊",
    },
    "Hotjar": {
        "patterns": ["hotjar.com", "hotjar", "hjSiteSettings"],
        "meta": [],
        "headers": [],
        "category": "Analytics",
        "icon": "🔥",
    },
    "Amplitude": {
        "patterns": ["amplitude.com", "amplitude", "amplitude.logEvent"],
        "meta": [],
        "headers": [],
        "category": "Analytics",
        "icon": "📊",
    },
    "Plausible": {
        "patterns": ["plausible.io", "plausible"],
        "meta": [],
        "headers": [],
        "category": "Analytics",
        "icon": "📊",
    },
    
    # === ADVERTISING ===
    "Google Ads (AdSense)": {
        "patterns": ["adsbygoogle", "googleads", "doubleclick.net", "googlesyndication"],
        "meta": [],
        "headers": [],
        "category": "Advertising",
        "icon": "📢",
    },
    "Facebook Pixel": {
        "patterns": ["connect.facebook.net", "fbevents.js", "fbq(", "fbq('init'"],
        "meta": [],
        "headers": [],
        "category": "Advertising",
        "icon": "📢",
    },
    "Taboola": {
        "patterns": ["taboola.com", "taboola", "TRC"],
        "meta": [],
        "headers": [],
        "category": "Advertising",
        "icon": "📢",
    },
    "Outbrain": {
        "patterns": ["outbrain.com", "outbrain", "OB_amp"],
        "meta": [],
        "headers": [],
        "category": "Advertising",
        "icon": "📢",
    },
    
    # === PAYMENT ===
    "Stripe": {
        "patterns": ["stripe.com", "stripe.js", "Stripe(", "stripe_checkout"],
        "meta": [],
        "headers": [],
        "category": "Payment",
        "icon": "💳",
    },
    "PayPal": {
        "patterns": ["paypal.com", "paypalobjects.com", "PayPal", "paypal-button"],
        "meta": [],
        "headers": [],
        "category": "Payment",
        "icon": "💰",
    },
    "Square": {
        "patterns": ["squareup.com", "square", "sq-payment-form"],
        "meta": [],
        "headers": [],
        "category": "Payment",
        "icon": "⬛",
    },
    "Braintree": {
        "patterns": ["braintreegateway.com", "braintree"],
        "meta": [],
        "headers": [],
        "category": "Payment",
        "icon": "💳",
    },
    
    # === CDN / HOSTING ===
    "Cloudflare": {
        "patterns": ["cloudflare", "cf-beacon"],
        "meta": [],
        "headers": ["cf-ray", "cf-cache-status", "server=cloudflare"],
        "category": "CDN & Security",
        "icon": "☁️",
    },
    "AWS (Amazon)": {
        "patterns": ["amazonaws.com", "aws", "cloudfront.net"],
        "meta": [],
        "headers": ["x-amz-request-id", "x-amz-cf-id"],
        "category": "Hosting",
        "icon": "☁️",
    },
    "Vercel": {
        "patterns": ["_next/static", "vercel-insights", "vercel"],
        "meta": [],
        "headers": ["x-vercel-id", "x-vercel-cache", "server=Vercel"],
        "category": "Hosting",
        "icon": "▲",
    },
    "Netlify": {
        "patterns": ["netlify", "netlify-cms"],
        "meta": ["generator=Netlify"],
        "headers": ["x-nf-request-id", "server=Netlify"],
        "category": "Hosting",
        "icon": "🌐",
    },
    "GitHub Pages": {
        "patterns": ["github.io", "githubpages"],
        "meta": [],
        "headers": ["server=GitHub.com"],
        "category": "Hosting",
        "icon": "🐙",
    },
    
    # === EMAIL MARKETING ===
    "Mailchimp": {
        "patterns": ["mailchimp.com", "mcjs", "mailchimp", "mc-submit"],
        "meta": [],
        "headers": [],
        "category": "Email Marketing",
        "icon": "📧",
    },
    "HubSpot": {
        "patterns": ["hubspot.com", "hs-analytics", "hubspot", "_hsq", "hsForms"],
        "meta": [],
        "headers": [],
        "category": "Marketing & CRM",
        "icon": "🟠",
    },
    "ConvertKit": {
        "patterns": ["convertkit.com", "convertkit", "ck-form"],
        "meta": [],
        "headers": [],
        "category": "Email Marketing",
        "icon": "📧",
    },
    "Klaviyo": {
        "patterns": ["klaviyo.com", "klaviyo", "klaviyo_forms"],
        "meta": [],
        "headers": [],
        "category": "Email Marketing",
        "icon": "📧",
    },
    
    # === CUSTOMER SUPPORT ===
    "Intercom": {
        "patterns": ["intercom.io", "intercom", "Intercom(", "IntercomMessenger"],
        "meta": [],
        "headers": [],
        "category": "Customer Support",
        "icon": "💬",
    },
    "Zendesk": {
        "patterns": ["zendesk.com", "zendesk", "zd-widget"],
        "meta": [],
        "headers": [],
        "category": "Customer Support",
        "icon": "💬",
    },
    "Freshdesk": {
        "patterns": ["freshdesk.com", "freshdesk"],
        "meta": [],
        "headers": [],
        "category": "Customer Support",
        "icon": "💬",
    },
    "LiveChat": {
        "patterns": ["livechatinc.com", "livechat", "LiveChat"],
        "meta": [],
        "headers": [],
        "category": "Customer Support",
        "icon": "💬",
    },
    "Crisp": {
        "patterns": ["crisp.chat", "crisp", "Crisp"],
        "meta": [],
        "headers": [],
        "category": "Customer Support",
        "icon": "💬",
    },
    
    # === CHATBOTS / AI ===
    "ChatGPT/OpenAI": {
        "patterns": ["openai", "chatgpt", "gpt"],
        "meta": [],
        "headers": [],
        "category": "AI/Chatbot",
        "icon": "🤖",
    },
    "Drift": {
        "patterns": ["drift.com", "drift", "Drift"],
        "meta": [],
        "headers": [],
        "category": "AI/Chatbot",
        "icon": "🤖",
    },
    
    # === SECURITY ===
    "reCAPTCHA": {
        "patterns": ["recaptcha", "google.com/recaptcha", "g-recaptcha"],
        "meta": [],
        "headers": [],
        "category": "Security",
        "icon": "🔒",
    },
    "Cloudflare Turnstile": {
        "patterns": ["challenges.cloudflare.com", "turnstile", "cf-turnstile"],
        "meta": [],
        "headers": [],
        "category": "Security",
        "icon": "🔒",
    },
    "hCaptcha": {
        "patterns": ["hcaptcha.com", "hcaptcha", "h-captcha"],
        "meta": [],
        "headers": [],
        "category": "Security",
        "icon": "🔒",
    },
    
    # === SEO ===
    "Yoast SEO": {
        "patterns": ["yoast", "yoast-seo", "yoast-schema"],
        "meta": [],
        "headers": [],
        "category": "SEO",
        "icon": "🔍",
    },
    "All in One SEO": {
        "patterns": ["All in One SEO", "aioseo"],
        "meta": [],
        "headers": [],
        "category": "SEO",
        "icon": "🔍",
    },
    
    # === FONTS ===
    "Google Fonts": {
        "patterns": ["fonts.googleapis.com", "fonts.gstatic.com"],
        "meta": [],
        "headers": [],
        "category": "Fonts",
        "icon": "🔤",
    },
    "Font Awesome": {
        "patterns": ["fontawesome", "font-awesome", "fontawesome.com"],
        "meta": [],
        "headers": [],
        "category": "Fonts",
        "icon": "🔤",
    },
    "Typekit/Adobe Fonts": {
        "patterns": ["typekit.net", "use.typekit.net", "adobe fonts"],
        "meta": [],
        "headers": [],
        "category": "Fonts",
        "icon": "🔤",
    },
    
    # === VIDEO ===
    "YouTube": {
        "patterns": ["youtube.com", "youtube-nocookie.com", "youtu.be"],
        "meta": [],
        "headers": [],
        "category": "Video",
        "icon": "🎬",
    },
    "Vimeo": {
        "patterns": ["vimeo.com", "player.vimeo.com", "Vimeo"],
        "meta": [],
        "headers": [],
        "category": "Video",
        "icon": "🎬",
    },
    "Loom": {
        "patterns": ["loom.com", "loom", "Loom"],
        "meta": [],
        "headers": [],
        "category": "Video",
        "icon": "🎬",
    },
    
    # === MAPS ===
    "Google Maps": {
        "patterns": ["maps.googleapis.com", "maps.google.com", "google.maps"],
        "meta": [],
        "headers": [],
        "category": "Maps",
        "icon": "📍",
    },
    "Mapbox": {
        "patterns": ["mapbox.com", "mapbox", "Mapbox"],
        "meta": [],
        "headers": [],
        "category": "Maps",
        "icon": "📍",
    },
    
    # === AUTH ===
    "Auth0": {
        "patterns": ["auth0.com", "auth0", "Auth0"],
        "meta": [],
        "headers": [],
        "category": "Authentication",
        "icon": "🔑",
    },
    "Firebase Auth": {
        "patterns": ["firebase", "firebaseapp.com", "firebase.google.com"],
        "meta": [],
        "headers": [],
        "category": "Authentication",
        "icon": "🔥",
    },
    "Clerk": {
        "patterns": ["clerk.com", "clerk", "Clerk"],
        "meta": [],
        "headers": [],
        "category": "Authentication",
        "icon": "🔑",
    },
    
    # === A/B TESTING ===
    "Optimizely": {
        "patterns": ["optimizely.com", "optimizely", "optimizely.push"],
        "meta": [],
        "headers": [],
        "category": "A/B Testing",
        "icon": "🧪",
    },
    "VWO": {
        "patterns": ["vwo.com", "vwo", "_vis_opt_queue"],
        "meta": [],
        "headers": [],
        "category": "A/B Testing",
        "icon": "🧪",
    },
    
    # === MONITORING ===
    "Sentry": {
        "patterns": ["sentry.io", "sentry", "Sentry.init"],
        "meta": [],
        "headers": ["sentry-trace"],
        "category": "Monitoring",
        "icon": "👀",
    },
    "New Relic": {
        "patterns": ["newrelic.com", "newrelic", "NREUM"],
        "meta": [],
        "headers": ["x-newrelic-id"],
        "category": "Monitoring",
        "icon": "👀",
    },
    "Datadog": {
        "patterns": ["datadoghq.com", "datadog", "DD_RUM"],
        "meta": [],
        "headers": ["x-datadog-trace-id"],
        "category": "Monitoring",
        "icon": "👀",
    },
}


async def detect_technologies(url: str) -> Dict:
    """
    Detect ALL technologies from any website.
    Returns detailed report with categories, confidence scores, sophistication score.
    """
    
    result = {
        "technologies": [],
        "categories": {},
        "tech_count": 0,
        "modern_score": 0,
        "sophistication_level": "",
        "top_technologies": [],
        "insights": [],
    }
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        response = httpx.get(
            f"https://{url}", 
            headers=headers, 
            timeout=20, 
            follow_redirects=True
        )
        
        html = response.text
        response_headers = {k.lower(): v.lower() for k, v in response.headers.items()}
        soup = BeautifulSoup(html, "html.parser")
        
        # Collect all searchable text
        all_html = html.lower()
        all_scripts = " ".join([
            s.get("src", "").lower() + " " + (s.string or "").lower() 
            for s in soup.find_all("script")
        ])
        all_links = " ".join([
            l.get("href", "").lower() 
            for l in soup.find_all("link")
        ])
        meta_generator = ""
        gen_tag = soup.find("meta", attrs={"name": "generator"})
        if gen_tag and gen_tag.get("content"):
            meta_generator = gen_tag["content"].lower()
        
        combined = all_html + " " + all_scripts + " " + all_links + " " + meta_generator
        
        # === DETECT EACH TECHNOLOGY ===
        detected = []
        
        for tech_name, sigs in TECH_DB.items():
            confidence = 0
            match_type = ""
            
            # Check patterns in HTML/scripts/links
            for pattern in sigs.get("patterns", []):
                if pattern.lower() in combined:
                    confidence += 40
                    match_type = "pattern_match"
                    break
            
            # Check meta generator
            for meta_pattern in sigs.get("meta", []):
                if meta_pattern.lower() in meta_generator:
                    confidence += 70
                    match_type = "meta_generator"
                    break
            
            # Check response headers
            for header_pattern in sigs.get("headers", []):
                header_lower = header_pattern.lower()
                for h_key, h_value in response_headers.items():
                    if header_lower in h_value or header_lower in h_key:
                        confidence += 60
                        match_type = "response_header"
                        break
            
            # Only include if confident enough
            if confidence >= 30:
                detected.append({
                    "name": tech_name,
                    "category": sigs["category"],
                    "icon": sigs["icon"],
                    "confidence": min(confidence, 100),
                    "match_type": match_type,
                })
        
        # Sort by confidence
        detected.sort(key=lambda x: x["confidence"], reverse=True)
        
        # === GROUP BY CATEGORY ===
        categories = {}
        for tech in detected:
            cat = tech["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append({
                "name": tech["name"],
                "icon": tech["icon"],
                "confidence": tech["confidence"]
            })
        
        # === CALCULATE SCORES ===
        # Modern tech = higher score
        modern_techs = ["React", "Next.js", "Vue.js", "Nuxt.js", "Svelte", 
                       "Stripe", "Cloudflare", "Vercel", "Netlify", "HubSpot",
                       "Mixpanel", "Amplitude", "Sentry", "Auth0", "Clerk",
                       "Tailwind CSS", "Svelte"]
        
        modern_count = sum(1 for t in detected if t["name"] in modern_techs)
        modern_score = min(100, len(detected) * 3 + modern_count * 15)
        
        if modern_score >= 80:
            sophistication = "Highly Modern & Sophisticated"
        elif modern_score >= 60:
            sophistication = "Moderately Modern"
        elif modern_score >= 40:
            sophistication = "Mixed Legacy & Modern"
        else:
            sophistication = "Legacy / Basic"
        
        # === GENERATE INSIGHTS ===
        insights = []
        
        if categories.get("E-Commerce"):
            insights.append("🛒 E-commerce platform detected — likely sells products online")
        if categories.get("Analytics"):
            insights.append("📊 Multiple analytics tools — data-driven decision making")
        if categories.get("Advertising"):
            insights.append("📢 Advertising platforms found — monetizes through ads")
        if categories.get("Payment"):
            insights.append("💳 Payment processor detected — handles online transactions")
        if categories.get("Marketing & CRM") or categories.get("Email Marketing"):
            insights.append("📧 Marketing automation tools — active lead generation")
        if categories.get("Customer Support"):
            insights.append("💬 Customer support tools — invests in user experience")
        if categories.get("CDN & Security"):
            insights.append("☁️ CDN/security layer — cares about performance & protection")
        if categories.get("A/B Testing"):
            insights.append("🧪 A/B testing tools — optimizes conversions scientifically")
        if categories.get("AI/Chatbot"):
            insights.append("🤖 AI/chatbot present — uses automation for engagement")
        if categories.get("Authentication"):
            insights.append("🔑 Modern auth system — enterprise-grade security")
        
        if not insights:
            insights.append("ℹ️ Basic technology stack — potential for modernization")
        
        # === BUILD RESULT ===
        result["technologies"] = detected
        result["categories"] = categories
        result["tech_count"] = len(detected)
        result["modern_score"] = modern_score
        result["sophistication_level"] = sophistication
        result["top_technologies"] = [t["name"] for t in detected[:5]]
        result["insights"] = insights
        
    except httpx.TimeoutException:
        result["error"] = "Website took too long to respond (timeout after 20s)"
    except httpx.ConnectError:
        result["error"] = "Could not connect to website. It may be down or blocking requests."
    except Exception as e:
        result["error"] = f"Error scanning: {str(e)}"
    
    return result