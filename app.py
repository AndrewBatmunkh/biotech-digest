# app.py — the Streamlit UI
# streamlit run app.py


import streamlit as st 
import datetime 

from config import TOPICS, RSS_FEEDS, EMAIL_ENABLED
from fetcher import fetch_all_articles #downloads the RSS feeds
from summarizer import summarize_article #groq ai

# at the top of app.py add this import
from database import (
    init_db, get_user, get_user_by_email, profile_exists, get_profile,
    star_article, unstar_article, get_starred, get_starred_count, update_note,
)
from profiler import show_onboarding


### PAGE CONFIG — must be the very first Streamlit command
st.set_page_config(
    page_title="Biotech News Digest", 
    page_icon="🧬",
    layout="wide" #uses the full width of screen. can be used as 'centered'
)


### CACHING — makes the app fast
# @st.cache_data --> decrator --> run this function once, remember the result
# without this, every click would re-fetch all feeds and re-call the AI
@st.cache_data(ttl=1800, show_spinner=False) #limited runs with every 1800 seconds, show spinner = False hides the loading animation
def get_articles(user_id):
    profile = get_profile(user_id)
    
    articles = fetch_all_articles() # downloads the 4 RSS feeds, returns 38 article dictionary

    for article in articles:# summarise each one with AI
        article["ai_summary"] = summarize_article( # this is the slow part — 38 API calls
            article["title"],
            article["raw_summary"],
            article.get("full_text", ""),
            profile=profile
        )

    return articles

### TOPIC TAGGING — figures out which topics each article belongs to
# takes one article dict, returns a list of matching topic names
def tag_article(article):
    searchable = (article["title"] + " " + article["raw_summary"]).lower()# searches the title + raw summary for keywords defined in config.py
    matched = []

    for topic, keywords in TOPICS.items(): #loops throught TOPICS dictionary -- > gives key and value at once
        if topic == "All": # # skip "All" — it's not a real topic to match against
            continue
        if any(kw in searchable for kw in keywords): #any() returns True if at least one keyword is found
            matched.append(topic)

    return matched if matched else ["Other"]  # if nothing matched, label it "Other"


# CARD COLORS — each article gets an accent color based on its primary topic group
_TOPIC_GROUP_COLORS = {
    # Therapeutic modalities — blue
    "CRISPR":               "#4A90D9",
    "Gene Therapy":         "#4A90D9",
    "RNA / mRNA":           "#4A90D9",
    "Cell Therapy":         "#4A90D9",
    "Antibody":             "#4A90D9",
    # Disease areas — rose
    "Cancer":               "#D95C5C",
    "Rare Disease":         "#D95C5C",
    "Neuroscience":         "#D95C5C",
    "Infectious Disease":   "#D95C5C",
    # Research & technology — green
    "Genomics":             "#2EAA72",
    "Diagnostics":          "#2EAA72",
    "AI & Drug Discovery":  "#2EAA72",
    # Business & regulatory — amber
    "Drug Development":     "#E8A020",
    "FDA / Regulatory":     "#E8A020",
    "Acquisitions":         "#E8A020",
    "Funding":              "#E8A020",
}
_DEFAULT_CARD_COLOR = "#888888"  # grey for "Other" / unmatched

def get_card_color(article):
    """Returns the group hue for the article's first recognized topic tag."""
    for tag in article.get("topic_tags", []):
        if tag in _TOPIC_GROUP_COLORS:
            return _TOPIC_GROUP_COLORS[tag]
    return _DEFAULT_CARD_COLOR

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

# CSS-safe slug per focus area — used as the st.button `key` so each button gets
# a `.st-key-nav_<slug>` class we can target with injected CSS in build_sidebar()
_FOCUS_AREA_SLUGS = {
    "Gene & Cell Therapy": "gene_cell_therapy",
    "Oncology":            "oncology",
    "Emerging Biology":    "emerging_biology",
    "Rare & Neurological": "rare_neurological",
    "Digital & Precision": "digital_precision",
    "Business & Industry": "business_industry",
}

