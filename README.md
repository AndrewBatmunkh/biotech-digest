# Biotech Digest

A personalized biotech/pharma news digest. It pulls articles from a set of
industry, regulatory, and research RSS feeds, summarizes each one with an
LLM into a consistent set of fields (technology, stage, results, market,
limitations, next steps), scores them against a per-user profile, and
surfaces the result as a Streamlit app — plus an optional weekly email
digest of each user's top stories.

## Features

- **Feed aggregation** — pulls from STAT News, BioPharma Dive, BioSpace,
  Endpoints News, MedCity News, FDA press releases, Nature Biotech, GEN,
  Cell Press, Science, and others (see `RSS_FEEDS` in [config.py](config.py)).
- **AI summaries** — each article is sent to Groq (`openai/gpt-oss-120b`) and
  summarized into fixed fields: technology, stage, results, importance,
  market, limitations, next steps, named company, and a news-tone read
  (positive/negative/neutral/mixed) for that company, grounded strictly in
  what the article says.
- **Company card** — if an article names a company, it's resolved to a stock
  ticker (via yfinance) and shown with live-ish price, market cap, a 6-month
  price chart, and calculated trend indicators (50/200-day moving-average
  trend, 6-month % change, revenue/earnings growth, analyst consensus).
  These are real fetched/computed numbers only — never AI-generated
  predictions or investment advice.
- **Per-user profiles** — onboarding captures technical level, focus areas,
  companies/keywords to watch, which shapes both the AI summaries and the
  article relevance score.
- **Saved articles** — star articles and attach personal notes, stored per
  user.
- **Weekly email digest** — a GitHub Actions workflow sends each user their
  top-scoring articles every Monday.

## Setup

```bash
pip install -r requirements.txt
# create a .env file with the variables below
streamlit run app.py
```

### Environment variables

| Variable         | Required for                      |
|-------------------|------------------------------------|
| `GROQ_API_KEY`     | AI summaries                      |
| `SUPABASE_URL` | user profiles, starred articles (Postgres connection string) |
| `EMAIL_FROM`, `EMAIL_PASSWORD` | sending the digest email (Gmail App Password) |
| `EMAIL_TO`         | GitHub Actions digest job          |
| `APP_URL`          | digest email links back to the app |

On Streamlit Cloud, set these as app secrets instead — `config.py` bridges
`st.secrets` into `os.environ` automatically.

## Project structure

| File | Purpose |
|------|---------|
| `app.py` | Streamlit UI — onboarding, article cards, starring, company cards |
| `fetcher.py` | Downloads and parses the RSS feeds, scrapes full article text |
| `summarizer.py` | Groq prompt + call that produces the structured AI summary |
| `company_data.py` | Resolves a company name to a ticker, fetches market data and fundamentals via yfinance |
| `database.py` | User/profile/starred-article persistence |
| `profiler.py` | Onboarding flow that builds a user's profile |
| `emailer.py` | Builds and sends the weekly digest email |
| `pipeline.py` | Standalone CLI script to test fetch → summarize without the UI |
| `config.py` | Feed list, topic keywords, and env/secrets loading |

## Running the weekly digest manually

```bash
python3 emailer.py
```

This is also run automatically every Monday at 9am UTC by
[.github/workflows/monday_digest.yml](.github/workflows/monday_digest.yml).

## Disclaimer

Company card trend data is sourced from Yahoo Finance (~15 min delayed) or
calculated from it, and news tone reflects only what a given article
states. None of it is a forecast, and nothing in this app is financial
advice.
