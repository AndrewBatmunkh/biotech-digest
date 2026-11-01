# emailer.py — digest email sender for Biotech Digest
# Fetches top articles, builds a clean HTML email, sends via Gmail SMTP
# Run directly: python3 emailer.py
# Or triggered from the sidebar button in app.py

import smtplib
import datetime
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from groq import Groq

from config import (
    EMAIL_ENABLED, EMAIL_FROM, EMAIL_PASSWORD,
    SMTP_HOST, SMTP_PORT, TOPICS, TOP_N_FOR_DIGEST,
    APP_URL,  # Change 1 / Change 5: app URL that article links point to, defined in config.py
    GROQ_API_KEY,
)
from database import get_all_users, get_profile
from fetcher import fetch_all_articles
from summarizer import summarize_article

client = Groq(api_key=GROQ_API_KEY, timeout=30.0)  # fail fast instead of hanging forever on a stuck request

EMAIL_PROMPT = """
You are writing a biotech email digest. Be punchy and scannable.

Given this article, respond ONLY with JSON — no markdown, no code fences:
{{
    "headline": "DRUG/TOPIC NAME — Company: one sentence what happened",
    "bullets": [
        "→ specific fact or number",
        "→ specific fact or number",
        "→ specific fact or number",
        "→ specific fact or number",
        "→ specific fact or number"
    ]
}}

Rules:
- Always include numbers, percentages, dollar amounts
- Each bullet is one specific fact
- Under 80 words total
- If {companies} or {keywords} appear add FLAG: at start of that bullet

Article title: {title}
Article text: {excerpt}
"""

# ─────────────────────────────────────────────
# MAPPINGS — mirrors app.py exactly
# ─────────────────────────────────────────────

_FOCUS_TO_TOPICS = {
    "Gene & Cell Therapy": ["CRISPR", "Gene Therapy", "RNA / mRNA", "Cell Therapy", "Antibody"],
    "Oncology":            ["Cancer"],
    "Emerging Biology":    ["Genomics"],
    "Rare & Neurological": ["Rare Disease", "Neuroscience"],
    "Digital & Precision": ["AI & Drug Discovery", "Diagnostics"],
    "Business & Industry": ["Drug Development", "FDA / Regulatory", "Acquisitions", "Funding"],
}

_FOCUS_AREA_COLORS = {
    "Gene & Cell Therapy": "#4A90D9",
    "Oncology":            "#D95C5C",
    "Emerging Biology":    "#2EAA72",
    "Rare & Neurological": "#8B5CF6",
    "Digital & Precision": "#06B6D4",
    "Business & Industry": "#E8A020",
}

# ─────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────

def _tag_article(article):
    """Match article to topic tags using keyword search — same logic as app.py."""
    searchable = (article["title"] + " " + article["raw_summary"]).lower()
    matched = []
    for topic, keywords in TOPICS.items():
        if topic == "All":
            continue
        if any(kw in searchable for kw in keywords):
            matched.append(topic)
    return matched if matched else ["Other"]


def _score_article(article, profile=None):
    """Score article by relevance — same logic as app.py."""
    summary = article.get("ai_summary", {})
    if "error" in summary:
        return 0
    score = 0

    # results with actual numbers are more useful than vague summaries
    if any(ch.isdigit() for ch in summary.get("results", "").lower()):
        score += 3

    # full text means the AI had more to work with
    if article.get("full_text"):
        score += 1

    # recency — fresh news floats up
    published = article.get("published")
    if published:
        age_hours = (datetime.datetime.now() - published).total_seconds() / 3600
        if age_hours < 24:
            score += 3
        elif age_hours < 48:
            score += 2
        elif age_hours < 72:
            score += 1

    # profile match bonuses
    if profile:
        searchable = (article.get("title", "") + " " + article.get("raw_summary", "")).lower()

        companies = [c.strip().lower() for c in profile.get("companies", "").split(",") if c.strip()]
        if any(c in searchable for c in companies):
            score += 4

        keywords = [k.strip().lower() for k in profile.get("keywords", "").split(",") if k.strip()]
        score += min(sum(1 for kw in keywords if kw in searchable) * 2, 4)

        article_tags = set(article.get("topic_tags", []))
        for focus in profile.get("focus_areas", []):
            label = focus.split("—")[0].strip()
            if any(t in article_tags for t in _FOCUS_TO_TOPICS.get(label, [])):
                score += 1

    return score


def _article_color(article):
    """Return the hex colour for this article based on its first matching focus area."""
    tags = set(article.get("topic_tags", []))
    for fa, topics in _FOCUS_TO_TOPICS.items():
        if any(t in tags for t in topics):
            return _FOCUS_AREA_COLORS[fa]
    return "#888888"


