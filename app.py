# app.py — the Streamlit UI
# streamlit run app.py

import streamlit as st
import datetime

from config import TOPICS, RSS_FEEDS
from fetcher import fetch_all_articles #downloads the RSS feeds
from summarizer import summarize_article #groq ai


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
def get_articles():
    articles = fetch_all_articles() # downloads the 4 RSS feeds, returns 38 article dictionary

    for article in articles:# summarise each one with AI
        article["ai_summary"] = summarize_article( # this is the slow part — 38 API calls
            article["title"],
            article["raw_summary"],
            article.get("full_text", "")
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


### RELEVANCE SCORING — rates how content-rich an article's AI summary is
# higher score = more scientific detail = floats to top of feed --> score of -9999 = every field was "Not specified" = sinks to bottom
_NOT_SPECIFIED = "not specified in article"
_SUMMARY_FIELDS = ["technology", "mechanism", "evolution", "stage", "results", "importance", "future"]

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

def score_article(article):
    summary = article.get("ai_summary", {})
    if "error" in summary:
        return 0

    # count fields that actually have content (not "not specified")
    filled = sum(
        1 for f in _SUMMARY_FIELDS
        if _NOT_SPECIFIED not in summary.get(f, "").lower()
        and summary.get(f, "") not in ("", "—")
    )

    if filled == 0:
        return -9999  # all fields empty — push to absolute bottom

    score = filled  # base: 0–6

    # +2 if results field has actual numbers (quantitative data = more useful)
    results_text = summary.get("results", "").lower()
    if any(ch.isdigit() for ch in results_text) and _NOT_SPECIFIED not in results_text:
        score += 2

    # +1 if mechanism is detailed (>80 chars means real molecular info, not a placeholder)
    mechanism_text = summary.get("mechanism", "").lower()
    if len(mechanism_text) > 80 and _NOT_SPECIFIED not in mechanism_text:
        score += 1

    # +1 if full article text was scraped (AI had more to work with)
    if article.get("full_text"):
        score += 1

    # recency bonus — fresh news scores higher
    published = article.get("published")
    if published:
        age_hours = (datetime.datetime.now() - published).total_seconds() / 3600
        if age_hours < 24:
            score += 2
        elif age_hours < 48:
            score += 1

    return score  # max possible ≈ 12


# ARTICLE CARD — renders one article in the UI
# st.expander creates a clickable dropdown — collapsed by default
# inside it we show the full AI summary in 3 columns
# CHANGE: add new summary fields here if you add them to your prompt

def render_card(article):
    summary = article.get("ai_summary", {}) # gets the Ai summary dict
    tags = " · ".join(article.get("topic_tags", [])) #fallback if missing 

    score = article.get("relevance_score", 0)
    score_bar = "█" * min(score, 10) + "░" * max(0, 10 - score)  # visual bar, capped at 10
    color = get_card_color(article)  # group hue for this card

    # thin colored bar above the expander — color indicates topic group
    st.markdown(
        f'<div style="height:4px;background:{color};border-radius:3px;margin-bottom:4px"></div>',
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
            # if AI call failed, show a warning instead of crashing
            st.warning(f"Could not summarise: {summary['error']}")
        else:
            col1, col2, col3 = st.columns(3)#creates 3 equal width columns, assigne to varaibles
            with col1: #
                st.markdown("🔬 **Technology**")#renders markdown text
                st.write(summary.get("technology", "—")) #displays any Python value, the summary gets the value, with - as the fallback
            with col2:
                st.markdown("📈 **Evolution**")
                st.write(summary.get("evolution", "—"))
            with col3:
                st.markdown("🏥 **Stage**")
                st.write(summary.get("stage", "—"))

            # mechanism gets its own full-width row — needs space for molecular detail
            st.markdown("⚙️ **Mechanism of Action**")
            st.write(summary.get("mechanism", "—"))

            # another 3 columns for the next 3 fields
            col4, col5, col6 = st.columns(3)
            with col4:
                st.markdown("📊 **Results**")
                st.write(summary.get("results", "—"))
            with col5:
                st.markdown("💡 **Importance**")
                st.write(summary.get("importance", "—"))
            with col6:
                st.markdown("🚀 **Future**")
                st.write(summary.get("future", "—"))

        # link to original article
        st.link_button("Read full article →", article["url"])

# SIDEBAR — topic filter
# CHANGE: topics come from config.py — add new ones there
def build_sidebar():
    st.sidebar.title("🧬 Biotech Digest") #streamlit object --> anything you call on it appreas in the left panel
    st.sidebar.caption("AI-powered · Updates every 30 min") 
    st.sidebar.divider() 

    st.sidebar.subheader("Filter by topic")
    selected = st.sidebar.radio( # creates a sinlge selectionbutton group
        label="topic",               #internal label — hidden from UI
        options=list(TOPICS.keys()), #["All", "CRISPR", "Gene Therapy", ...]
        label_visibility="collapsed" #hides the label text
    )

    st.sidebar.divider()
    st.sidebar.markdown(
        "**Card colors**\n"
        '<span style="color:#4A90D9">■</span> Therapeutic modalities<br>'
        '<span style="color:#D95C5C">■</span> Disease areas<br>'
        '<span style="color:#2EAA72">■</span> Research & technology<br>'
        '<span style="color:#E8A020">■</span> Business & regulatory',
        unsafe_allow_html=True
    )

    st.sidebar.divider()
    source_list = "\n".join(f"- {name}" for name, _ in RSS_FEEDS)  # builds from config — no manual updates needed
    st.sidebar.markdown(f"**Sources**\n{source_list}")

    return selected  # returns whatever topic the user clicked

# MAIN — runs everything in order --> called at the bottom
# Streamlit reruns this entire function on every user interaction
def main(): 
    selected_topic = build_sidebar() # build sidebar and get selected topic --> selected topics, runs everytime

    st.title("🧬 Biotech News Digest") #header
    st.caption(
        f"Latest biotech news · summarised by AI · "
        f"{datetime.date.today().strftime('%B %d, %Y')}"
    )
    # ── fetch + summarise ──
    # show a spinner while loading — gives user feedback
    with st.spinner("Fetching and summarising articles..."): #shows alot --> 
        articles = get_articles()

    if not articles:
        st.error("No articles fetched. Check your RSS feeds in config.py.") 
        return  # stop here if nothing came back

    # ── tag topics ──
    for article in articles: # tag each article with matching topics --> only if not tagged yet
        if not article.get("topic_tags"):
            article["topic_tags"] = tag_article(article) #empty list

    # ── score ──
    # runs once per article after AI summary is done; score is stored on the dict so it's not recalculated on every re-render
    for article in articles:
        if "relevance_score" not in article:
            article["relevance_score"] = score_article(article)

    # ── filter ──
    if selected_topic == "All": # if "All" is selected show everything
        filtered = articles
    else:
        filtered = [
            a for a in articles # use a list comprehension --> to build a new list containing only articles --> selected topics in topics tag
            if selected_topic in a.get("topic_tags", [])
        ]

    # ── sort by relevance — highest score first, "all not specified" articles sink to bottom ──
    filtered = sorted(filtered, key=lambda a: a["relevance_score"], reverse=True)

    # ── render ──
    st.subheader(f"{len(filtered)} articles · {selected_topic}") # small headings

    if not filtered: # 
        st.info(f"No articles matched '{selected_topic}'. Try 'All' or another topic.") # shows a blue info box --> If no articles matched the filter, tell the user and stop — no point trying to render an empty list.
        return

    # render each article as a card
    for article in filtered:
        render_card(article) #goes through every filtered article and calls render card

# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────
# call main() when the file runs
# note: no if __name__ == "__main__" needed here
# streamlit handles the running itself
main()
