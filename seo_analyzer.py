"""
seo_analyzer.py — Complete SEO analysis engine
Businesses pay $2000+/month for this data elsewhere
"""

import httpx
import re
from bs4 import BeautifulSoup
from typing import Dict
from urllib.parse import urlparse


async def analyze_seo(url: str) -> Dict:
    """Full SEO audit — score, issues, recommendations, traffic estimate"""
    
    result = {
        "score": 0,
        "grade": "",
        "critical_issues": [],
        "warnings": [],
        "good_points": [],
        "recommendations": [],
        "details": {},
        "estimated_traffic_value": "",
        "competitive_level": "",
    }
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        response = httpx.get(f"https://{url}", headers=headers, timeout=15, follow_redirects=True)
        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        
        score = 100  # Start at 100, subtract for issues
        details = {}
        
        # =====================
        # 1. TITLE TAG
        # =====================
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            title_text = title_tag.string.strip()
            details["title"] = title_text
            details["title_length"] = len(title_text)
            
            if len(title_text) == 0:
                score -= 20
                result["critical_issues"].append("❌ Empty title tag")
            elif len(title_text) < 30:
                score -= 10
                result["warnings"].append("⚠️ Title too short (under 30 chars): '{title_text}'")
            elif len(title_text) > 65:
                score -= 5
                result["warnings"].append(f"⚠️ Title too long ({len(title_text)} chars). Google cuts at ~60.")
            else:
                result["good_points"].append(f"✅ Title optimal ({len(title_text)} chars): '{title_text[:60]}'")
        else:
            score -= 25
            result["critical_issues"].append("❌ NO TITLE TAG — This is a major SEO problem!")
            details["title"] = None
        
        # =====================
        # 2. META DESCRIPTION
        # =====================
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            desc = meta_desc["content"].strip()
            details["meta_description"] = desc
            details["meta_description_length"] = len(desc)
            
            if len(desc) < 100:
                score -= 10
                result["warnings"].append(f"⚠️ Meta description too short ({len(desc)} chars)")
            elif len(desc) > 170:
                score -= 5
                result["warnings"].append(f"⚠️ Meta description too long ({len(desc)} chars)")
            else:
                result["good_points"].append(f"✅ Meta description optimal ({len(desc)} chars)")
        else:
            score -= 15
            result["critical_issues"].append("❌ NO META DESCRIPTION — Google will guess what to show!")
            details["meta_description"] = None
        
        # =====================
        # 3. H1 TAG
        # =====================
        h1_list = soup.find_all("h1")
        details["h1_count"] = len(h1_list)
        
        if len(h1_list) == 0:
            score -= 15
            result["critical_issues"].append("❌ NO H1 TAG — Most important heading missing!")
        elif len(h1_list) > 1:
            score -= 5
            h1_texts = [h.get_text().strip() for h in h1_list]
            details["h1_texts"] = h1_texts
            result["warnings"].append(f"⚠️ Multiple H1 tags ({len(h1_list)} found). Should have exactly 1.")
        else:
            h1_text = h1_list[0].get_text().strip()
            details["h1_text"] = h1_text
            result["good_points"].append(f"✅ Single H1 tag: '{h1_text[:50]}'")
        
        # =====================
        # 4. HTTPS
        # =====================
        is_https = url.startswith("https") or str(response.url).startswith("https")
        details["uses_https"] = is_https
        
        if is_https:
            result["good_points"].append("✅ HTTPS enabled — secure and Google-approved")
        else:
            score -= 20
            result["critical_issues"].append("❌ NOT USING HTTPS — Google penalizes non-secure sites!")
        
        # =====================
        # 5. IMAGES & ALT TAGS
        # =====================
        all_images = soup.find_all("img")
        total_images = len(all_images)
        images_with_alt = [img for img in all_images if img.get("alt")]
        images_without_alt = total_images - len(images_with_alt)
        
        details["total_images"] = total_images
        details["images_with_alt"] = len(images_with_alt)
        details["images_without_alt"] = images_without_alt
        
        if total_images == 0:
            result["warnings"].append("⚠️ No images found on page")
        elif images_without_alt == 0:
            result["good_points"].append(f"✅ All {total_images} images have alt tags")
        elif images_without_alt > total_images * 0.5:
            score -= 10
            result["critical_issues"].append(f"❌ {images_without_alt}/{total_images} images missing alt tags (>50%)")
        else:
            score -= 5
            result["warnings"].append(f"⚠️ {images_without_alt}/{total_images} images missing alt tags")
        
        # =====================
        # 6. PAGE SPEED (approximate)
        # =====================
        load_time = response.elapsed.total_seconds()
        page_size_kb = len(html) / 1024
        
        details["load_time_seconds"] = round(load_time, 2)
        details["page_size_kb"] = round(page_size_kb, 1)
        
        if load_time > 5:
            score -= 15
            result["critical_issues"].append(f"❌ Very slow ({load_time:.1f}s). Google ranks fast sites higher.")
        elif load_time > 3:
            score -= 10
            result["warnings"].append(f"⚠️ Slow load time ({load_time:.1f}s). Aim for under 2s.")
        elif load_time > 1.5:
            score -= 3
            result["warnings"].append(f"⚠️ Acceptable speed ({load_time:.1f}s). Could be faster.")
        else:
            result["good_points"].append(f"✅ Fast load time ({load_time:.1f}s)")
        
        if page_size_kb > 1000:
            score -= 10
            result["warnings"].append(f"⚠️ Page very large ({page_size_kb:.0f} KB). Slow on mobile.")
        elif page_size_kb > 300:
            result["warnings"].append(f"⚠️ Page moderately large ({page_size_kb:.0f} KB)")
        else:
            result["good_points"].append(f"✅ Page size reasonable ({page_size_kb:.0f} KB)")
        
        # =====================
        # 7. MOBILE FRIENDLINESS
        # =====================
        viewport = soup.find("meta", attrs={"name": "viewport"})
        details["has_viewport"] = viewport is not None
        
        if viewport:
            result["good_points"].append("✅ Mobile viewport meta tag present")
        else:
            score -= 15
            result["critical_issues"].append("❌ NO VIEWPORT TAG — Site won't display correctly on mobile!")
        
        # =====================
        # 8. CANONICAL URL
        # =====================
        canonical = soup.find("link", attrs={"rel": "canonical"})
        if canonical:
            details["canonical_url"] = canonical.get("href")
            result["good_points"].append("✅ Canonical URL set (prevents duplicate content issues)")
        else:
            score -= 3
            result["warnings"].append("⚠️ No canonical URL — risk of duplicate content")
        
        # =====================
        # 9. OPEN GRAPH (Social Sharing)
        # =====================
        og_title = soup.find("meta", attrs={"property": "og:title"})
        og_desc = soup.find("meta", attrs={"property": "og:description"})
        og_image = soup.find("meta", attrs={"property": "og:image"})
        
        og_count = sum([1 for tag in [og_title, og_desc, og_image] if tag])
        details["og_tags_count"] = og_count
        
        if og_count >= 3:
            result["good_points"].append(f"✅ Full Open Graph tags ({og_count}) — great social sharing")
        elif og_count >= 1:
            result["warnings"].append(f"⚠️ Partial Open Graph tags ({og_count}/3) — social sharing incomplete")
        else:
            score -= 5
            result["warnings"].append("⚠️ No Open Graph tags — shares on social will look bad")
        
        # =====================
        # 10. ROBOTS.TXT
        # =====================
        try:
            robots = httpx.get(f"https://{url}/robots.txt", timeout=5, follow_redirects=True)
            details["has_robots_txt"] = robots.status_code == 200
            if robots.status_code == 200:
                result["good_points"].append("✅ robots.txt found")
            else:
                score -= 3
                result["warnings"].append("⚠️ No robots.txt — search engines may crawl everything")
        except:
            details["has_robots_txt"] = False
            result["warnings"].append("⚠️ robots.txt not accessible")
        
        # =====================
        # 11. SITEMAP.XML
        # =====================
        try:
            sitemap = httpx.get(f"https://{url}/sitemap.xml", timeout=5, follow_redirects=True)
            details["has_sitemap"] = sitemap.status_code == 200
            if sitemap.status_code == 200:
                result["good_points"].append("✅ sitemap.xml found — helps Google discover all pages")
            else:
                score -= 3
                result["warnings"].append("⚠️ No sitemap.xml — Google may miss some pages")
        except:
            details["has_sitemap"] = False
        
        # =====================
        # 12. LINKS
        # =====================
        domain = urlparse(f"https://{url}").netloc
        all_links = soup.find_all("a", href=True)
        
        internal = [l for l in all_links if domain in l["href"] or l["href"].startswith("/") or l["href"].startswith("#")]
        external = [l for l in all_links if domain not in l["href"] and not l["href"].startswith("/") and not l["href"].startswith("#")]
        
        details["internal_links"] = len(internal)
        details["external_links"] = len(external)
        details["total_links"] = len(all_links)
        
        # Broken link indicators
        no_href_links = [l for l in all_links if l["href"] == "" or l["href"] == "#"]
        details["empty_links"] = len(no_href_links)
        
        if len(internal) >= 10:
            result["good_points"].append(f"✅ Good internal linking ({len(internal)} internal links)")
        elif len(internal) >= 3:
            result["warnings"].append(f"⚠️ Few internal links ({len(internal)})")
        else:
            score -= 5
            result["warnings"].append(f"⚠️ Very few internal links ({len(internal)}) — hard for Google to navigate")
        
        # =====================
        # 13. KEYWORDS
        # =====================
        visible_text = soup.get_text(separator=" ", strip=True)
        words = re.findall(r'\b[a-zA-Z]{5,}\b', visible_text.lower())
        
        if words:
            word_freq = {}
            for w in words:
                word_freq[w] = word_freq.get(w, 0) + 1
            
            top_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:15]
            details["top_keywords"] = [
                {"word": kw, "count": cnt, "density": round(cnt / len(words) * 100, 2)} 
                for kw, cnt in top_keywords
            ]
            details["total_words"] = len(words)
        
        # =====================
        # 14. STRUCTURED DATA
        # =====================
        json_ld = soup.find_all("script", attrs={"type": "application/ld+json"})
        details["has_structured_data"] = len(json_ld) > 0
        details["structured_data_count"] = len(json_ld)
        
        if len(json_ld) > 0:
            result["good_points"].append(f"✅ Structured data found ({len(json_ld)} schema blocks) — helps Google understand content")
        else:
            score -= 5
            result["warnings"].append("⚠️ No structured data (Schema.org) — missing rich search result opportunities")
        
        # =====================
        # FINAL GRADE
        # =====================
        score = max(0, min(100, score))
        
        if score >= 90:
            grade = "A+"
            competitive_level = "Highly competitive — excellent SEO foundation"
            traffic_value = "$50K+ potential monthly organic traffic value"
        elif score >= 80:
            grade = "A"
            competitive_level = "Strong — few issues to fix"
            traffic_value = "$10K-$50K potential monthly organic traffic value"
        elif score >= 70:
            grade = "B"
            competitive_level = "Good with room for improvement"
            traffic_value = "$1K-$10K potential monthly organic traffic value"
        elif score >= 60:
            grade = "C"
            competitive_level = "Average — significant improvements needed"
            traffic_value = "$500-$1K potential monthly organic traffic value"
        elif score >= 50:
            grade = "D"
            competitive_level = "Below average — many issues to address"
            traffic_value = "$100-$500 potential monthly organic traffic value"
        else:
            grade = "F"
            competitive_level = "Poor — needs complete SEO overhaul"
            traffic_value = "$0-$100 potential monthly organic traffic value"
        
        # Generate recommendations
        recs = []
        if not details.get("title"):
            recs.append("1. Add a title tag (50-60 characters, include main keyword)")
        if not details.get("meta_description"):
            recs.append("2. Add a meta description (120-160 characters, compelling)")
        if details.get("h1_count", 0) == 0:
            recs.append("3. Add exactly ONE H1 tag with your primary keyword")
        if not details.get("uses_https"):
            recs.append("4. Enable HTTPS immediately (free with Let's Encrypt)")
        if not details.get("has_viewport"):
            recs.append("5. Add viewport meta tag for mobile responsiveness")
        if details.get("images_without_alt", 0) > 0:
            recs.append(f"6. Add alt tags to {details['images_without_alt']} images")
        if not details.get("has_structured_data"):
            recs.append("7. Add Schema.org structured data for rich search results")
        if not details.get("has_sitemap"):
            recs.append("8. Create and submit a sitemap.xml to Google")
        if load_time > 2:
            recs.append("9. Optimize page speed (compress images, minify CSS/JS, use CDN)")
        if details.get("internal_links", 0) < 5:
            recs.append("10. Add more internal links to improve navigation and SEO")
        
        if not recs:
            recs.append("SEO is strong! Focus on content quality and building backlinks next.")
        
        result["score"] = score
        result["grade"] = grade
        result["competitive_level"] = competitive_level
        result["estimated_traffic_value"] = traffic_value
        result["recommendations"] = recs
        result["details"] = details
        
    except Exception as e:
        result["score"] = 0
        result["grade"] = "N/A"
        result["error"] = str(e)
    
    return result