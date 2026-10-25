import os
import json
from dotenv import load_dotenv
from groq import Groq
import re
from fetch import get_stock_data, get_news

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "openai/gpt-oss-120b"  # open-source gpt

SYSTEM = """You are FinTruth, a sceptical stock research assistant for Indian retail investors.
Use ONLY the data and headlines provided. Never invent numbers or headlines. Write in simple plain English.
Return ONLY valid JSON:
{
  "description": "one line on what the company does",
  "company_news": [{"headline": "copied exactly from news", "sentiment": "positive|negative|neutral", "why": "one sentence on what it means for this company's investors"}],
  "financial_points": ["4 short sentences, one fact each: growth, profit, debt, returns"],
  "tip_check": {"verdict": "one sentence", "red_flags": ["..."]} or null if no tip was given,
  "conclusion": "3-4 plain sentences"
}

NEWS RULES: You get up to 15 headlines. Pick the 3 most useful for an investor: results, orders, deals, regulation, legal issues, management changes, big price moves. Skip duplicates, price pages, generic listings and opinion fluff. Return fewer than 3 if few are useful, or [] if none.

CONCLUSION RULES: Summarise everything: business quality (growth, profit, debt), the biggest risk, what the news adds, and the tip verdict if a tip was given. Do not give buy or sell advice. Do not quote a risk score number. End with one thing the investor should check next.

Ignore P/E below 3 or above 100; it is unreliable. If news mentions fraud, investigation, default or insolvency, say the financial figures may be outdated and should not be trusted.
If a number is null, skip it.
Tip red flags: urgency, guaranteed returns, unrealistic targets, insider claims, low-volume small caps, claims that conflict with the data."""

ALERT_RE = re.compile(r"\b(cbi|sebi|fraud|probe|arrest\w*|insolvency|bankruptcy|default\w*|scam|diversion|forensic|delist\w*)\b", re.I)


def news_alerts(news, name=""):
    key = name.split()[0].lower() if name else ""
    return [h for h in (news or [])
            if ALERT_RE.search(h) and (not key or key in h.lower())]

def compute_risk(d: dict, tip_check: dict | None):
    score, why = 15, []

    dte = d.get("debt_to_equity")  # ratio, after the /100 fix
    if dte is not None:
        if dte > 2: score += 20; why.append("very high debt")
        elif dte > 1: score += 10; why.append("high debt")
        elif dte > 0.5: score += 4

    ch = d.get("change_6mo_pct")
    if ch is not None:
        if ch < -30: score += 15; why.append(f"price down {abs(round(ch))}% in 6 months")
        elif ch < -15: score += 8; why.append(f"price down {abs(round(ch))}% in 6 months")
        elif ch < -5: score += 3

    pm = d.get("profit_margin")
    if pm is not None:
        if pm < 0: score += 15; why.append("the company is making a loss")
        elif pm < 0.05: score += 6; why.append("thin profit margin")

    rg = d.get("revenue_growth")
    if rg is not None:
        if rg < 0: score += 10; why.append("sales are shrinking")
        elif rg < 0.05: score += 3

    mc = d.get("market_cap")
    if mc:
        if mc >= 5e12: score -= 10
        elif mc >= 1e12: score -= 6
        elif mc < 2e10: score += 14; why.append("very small company")
        elif mc < 1e11: score += 8; why.append("small company")

    if (d.get("avg_volume") or 0) < 100000:
        score += 8; why.append("rarely traded, easy to manipulate")

    alerts = news_alerts(d.get("news"), d.get("name"))
    if alerts:
        score += min(25, 12 * len(alerts))
        why.insert(0, "serious legal or regulatory headlines")

    flags = len((tip_check or {}).get("red_flags") or [])
    if flags >= 2:
        score = max(score, 70) + 5 * flags
        why.append("the tip shows classic scam signs")
    elif flags == 1:
        score += 10
        why.append("the tip has a warning sign")

    score = max(5, min(100, score))
    reason = ("Because " + ", ".join(why[:3]) + ".").capitalize() if why \
        else "Large, profitable company with manageable debt."
    return score, reason

def industry_query(data: dict) -> str:
      try:
          r = client.chat.completions.create(
              model=MODEL,
              messages=[{"role": "user", "content":
                  f"Company: {data['name']}\nBusiness: {data.get('business')}\n"
                  "Give a 2-4 word Google News search phrase for the industry this company's "
                  "main business competes in (examples: 'wind energy India', 'private banks India'). "
                  "Reply with the phrase only."}],
              temperature=0,
          )
          return r.choices[0].message.content.strip().strip('"')[:60]
      except Exception:
          return f"{data.get('industry') or data.get('sector')} India"

def analyze(query: str, tip: str = "") -> dict:
    data = get_stock_data(query)
    if "error" in data:
        return data

    user_msg = f"STOCK DATA:\n{json.dumps(data, indent=2)}\n\nTIP TEXT:\n{tip or 'None'}"
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": user_msg}],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    result = json.loads(resp.choices[0].message.content)
    result["risk_score"], result["risk_reason"] = compute_risk(data, result.get("tip_check"))
    result["alerts"] = news_alerts(data.get("news"), data.get("name"))[:3]
    result["raw_data"] = data
    return result

if __name__ == "__main__":
    out = analyze("SUZLON", "URGENT!! Buy Suzlon today, guaranteed 3x in 2 weeks, insider info")
    print(json.dumps(out, indent=2))