def _get_email_summary(article, profile=None):
    """Calls Groq for a punchy headline + fact bullets tailored for the email digest."""
    excerpt = article.get("ai_summary", {}).get("technology") or article.get("raw_summary", "")
    companies = (profile.get("companies", "") if profile else "") or "none specified"
    keywords  = (profile.get("keywords", "") if profile else "") or "none specified"

    prompt = EMAIL_PROMPT.format(
        title=article.get("title", ""),
        excerpt=excerpt or "no excerpt available",
        companies=companies,
        keywords=keywords,
    )
    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
        )
        raw_text = response.choices[0].message.content.strip()
        start = raw_text.find("{")
        end   = raw_text.rfind("}") + 1
        if start == -1 or end == 0:
            return {"error": "Groq returned no JSON"}
        return json.loads(raw_text[start:end])

    except json.JSONDecodeError as e:
        return {"error": f"Groq returned invalid JSON: {e}"}

    except Exception as e:  # any other error — bad API key, rate limit, network issue etc
        return {"error": f"API call failed: {e}"}


# ─────────────────────────────────────────────
# MAIN FUNCTIONS
# ─────────────────────────────────────────────

def get_top_articles(user, n=TOP_N_FOR_DIGEST):
    """
    Loads this user's profile, fetches all articles, summarises them with AI,
    tags and scores each one, filters to this user's chosen focus areas,
    and returns the top N articles by relevance score.
    """
    profile = get_profile(user["id"])
    focus_areas = profile.get("focus_areas", []) if profile else []

    print(f"Fetching articles for {user['full_name']}...")
    articles = fetch_all_articles()
    print(f"✅ Fetched {len(articles)} articles")

    # summarise each article with the user's profile for personalisation
    print("Summarising with AI...")
    for i, article in enumerate(articles):
        print(f"  {i+1}/{len(articles)}: {article['title'][:60]}...")
        article["ai_summary"] = summarize_article(
            article["title"],
            article["raw_summary"],
            article.get("full_text", ""),
            profile=profile,
        )

    # tag each article with matching topic labels
    for article in articles:
        article["topic_tags"] = _tag_article(article)

    # score each article
    for article in articles:
        article["relevance_score"] = _score_article(article, profile)

    # keep only articles that match at least one of the user's focus areas
    def _matches_focus(article):
        tags = set(article.get("topic_tags", []))
        for fa in focus_areas:
            label = fa.split("—")[0].strip()
            if any(t in tags for t in _FOCUS_TO_TOPICS.get(label, [])):
                return True
        return False

    relevant = [a for a in articles if _matches_focus(a)]

    # sort by score descending, return top N
    top = sorted(relevant, key=lambda a: a["relevance_score"], reverse=True)[:n]
    print(f"✅ Selected top {len(top)} articles for digest")
    return top


def build_html_email(user, articles):
    """
    Builds the HTML email body from the user and their top articles.
    Returns (subject, html) as a tuple.
    """
    first_name = user["full_name"].split()[0]
    profile    = get_profile(user["id"])
    focus_areas = profile.get("focus_areas", []) if profile else []

    # Change 3: comma-separated list built only from the focus areas this user actually
    # picked in their profile — never the full fixed list of all possible focus areas.
    focus_labels = ", ".join(fa.split("—")[0].strip() for fa in focus_areas) or "biotech"

    # build one HTML block per article
    articles_html = ""
    for article in articles:
        color  = _article_color(article)
        title  = article.get("title", "Untitled")
        source = article.get("source", "")

        email_summary = _get_email_summary(article, profile)
        has_summary = "error" not in email_summary
        headline = email_summary.get("headline", "") if has_summary else ""
        bullets  = email_summary.get("bullets", []) if has_summary else []

        headline_html = (
            f'<p style="font-size:0.88rem;color:#777;font-style:italic;margin:0 0 12px 0;line-height:1.55">{headline}</p>'
            if headline else ""
        )
        bullets_html = "".join(
            f'<p style="margin:0 0 6px 0;font-size:0.85rem;color:#444;line-height:1.5">{bullet}</p>'
            for bullet in bullets
        )

        # title (bold caps + source), AI headline sentence, fact bullets, then a
        # section-coloured link — all inside the coloured-border card
        articles_html += f"""
        <div style="padding:18px 32px;border-left:4px solid {color};margin:4px 0">
          <h2 style="font-size:1.1rem;color:#1a1a2e;margin:0 0 6px 0;line-height:1.4;font-weight:700">{title.upper()} — {source}</h2>
          {headline_html}
          <div style="margin:0 0 12px 0">
            {bullets_html}
          </div>
          <a href="{APP_URL}" style="color:{color};font-size:0.85rem;text-decoration:none;font-weight:bold">Open in Biotech Digest →</a>
        </div>
        <div style="border-top:1px solid #f0f0f0;margin:0 32px"></div>
        """

    subject = "🧬 Your biotech week — 5 stories worth your time"

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:20px;background:#f0f2f5;font-family:Arial,Helvetica,sans-serif">
  <div style="max-width:600px;margin:0 auto;background:white;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,0.08)">

    <!-- Change 4: dark navy header with the logo and app name in white -->
    <div style="background:#0F1117;padding:24px 32px">
      <h1 style="color:white;margin:0;font-size:1.25rem;font-weight:bold">🧬 Biotech Digest</h1>
      <p style="color:rgba(255,255,255,0.6);margin:4px 0 0 0;font-size:0.82rem">AI-powered intelligence briefing</p>
    </div>

    <!-- Greeting -->
    <div style="padding:24px 32px 16px 32px">
      <p style="font-size:0.95rem;color:#333;margin:0;line-height:1.65">
        Hey <strong>{first_name}</strong>,<br><br>
        Here are this week's top picks based on your interests in
        <strong>{focus_labels}</strong>.
      </p>
    </div>

    <!-- Article cards -->
    <div style="padding:8px 0 16px 0">
      {articles_html}
    </div>

    <!-- Change 4: updated footer copy -->
    <div style="padding:20px 32px;background:#f8f8f8;border-top:1px solid #eee">
      <p style="color:#bbb;font-size:0.75rem;margin:0;line-height:1.6">
        Sent by Biotech Digest · To update your preferences open the app
      </p>
    </div>

  </div>
