import os
from dotenv import load_dotenv
load_dotenv()  # reads the .env file

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")


#RSS feeds
#a list of tuples, where in each tuple --> a name u see in the UI and the RSS URL
RSS_FEEDS = [
    # Industry news
    ("STAT News",           "https://www.statnews.com/feed/"),
    ("BioPharma Dive",      "https://www.biopharmadive.com/feeds/news/"),
    ("Fierce Biotech",      "https://www.fiercebiotech.com/rss/xml"),
    ("Endpoints News",      "https://endpts.com/feed/"),
    ("MedCity News",        "https://medcitynews.com/feed/"),
    ("PharmaLive",          "https://www.pharmalive.com/feed/"),
    # Regulatory
    ("FDA News Releases",   "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml"),
    # Research journals
    ("Nature Biotech News", "https://www.nature.com/nbt.rss"),
    ("GenomeWeb",           "https://www.genomeweb.com/rss/all"),
    ("Cell Press (Cell)",   "https://www.cell.com/cell/inpress.rss"),
    ("Science (AAAS)",      "https://www.science.org/rss/news_current.xml"),
]


#For the topics where the sources we will pull out from --> a dictionary
#Key =  topics name shown in UI, Value = list of keywoards to match in articles
#Matching ins case sensitive --> CRISPR --> crispr, cas 9, etc
TOPICS = {
    "All":              [],

    # Therapeutic modalities
    "CRISPR":           ["crispr", "cas9", "cas12", "base edit", "prime edit", "gene edit"],
    "Gene Therapy":     ["gene therapy", "aav", "adeno-associated", "viral vector", "lentiviral", "ex vivo"],
    "RNA / mRNA":       ["mrna", "rna therapy", "antisense", "sirna", "rnai", "oligonucleotide"],
    "Cell Therapy":     ["car-t", "car t", "cell therapy", "tcr", "nk cell", "stem cell", "ipsc"],
    "Antibody":         ["antibody", "monoclonal", "bispecific", "adc", "antibody-drug conjugate", "nanobody"],

    # Disease areas
    "Cancer":           ["cancer", "oncology", "tumor", "tumour", "immunotherapy", "checkpoint", "leukemia", "lymphoma"],
    "Rare Disease":     ["rare disease", "orphan", "ultra-rare", "unmet need"],
    "Neuroscience":     ["neurology", "neuroscience", "alzheimer", "parkinson", "neurodegeneration", "cns", "brain"],
    "Infectious Disease": ["infectious", "vaccine", "antiviral", "antimicrobial", "pathogen", "pandemic"],

    # Research & technology
    "Genomics":         ["genomic", "sequencing", "whole genome", "exome", "proteomics", "multi-omics", "single cell"],
    "Diagnostics":      ["diagnostic", "biomarker", "assay", "liquid biopsy", "companion diagnostic", "point-of-care"],
    "AI & Drug Discovery": ["artificial intelligence", "machine learning", "deep learning", "ai-driven", "generative", "drug discovery platform"],

    # Business & regulatory
    "Drug Development": ["phase 1", "phase 2", "phase 3", "clinical trial", "ind ", "nda", "bla", "pivotal"],
    "FDA / Regulatory": ["fda", "approval", "approved", "ema", "breakthrough therapy", "fast track", "priority review", "pdufa"],
    "Acquisitions":     ["acqui", "merger", "deal", "buyout", "partnership", "license agreement", "collaboration"],
    "Funding":          ["series a", "series b", "series c", "ipo", "raised", "funding", "venture", "investment"],
}
# how many articles to grap per feed, 10 feeds, 10 articles
MAX_ARTICLES_PER_FEED = 3

#how long streamlit remembers fetched articesl before redownloading( in seconds)
CACHE_TTL_SECONDS = 1800

# set Email enabled to true when ready toset up the daily digest feature
#leave everything else as is, untul day 7 --> whenwe tackle email

EMAIL_ENABLED  = False
EMAIL_FROM     = os.getenv("EMAIL_FROM", "")      # Your Gmail address
EMAIL_TO       = os.getenv("EMAIL_TO", "")        # Where digest gets sent (can be same as above)
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")  # Gmail App Password — NOT your real password
SMTP_HOST      = "smtp.gmail.com"                  # Gmail's mail server — don't change this
SMTP_PORT      = 587                               # Standard email port — don't change this
TOP_N_FOR_DIGEST = 5   