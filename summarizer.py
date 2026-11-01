from groq import Groq
import json
from config import GROQ_API_KEY

client = Groq(api_key=GROQ_API_KEY, timeout=30.0)  # fail fast instead of hanging forever on a stuck request

PROMPT_TEMPLATE = """
You are a senior biotech analyst writing intelligence briefings.

READER PROFILE — use this to shape every summary:
- Technical level: {technical_level}
  Beginner = explain everything simply, no jargon at all
  Intermediate = plain English with terms explained inline
  Expert = keep technical depth but still explain clearly
- Focus areas: {focus_areas}
  Emphasise angles related to these areas in every field
- What matters most: {what_matters}
  Give extra depth to fields matching these priorities
- Companies to watch: {companies}
  If any appear in the article, flag them explicitly with a note
- Keywords to flag: {keywords}
  If any appear in the article, flag them explicitly with a note

RULES:
- 1-2 sentences max per field
- Write in plain English — explain what things do, not just what they are called
- When you use a scientific term, immediately explain it in plain English in the same sentence
  Good example: 'CRISPR-Cas9 (a gene editing tool that works like molecular scissors) cut out the faulty gene'
  Bad example: 'Cas9 nuclease activity at the KRAS G12C locus via electroporation of RNP complexes'
- ALWAYS keep every number, percentage, statistic, trial phase, patient count, response rate,
  survival data, market size, deal value, and timeline — these are non-negotiable
- Extract every specific detail the article provides — drug names, companies, trial phases, numbers
- Where the article lacks detail, add ONE sentence of relevant context from your knowledge
- Never write generic filler — every sentence must add value
- Never repeat the same point across fields
- If a company or keyword from the reader profile appears, start that sentence with FLAG:

TONE: Explain to a smart friend who understands business and data but is not a scientist.
They want the numbers and what they mean, not the molecular mechanism described in Latin.

Respond ONLY with this JSON — no markdown, no code fences:
{{
    "technology": "1-2 sentences max. What this technology does in plain English, how it works simply explained, what makes it different from existing approaches. Include the technical name but explain it immediately.",
    "stage": "1-2 sentences max. Where this is in development — research, animal testing, human trials which phase, or approved. Include patient numbers, trial locations, eligibility if known.",
    "results": "1-2 sentences max. ALL numbers and data points — response rates, survival rates, percentages, comparisons to existing treatments. Explain what each number means for patients in plain English.",
    "importance": "1-2 sentences max. What problem this solves in plain English, how many people are affected globally, why current treatments fail, what changes for patients if this works.",
    "market": "1-2 sentences max. Market size in dollars, named competitors and where they are in development, deal values, commercial potential and timeline to revenue.",
    "limitations": "1-2 sentences max. What could go wrong in plain English, safety concerns with numbers if available, regulatory hurdles, manufacturing or scaling challenges.",
    "next_steps": "1-2 sentences max. What happens next with specific timelines, planned trials, upcoming regulatory decisions, conference presentations, partnerships to watch."
}}

Article title: {title}
Article text: {excerpt}
"""

# FUNCTION 1 — summarise a single article
def summarize_article(title, raw_summary, full_text="", profile=None):
    best_text = full_text if full_text else raw_summary

    if profile:
        technical_level = profile.get("technical_level", "Intermediate")
        focus_areas     = ", ".join(profile.get("focus_areas", [])) or "General biotech"
        what_matters    = ", ".join(profile.get("what_matters", [])) or "The science, the data"
        companies       = profile.get("companies", "") or "none specified"
        keywords        = profile.get("keywords", "") or "none specified"
    else:
        technical_level = "Intermediate"
        focus_areas     = "General biotech"
        what_matters    = "The science, the data"
        companies       = "none specified"
        keywords        = "none specified"

    prompt = PROMPT_TEMPLATE.format(
        title=title,
        excerpt=best_text or "no excerpt available",
        technical_level=technical_level,
        focus_areas=focus_areas,
        what_matters=what_matters,
        companies=companies,
        keywords=keywords,
    )
    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",  # old model retired on this account — largest general-purpose model available
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2500,
        )
        raw_text = response.choices[0].message.content.strip()
        # extract just the JSON object — ignore any text before { or after }
        start = raw_text.find("{")
        end   = raw_text.rfind("}") + 1
        if start == -1 or end == 0:
            return {"error": "Groq returned no JSON"}
        results = json.loads(raw_text[start:end])
        return results

    except json.JSONDecodeError as e:
        return {"error": f"Groq returned invalid JSON: {e}"}

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
    print("\nSending to AI...")

    result = summarize_article(test_article["title"], test_article["raw_summary"])

    print("\n--- AI Summary ---")
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"Technology:   {result.get('technology', '—')}")
        print(f"Stage:        {result.get('stage', '—')}")
        print(f"Results:      {result.get('results', '—')}")
        print(f"Importance:   {result.get('importance', '—')}")
        print(f"Market:       {result.get('market', '—')}")
        print(f"Limitations:  {result.get('limitations', '—')}")
        print(f"Next Steps:   {result.get('next_steps', '—')}")