# banner image shown above each focus area's section header
FOCUS_AREA_IMAGES = {
    "Gene & Cell Therapy":  "https://images.unsplash.com/photo-1643780668909-580822430155?w=1200&q=80",
    "Oncology":             "https://images.unsplash.com/photo-1576086213369-97a306d36557?q=80&w=1480",
    "Emerging Biology":     "https://images.unsplash.com/photo-1530026405186-ed1f139313f3?w=1200&q=80",
    "Rare & Neurological":  "https://plus.unsplash.com/premium_photo-1681487548276-48a2c640ade9?w=1200&q=80",
    "Digital & Precision":  "https://plus.unsplash.com/premium_photo-1698421947098-d68176a8f5b2?w=1200&q=80",
    "Business & Industry":  "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=1200&q=80",
    "Other Articles":       "https://images.unsplash.com/photo-1614935151651-0bea6508db6b?w=1200&q=80",
}

def score_article(article, profile=None):
    summary = article.get("ai_summary", {})
    if "error" in summary:
        return 0
    score = 0

    # results with real numbers are more useful than vague summaries
    if any(ch.isdigit() for ch in summary.get("results", "").lower()):
        score += 3

    # full article text means the AI had more to work with
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

    # profile match — articles relevant to what the user cares about score higher
    if profile:
        searchable = (article.get("title", "") + " " + article.get("raw_summary", "")).lower()

        # company match — user explicitly asked to track these
        companies = [c.strip().lower() for c in profile.get("companies", "").split(",") if c.strip()]
        if any(c in searchable for c in companies):
            score += 4

        # keyword match — up to +4
        keywords = [k.strip().lower() for k in profile.get("keywords", "").split(",") if k.strip()]
        score += min(sum(1 for kw in keywords if kw in searchable) * 2, 4)

        # focus area match via topic tags — +1 per matching area
        article_tags = set(article.get("topic_tags", []))
        for focus in profile.get("focus_areas", []):
            label = focus.split("—")[0].strip()
            if any(t in article_tags for t in _FOCUS_TO_TOPICS.get(label, [])):
                score += 1

    return score


# ARTICLE CARD — renders one article in the UI
# st.expander creates a clickable dropdown — collapsed by default
# inside it we show the full AI summary in 3 columns
# CHANGE: add new summary fields here if you add them to your prompt

def render_card(article, user_id, starred_urls, color=None):
    summary = article.get("ai_summary", {})
    tags = " · ".join(article.get("topic_tags", []))

    score = article.get("relevance_score", 0)
    display_score = max(0, score)
    score_bar = "█" * min(display_score, 10) + "░" * max(0, 10 - display_score)
    card_color = color or get_card_color(article)

    st.markdown(
        f'<div style="height:4px;background:{card_color};border-radius:3px;margin-bottom:4px"></div>',
        unsafe_allow_html=True
    )

    with st.expander(f"**{article['title']}**"): #creates a clickable dropdown — collapsed by default

        # metadata row — source, date, topics, relevance
        st.caption( #renders small greey text
            f"{article['source']} · "
            f"{article['published'].strftime('%B %d, %Y')} · "
            f"Topics: {tags} · "
            f"Relevance: {score_bar} {score}"
        ) # readability

        st.divider()  # horizontal line

        if "error" in summary:
            st.warning(f"Could not summarise: {summary['error']}")
        else:
            st.markdown("🔬 **Technology**")
            st.write(summary.get("technology", "—"))

            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("🏥 **Stage**")
                st.write(summary.get("stage", "—"))
            with col2:
                st.markdown("💡 **Importance**")
                st.write(summary.get("importance", "—"))
            with col3:
                st.markdown("📈 **Market**")
                st.write(summary.get("market", "—"))

            st.markdown("📊 **Results**")
            st.write(summary.get("results", "—"))

            col4, col5 = st.columns(2)
            with col4:
                st.markdown("⚠️ **Limitations**")
                st.write(summary.get("limitations", "—"))
            with col5:
                st.markdown("🚀 **Next Steps**")
                st.write(summary.get("next_steps", "—"))

        col_link, col_star = st.columns([4, 1])
        with col_link:
            st.link_button("Read full article →", article["url"])
        with col_star:
            url = article["url"]
            if url in starred_urls:
                if st.button("⭐ Saved", key=f"star_{url}"):
                    unstar_article(user_id, url)
                    starred_urls.discard(url)
                    st.rerun()
            else:
                if st.button("☆ Save", key=f"star_{url}"):
                    star_article(user_id, article)
                    starred_urls.add(url)
                    st.rerun()

