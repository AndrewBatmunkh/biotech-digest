import feedparser   # reads xmL and converts it, the library that downloads + parses RSS feeds into Python dicts
import datetime  # built-in Python tool for working with dates and times
import re          # built-in tool for removing HTML tags from text
import requests    # downloads the full article HTML page
import trafilatura # extracts clean body text from HTML (strips ads, nav, footers)
from concurrent.futures import ThreadPoolExecutor, as_completed  # fetch many articles at once in parallel

from config import RSS_FEEDS,  MAX_ARTICLES_PER_FEED

SCRAPE_TIMEOUT   = 10    # seconds to wait per article before giving up
SCRAPE_MAX_CHARS = 3000  # truncate so AI prompt stays a reasonable size
SCRAPE_WORKERS   = 1     # how many articles to download at the same time


###DATE FIXER FUNCTION
# feedparser gives dates as a tuple like (2026, 5, 5, 8, 0, 0)
# we convert it to a proper Python datetime object so we can sort + format it
def _parse_date(entry):
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime.datetime(*entry.published_parsed[:6]) #unpacks them in seperate arguments
        except (TypeError, ValueError):
            pass
    return datetime.datetime.now()  # fallback: use right now if no date found


### TEXT CLEANING FUNCTION
def _clean_text(raw):
    if not raw:
        return ""
    return re.sub(r"<[^>]+>", "", raw).strip()
#re.sub find HTML tag and deletes it, anything that starts with < and > , then .strip() removes any leftover spaces from start to end

###NEW FUNCTION! --> HELPS PULL FULL TEXT --> BETTER AI SUMMARY?
# Downloads the full article page and returns clean plain text
# Falls back to "" if the site blocks us, times out, or has no extractable text
def _fetch_full_text(url):
    try:
        resp = requests.get(
            url,
            timeout=SCRAPE_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (compatible; BiotechDigestBot/1.0)"},
        )
        resp.raise_for_status()
        text = trafilatura.extract(
            resp.text,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
        )
        if text:
            return text[:SCRAPE_MAX_CHARS]  # cap length so AI prompts stay manageable
    except Exception:
        pass
    return ""

###ARTICLE THREADER FUNCTION
# Sends all articles to a thread pool so scraping happens in parallel, not one-by-one
# Without this, 77 articles × 10s timeout = potentially 13 minutes of waiting
def _scrape_articles(articles):
    def _worker(article):
        article["full_text"] = _fetch_full_text(article["url"])
        return article

    with ThreadPoolExecutor(max_workers=SCRAPE_WORKERS) as pool:
        futures = {pool.submit(_worker, a): a for a in articles}
        for future in as_completed(futures):
            future.result()

    return articles


###MAIN FUNCTION — fetches all articles from all feeds
#no input is needed - all from config.py - this will be later used in app.py
def fetch_all_articles():
    all_articles = [] #empty list, put article dictionaries one by one
    for source_name, feed_url in RSS_FEEDS: # loops through the  feeds in config.py
        try:
            feed = feedparser.parse(feed_url) # goes to the url, downlaods the RSS XML
            if feed.bozo and not feed.entries:
                print(f"skipping {source_name}")
                continue
            for entry in feed.entries[:MAX_ARTICLES_PER_FEED]: #  loop through each article, but only up to MAX_ARTICLES_PER_FEED
                article = {
                    "source": source_name,
                    "title": entry.get("title", "No title").strip(), #if theres a title get title, if not dont need
                    "url":  entry.get("link", ""),
                    "raw_summary": _clean_text(entry.get("summary", "")),
                    "full_text":   "",   # filled below by _scrape_articles — the full article body
                    "published":   _parse_date(entry),
                    "ai_summary":  "",   # empty for now — summarizer.py fills this later
                    "topic_tags":  [],   # empty for now — app.py fills this later
                }
                all_articles.append(article) #add to our list
        except Exception as e:
            print(f"error fetching {source_name}: {e}")# if anything above crashed - bad internet, broken feed, anything, just go
            continue
    print(f"Scraping full text for {len(all_articles)} articles...")
    _scrape_articles(all_articles)
    scraped = sum(1 for a in all_articles if a["full_text"])
    print(f"Scraped {scraped}/{len(all_articles)} successfully")

    all_articles.sort(key=lambda a: a["published"], reverse=True) # sort all by the date
    return all_articles


###TEST BLOCK — only runs when you do: python3 fetcher.py

if __name__ == "__main__":
    print("Fetching articles...")
    articles = fetch_all_articles()
    print(f"\nFetched {len(articles)} articles total\n") # countr the items in list

    for article in articles[:5]:
        print(f"SOURCE:    {article['source']}")
        print(f"TITLE:     {article['title']}")
        print(f"PUBLISHED: {article['published']}") 
        print(f"URL:       {article['url']}")
        body = article["full_text"] or article["raw_summary"]  # prefer full text, fall back to RSS excerpt
        print(f"BODY:      {body[:150]}...") # takes the first 150 characters
        print("-" * 60) #prints lines of 60 dashes in visual divider