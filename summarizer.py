from groq import Groq
import json
from config import GROQ_API_KEY

client = Groq(api_key=GROQ_API_KEY)

#enai.configure(api_key=GEMINI_API_KEY) # logged in
#model = genai.GenerativeModel("gemini-2.0-flash") #line open, creates model object

# THE PROMPT 
# this is the most important thing to understand — the prompt IS the programming
#{{ }}, double curly braces - final output will be {}
PROMPT_TEMPLATE = """
You are a molecular biologist and biotech research scientist reviewing primary literature and industry news. Your reader is a biotech graduate student who wants scientific depth, not a lay summary.

Given the article title and text below, respond ONLY with a JSON object in exactly this format:
{{
    "technology": "Name the specific therapeutic modality and molecule — e.g. 'AAV9-packaged CRISPR base editor targeting exon 23 of DMD', 'bispecific CD3×CD19 IgG1 antibody', 'LNP-formulated mRNA encoding spike protein'. Describe what it physically does at the molecular level.",
    "mechanism": "Name the exact molecular target(s), cell types, and pathway involved — e.g. 'blocks PD-L1 on tumor-associated macrophages, relieving suppression of CD8+ T cells via the PD-1/PD-L1 checkpoint axis'. Include receptor subtypes, gene symbols, or protein domains when stated.",
    "evolution": "What does this replace or improve on scientifically — name the predecessor approach and the specific advantage (e.g. higher HDR efficiency vs. NHEJ, reduced off-target editing, broader HLA coverage, improved half-life vs. first-gen antibody).",
    "stage": "Development stage — research / preclinical / IND-filed / Phase 1 / Phase 2 / Phase 3 / BLA or NDA submitted / FDA approved. Include any regulatory designations: Breakthrough Therapy, Fast Track, Orphan Drug, Accelerated Approval.",
    "results": "Key quantitative outcomes — efficacy (ORR, OS, PFS, editing efficiency %, AAV transduction rate), safety (DLTs, grade 3+ AEs, immunogenicity), or biomarker data with patient numbers and p-values where reported. Write 'Not reported' if absent.",
    "importance": "Why this matters — clinical impact (unmet need addressed, patient population size, survival improvement), scientific significance (paradigm shift, first-in-class), or market relevance (disease burden, competitive landscape).",
    "future": "Next scientific or commercial steps — upcoming data readouts, Phase expansion, IND plans, partnership or licensing deals, regulatory milestones, or projected market size with timeframe."
}}

Rules:
- Respond with JSON only — no extra text, no markdown, no code fences
- Always use the specific names from the article: drug names, gene symbols, protein targets, cell types, pathways
- Include every number, percentage, or p-value mentioned — precision matters
- If a field cannot be answered from the article, write "Not specified in article" — never fabricate
- Prioritise molecular mechanism and quantitative data over vague high-level statements

Article title: {title}
Article text: {excerpt}
"""

# FUNCTION 1 — summarise a single article
def summarize_article(title, raw_summary, full_text=""): # title and raw_summary come in from fetcher.py's article dict
    best_text = full_text if full_text else raw_summary
    prompt = PROMPT_TEMPLATE.format(
        title=title,
        excerpt= best_text or "no excerpt available" # fallback if summary is empty
    )
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile", 
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800
            )
        raw_text = response.choices[0].message.content.strip() #raw string that gemini returns
        raw_text = raw_text.replace("```json", "").replace("```", "").strip() #sometimes in markdown code, fixes that
        results = json.loads(raw_text)# turns text strings into python dictionary
        return results

    except json.JSONDecodeError:
        return {"error": "Gemini returned invalid JSON"}

    except Exception as e: # any other error — bad API key, rate limit, network issue etc
        return {"error": f"API call failed: {e}"}


# FUNCTION 2 — summarise a whole list of articles
def summarize_articles(articles):
    total = len(articles)
    for i, article in enumerate(articles): # enumerate gives us both the index (i) and the item (article)
        print(f"Summarising {i+1}/{total}: {article['title'][:50]}...")
        article["ai_summary"] = summarize_article(
            article["title"],
            article.get("full_text", "") # calls summarize article() for each article, and prints results back into article dictionary
        )
    return articles  # return the same list, now with ai_summary filled in


# TEST BLOCK — only runs with: python3 summarizer.py
if __name__ == "__main__":# we import fetch here so we can grab one real article to test with
    from fetcher import fetch_all_articles
    print("Fetching one article to test with...")
    articles = fetch_all_articles()

    test_article = articles[0]
    print(f"\nTitle: {test_article['title']}")
    print(f"Raw summary: {test_article['raw_summary'][:300]}...")
    print("\Sending to AI...")

    result = summarize_article(test_article["title"], test_article["raw_summary"])

    print("\n--- AI Summary ---")
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"Technology:   {result['technology']}")
        print(f"Evolution:    {result['evolution']}")
        print(f"Importance:   {result['importance']}")
        print(f"Stage:        {result['stage']}")
        print(f"Results:      {result['results']}")
        print(f"Future:       {result['future']}")