def render_section(focus_label, color, articles, user_id, starred_urls):
    # show topic banner image above section header — fixed 160px height, not full width image height
    image_url = FOCUS_AREA_IMAGES.get(focus_label)
    if image_url:
        st.markdown(f'''
            <div style="
                width: 100%;
                height: 160px;
                background-image: url({image_url});
                background-size: cover;
                background-position: center;
                border-radius: 8px 8px 0 0;
            "></div>
        ''', unsafe_allow_html=True)

    # coloured section header — flush against the image above it when one is shown
    header_radius = "0 0 8px 8px" if image_url else "6px"
    header_margin = "0 0 8px 0" if image_url else "16px 0 8px 0"
    st.markdown(
        f'<div style="background:{color};padding:12px 16px;border-radius:{header_radius};margin:{header_margin}">'
        f'<span style="color:white;font-weight:bold;font-size:1.1rem">{focus_label}</span>'
        f'<span style="color:rgba(255,255,255,0.75);font-size:0.9rem;margin-left:10px">{len(articles)} articles</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    for article in articles:
        render_card(article, user_id, starred_urls, color=color)


def render_starred_view(user_id):
    col_back, col_title = st.columns([1, 5])
    with col_back:
        if st.button("← Feed"):
            st.session_state["view"] = "feed"
            st.rerun()
    with col_title:
        st.title("⭐ Saved Articles")

    starred = get_starred(user_id)

    if not starred:
        st.info("No saved articles yet. Click ☆ Save on any article in the feed.")
        return

    st.caption(f"{len(starred)} saved articles")

    for article in starred:
        summary = article.get("ai_summary", {})
        with st.expander(f"**{article['title']}**"):
            st.caption(
                f"{article.get('source', '')} · "
                f"Published {article.get('published', '')[:10]} · "
                f"Saved {article.get('saved_at', '')[:10]}"
            )
            st.divider()

            if summary and "error" not in summary:
                st.markdown("🔬 **Technology**")
                st.write(summary.get("technology", "—"))

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown("🏥 **Stage**")
                    st.write(summary.get("stage", "—"))
                with col2:
                    st.markdown("💡 **Importance**")
                    st.write(summary.get("importance", "—"))
                with col3:
                    st.markdown("📈 **Market**")
                    st.write(summary.get("market", "—"))

                st.markdown("📊 **Results**")
                st.write(summary.get("results", "—"))

                col4, col5 = st.columns(2)
                with col4:
                    st.markdown("⚠️ **Limitations**")
                    st.write(summary.get("limitations", "—"))
                with col5:
                    st.markdown("🚀 **Next Steps**")
                    st.write(summary.get("next_steps", "—"))

            st.divider()

            note = st.text_area(
                "📝 Personal note",
                value=article.get("note", ""),
                key=f"note_{article['url']}",
                placeholder="Add your thoughts on this article...",
                height=80,
            )
            col_save, col_link, col_remove = st.columns([2, 4, 1])
            with col_save:
                if st.button("Save note", key=f"save_{article['url']}"):
                    update_note(user_id, article["url"], note)
                    st.success("Note saved!")
            with col_link:
                st.link_button("Read full article →", article["url"])
            with col_remove:
                if st.button("🗑️ Remove", key=f"remove_{article['url']}"):
                    unstar_article(user_id, article["url"])
                    st.rerun()


# SIDEBAR — topic filter
# CHANGE: topics come from config.py — add new ones there
def build_sidebar(user_id, profile):
    st.sidebar.title("🧬 Biotech Digest")
    st.sidebar.caption("AI-powered · Updates every 30 min")
    st.sidebar.divider()

    starred_count = get_starred_count(user_id)
    if st.sidebar.button(f"⭐  Starred  ({starred_count})", use_container_width=True):
        st.session_state["view"] = "starred"
        st.rerun()

    if EMAIL_ENABLED:
        from emailer import send_digest_email
        if st.sidebar.button("📧 Send digest now", use_container_width=True):
            with st.sidebar.spinner("Building and sending digest..."):
                success = send_digest_email()
            if success:
                st.sidebar.success("✅ Digest sent!")
            else:
                st.sidebar.error("❌ Send failed — check your .env config.")

    # clears the session-stored articles so main() re-fetches and re-summarises on the next rerun
    if st.sidebar.button("🔄 Refresh feed", use_container_width=True):
        st.session_state.pop("articles", None)
        st.rerun()

    st.sidebar.divider()

    # focus areas — clickable buttons that filter the main page down to one section
    focus_areas = profile.get("focus_areas", []) if profile else []
    if focus_areas:
        st.sidebar.markdown("**Your focus areas**")
        active_section = st.session_state.get("active_section", "All")

        # CSS-only styling: each nav button gets a `.st-key-nav_<slug>` class from its
        # `key`, so we can give it a solid coloured background + white text. The active
        # button (kind="primary" on the underlying <button>) gets a white border on top;
        # inactive buttons (kind="secondary") get no border.
        nav_colors = {"all": "#666666"}
        nav_colors.update({slug: _FOCUS_AREA_COLORS[fa] for fa, slug in _FOCUS_AREA_SLUGS.items()})
        css_rules = "".join(f"""
            .st-key-nav_{slug} button {{
                background-color: {color};
                color: white;
                border: none;
            }}
            .st-key-nav_{slug} button[kind="primary"] {{
                border: 2px solid white;
            }}
            .st-key-nav_{slug} button p {{
                color: white;
            }}
        """ for slug, color in nav_colors.items())
        st.sidebar.markdown(f"<style>{css_rules}</style>", unsafe_allow_html=True)

        # resets the filter — shows every section again
        if st.sidebar.button(
            "All sections",
            key="nav_all",
            use_container_width=True,
            type="primary" if active_section == "All" else "secondary",  # highlights when selected
        ):
            st.session_state["active_section"] = "All"
            st.rerun()

        for fa in focus_areas:
            slug = _FOCUS_AREA_SLUGS.get(fa, "other")
            if st.sidebar.button(
                fa,
                key=f"nav_{slug}",
                use_container_width=True,
                type="primary" if active_section == fa else "secondary",  # highlights when selected
            ):
                st.session_state["active_section"] = fa
                st.rerun()

        st.sidebar.divider()

    source_list = "\n".join(f"- {name}" for name, _ in RSS_FEEDS)
    st.sidebar.markdown(f"**Sources**\n{source_list}")

# MAIN — runs everything in order --> called at the bottom
# Streamlit reruns this entire function on every user interaction
def main():
    init_db()

    # identity gate — each browser session identifies itself by email so
    # friends sharing the link each get their own profile/starred list
    if "user_id" not in st.session_state:
        if "new_user_email" in st.session_state:
            # brand-new email — hand off straight to onboarding, pre-filled
            submitted = show_onboarding(default_email=st.session_state["new_user_email"])
            if submitted:
                st.session_state.pop("new_user_email", None)
                st.rerun()
            return

        st.markdown("## 🧬 Biotech Digest")
        st.caption("Enter your email to continue")
        email_input = st.text_input("Email address", placeholder="you@email.com")
        if st.button("Continue →", type="primary"):
            email_clean = email_input.strip()
            if not email_clean:
                st.error("Please enter your email address")
                return
            existing = get_user_by_email(email_clean)
            if existing:
                st.session_state["user_id"] = existing["id"]
                st.session_state["user_name"] = existing["full_name"].split()[0]
            else:
                st.session_state["new_user_email"] = email_clean
            st.rerun()
        return

    user = get_user(st.session_state["user_id"])
    if user is None or not profile_exists(user["id"]):
        submitted = show_onboarding(default_email=user["email"] if user else "")
        if submitted:
            st.rerun()
        return

    if "view" not in st.session_state:
        st.session_state["view"] = "feed"

    # tracks which focus area (if any) the sidebar nav has filtered the page to
    if "active_section" not in st.session_state:
        st.session_state["active_section"] = "All"

    profile = get_profile(user["id"])
    build_sidebar(user["id"], profile)

    if st.session_state["view"] == "starred":
        render_starred_view(user["id"])
        return

    st.title("🧬 Biotech News Digest")
    st.caption(
        f"Latest biotech news · summarised by AI · "
        f"{datetime.date.today().strftime('%B %d, %Y')}"
    )

    # fetch + summarise only once per session — reused across reruns until "Refresh feed" clears it
    if "articles" not in st.session_state:
        with st.spinner("Fetching and summarising articles..."):
            st.session_state["articles"] = get_articles(user["id"])
    articles = st.session_state["articles"]

    if not articles:
        st.error("No articles fetched. Check your RSS feeds in config.py.")
        return

    starred_urls = {a["url"] for a in get_starred(user["id"])}

    for article in articles:
        if not article.get("topic_tags"):
            article["topic_tags"] = tag_article(article)

    for article in articles:
        if "relevance_score" not in article:
            article["relevance_score"] = score_article(article, profile)

    # sort all articles by relevance first, then assign to sections
    all_sorted = sorted(articles, key=lambda a: a["relevance_score"], reverse=True)

    focus_areas = profile.get("focus_areas", []) if profile else []
    sections = {fa: [] for fa in focus_areas}
    other_articles = []
    assigned_urls = set()

    for article in all_sorted:
        article_tags = set(article.get("topic_tags", []))
        placed = False
        for fa in focus_areas:
            if article["url"] not in assigned_urls:
                if any(t in article_tags for t in _FOCUS_TO_TOPICS.get(fa, [])):
                    sections[fa].append(article)
                    assigned_urls.add(article["url"])
                    placed = True
                    break
        if not placed:
            other_articles.append(article)

    active_section = st.session_state.get("active_section", "All")

    # render each focus area section in the order the user chose them —
    # if a specific section is active, only that one is shown
    for fa in focus_areas:
        if active_section not in ("All", fa):
            continue
        if sections[fa]:
            render_section(fa, _FOCUS_AREA_COLORS.get(fa, "#888888"), sections[fa], user["id"], starred_urls)

    # other articles — collapsed and visually de-emphasised, hidden while a section is filtered
    if other_articles and active_section == "All":
        other_image_url = FOCUS_AREA_IMAGES.get("Other Articles")
        if other_image_url:
            st.markdown(f'''
                <div style="
                    width: 100%;
                    height: 160px;
                    background-image: url({other_image_url});
                    background-size: cover;
                    background-position: center;
                    border-radius: 8px 8px 0 0;
                "></div>
            ''', unsafe_allow_html=True)

        other_header_radius = "0 0 8px 8px" if other_image_url else "6px"
        other_header_margin = "0 0 8px 0" if other_image_url else "16px 0 8px 0"
        st.markdown(
            f'<div style="background:#888888;padding:10px 16px;border-radius:{other_header_radius};margin:{other_header_margin}">'
            f'<span style="color:white;font-weight:bold">Other Articles</span>'
            f'<span style="color:rgba(255,255,255,0.75);font-size:0.9rem;margin-left:10px">{len(other_articles)} articles</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        with st.expander("Show other articles", expanded=False):
            for article in other_articles:
                render_card(article, user["id"], starred_urls, color="#888888")


main()
