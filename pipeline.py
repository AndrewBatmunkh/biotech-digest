# pipeline.py — connects fetcher + summarizer together

from fetcher import fetch_all_articles
from summarizer import summarize_article

def run_pipeline(): #gets everything from the other files
     print("Step 1: Fetching articles from RSS feeds...")
     articles  = fetch_all_articles() # downloads the Rss eeds 
     print(f"✅ Fetched {len(articles)} articles\n")
     print("Step 2: Summarising first 3 articles with AI...")
     test_articles = articles[:5] # calling the first three
     
     for i, article in enumerate(test_articles): # this loops through each articles
        print(f"\n{'='*60}")
        print(f"ARTICLE {i+1} of {len(test_articles)}")
        print(f"{'='*60}")
        print(f"SOURCE:    {article['source']}")
        print(f"TITLE:     {article['title']}")
        print(f"PUBLISHED: {article['published'].strftime('%B %d, %Y')}") #strftime just makes it a readible target
        print(f"URL:       {article['url']}")
        print(f"\nSending to AI...")

        summary = summarize_article(
            article["title"],
            article["raw_summary"],
            article.get("full_text", ""),
        )

        article["ai_summary"] = summary

        print("\n--- AI SUMMARY ---")
        if "error" in summary:
            print(f"❌ Error: {summary['error']}")
        else:
            print(f"🔬 Technology:   {summary['technology']}")
            print(f"🏥 Stage:        {summary['stage']}")
            print(f"📊 Results:      {summary['results']}")
            print(f"💡 Importance:   {summary['importance']}")
            print(f"📈 Market:       {summary['market']}")
            print(f"⚠️  Limitations:  {summary['limitations']}")
            print(f"🚀 Next steps:   {summary['next_steps']}")

     print(f"\n{'='*60}")
     print(f"✅ Pipeline complete — {len(test_articles)} articles summarised")
     print(f"{'='*60}")

if __name__ == "__main__": #only runs when you do python3 pipeline.py
    run_pipeline() #when app.py imports from the file later, the block stays silent