</body>
</html>"""

    return subject, html


def send_digest_email(user, articles=None):
    """
    Orchestrates the full send flow for one user — fetches their top articles
    if not provided, builds the HTML email, and sends it to their own email
    via Gmail SMTP. Returns True on success, False on failure.
    """
    if not EMAIL_ENABLED:
        print("❌ Email is disabled. Set EMAIL_ENABLED = True in config.py")
        return False

    if not all([EMAIL_FROM, EMAIL_PASSWORD]):
        print("❌ Email credentials missing. Set EMAIL_FROM, EMAIL_PASSWORD in .env")
        return False

    if not user.get("email"):
        print(f"❌ User {user.get('full_name', user.get('id'))} has no email on file.")
        return False

    # fetch top articles if caller didn't pass them in
    if articles is None:
        articles = get_top_articles(user)

    if not articles:
        print(f"❌ No articles to send for {user['full_name']}.")
        return False

    subject, html_body = build_html_email(user, articles)

    # compose MIME message — "alternative" means it gracefully falls back if HTML fails
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_FROM
    msg["To"]      = user["email"]
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()                         # upgrade to encrypted connection
            server.login(EMAIL_FROM, EMAIL_PASSWORD)  # authenticate with Gmail App Password
            server.sendmail(EMAIL_FROM, user["email"], msg.as_string())
        print(f"✅ Digest sent to {user['email']}")
        return True

    except smtplib.SMTPAuthenticationError:
        print("❌ Gmail auth failed — use an App Password, not your real password.")
        print("   Create one at: myaccount.google.com/apppasswords")
        return False

    except Exception as e:
        print(f"❌ Failed to send to {user['email']}: {e}")
        return False


def send_all_digests():
    """
    Sends every signed-up user their own personalised digest — skips anyone
    who chose "Off" for digest frequency during onboarding. This is what the
    Monday GitHub Actions job calls so each person gets mailed separately.
    """
    users = get_all_users()
    if not users:
        print("❌ No users found in database.")
        return

    sent, skipped, failed = 0, 0, 0
    for user in users:
        try:
            profile = get_profile(user["id"])
            frequency = profile.get("digest_frequency") if profile else None
            if frequency == "Off":
                print(f"⏭️  Skipping {user['full_name']} — digest turned off.")
                skipped += 1
                continue

            print(f"Building digest for {user['full_name']} ({user['email']})...")
            if send_digest_email(user):
                sent += 1
            else:
                failed += 1

        except Exception as e:
            # one broken user (bad DB row, unexpected error) must not stop
            # everyone else in the batch from getting their digest
            print(f"❌ Unexpected error for {user.get('full_name', user.get('id'))}: {e}")
            failed += 1

    print(f"\n✅ Sent {sent} · ⏭️ Skipped {skipped} · ❌ Failed {failed}")


# ─────────────────────────────────────────────
# TEST BLOCK — python3 emailer.py
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("Sending digests to all users...")
    send_all_digests()
