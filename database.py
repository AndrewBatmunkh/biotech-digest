# database.py — PostgreSQL (Supabase) database for Biotech Digest
# handles all read/write operations for users, profiles, and starred articles
# every other file imports from here — nothing touches the DB directly

import psycopg2 # postgres driver
import json # converts to list to strings
import datetime # time
import os #file path
from dotenv import load_dotenv

load_dotenv()  
DATABASE_URL = os.getenv("SUPABASE_URL") 

# SETUP--> WONT OVERWRITE
def init_db():
    """Create all tables if they don't already exist."""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor() 

    # users table — one row = one person 
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id         SERIAL PRIMARY KEY,
            full_name  TEXT NOT NULL,
            email      TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        )
    """)

    # profiles table — onboarding answers linked to a user
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            id               SERIAL PRIMARY KEY,
            user_id          INTEGER NOT NULL UNIQUE,
            technical_level  TEXT,
            focus_areas      TEXT,
            what_matters     TEXT,
            companies        TEXT,
            keywords         TEXT,
            digest_frequency TEXT,
            created_at       TEXT,
            last_updated     TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # starred table — saved articles linked to a user
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS starred (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER NOT NULL,
            title       TEXT NOT NULL,
            source      TEXT,
            url         TEXT NOT NULL,
            published   TEXT,
            saved_at    TEXT NOT NULL,
            note        TEXT DEFAULT '',
            ai_summary  TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # unique index ensures ON CONFLICT DO NOTHING actually deduplicates
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_starred_user_url
        ON starred(user_id, url)
    """)

    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# USER OPERATIONS


def create_user(full_name, email):
    """
    Create a new user. Returns the new user's id.
    If email already exists, returns the existing user's id.
  
    """
    email = email.strip().lower()
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO users (full_name, email, created_at)
            VALUES (%s, %s, %s)
            RETURNING id
        """, (full_name, email, datetime.datetime.now().isoformat()))
        user_id = cursor.fetchone()[0]  # Postgres has no lastrowid — RETURNING id gives it back
        conn.commit()
        print(f"✅ User created: {full_name}")
        return user_id

    except psycopg2.IntegrityError:
        # email already exists — get existing user's id
        conn.rollback()  # Postgres aborts the transaction on error — must roll back before reusing the connection
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        row = cursor.fetchone()
        return row[0] if row else None

    finally:
        conn.close()  # always close connection even if error occurs


def get_user(user_id):
    """Get a user by id. Returns a dict or None."""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, full_name, email, created_at FROM users WHERE id = %s",
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id":         row[0],
            "full_name":  row[1],
            "email":      row[2],
            "created_at": row[3]
        }
    return None


def get_all_users():
    """Get every user in the database — used to send each person their own digest."""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT id, full_name, email, created_at FROM users")
    rows = cursor.fetchall()
    conn.close()

    return [
        {"id": row[0], "full_name": row[1], "email": row[2], "created_at": row[3]}
        for row in rows
    ]


def get_user_by_email(email):
    """Look up a user by email (case-insensitive). Returns a dict or None."""
    email = email.strip().lower()
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, full_name, email, created_at FROM users WHERE email = %s",
        (email,)
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id":         row[0],
            "full_name":  row[1],
            "email":      row[2],
            "created_at": row[3]
        }
    return None


# ─────────────────────────────────────────────
# PROFILE OPERATIONS
# ─────────────────────────────────────────────

def save_profile(user_id, technical_level, focus_areas,
                 what_matters, companies, keywords, digest_frequency):
    """
    Save or update onboarding answers for a user.
    Uses INSERT ... ON CONFLICT DO UPDATE so it works for both new and returning users.
    focus_areas and what_matters are lists — stored as JSON strings.
    """
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()

    cursor.execute("""
        INSERT INTO profiles
        (user_id, technical_level, focus_areas, what_matters,
         companies, keywords, digest_frequency, created_at, last_updated)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET
            technical_level  = EXCLUDED.technical_level,
            focus_areas      = EXCLUDED.focus_areas,
            what_matters     = EXCLUDED.what_matters,
            companies        = EXCLUDED.companies,
            keywords         = EXCLUDED.keywords,
            digest_frequency = EXCLUDED.digest_frequency,
            created_at       = EXCLUDED.created_at,
            last_updated     = EXCLUDED.last_updated
    """, (
        user_id,
        technical_level,
        json.dumps(focus_areas),    # convert list to JSON string
        json.dumps(what_matters),   # convert list to JSON string
        companies,
        keywords,
        digest_frequency,
        now,
        now
    ))

    conn.commit()
    conn.close()
    print(f"✅ Profile saved for user {user_id}")


def get_profile(user_id):
    """
    Get profile for a user. Returns a dict or None.
    Converts JSON strings back to Python lists automatically.
    """
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT technical_level, focus_areas, what_matters,
               companies, keywords, digest_frequency,
               created_at, last_updated
        FROM profiles WHERE user_id = %s
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "technical_level":  row[0],
            "focus_areas":      json.loads(row[1]) if row[1] else [],
            "what_matters":     json.loads(row[2]) if row[2] else [],
            "companies":        row[3] or "",
            "keywords":         row[4] or "",
            "digest_frequency": row[5],
            "created_at":       row[6],
            "last_updated":     row[7]
        }
    return None


def profile_exists(user_id):
    """Quick check — does this user have a profile yet?"""
    return get_profile(user_id) is not None


# ─────────────────────────────────────────────
# STARRED ARTICLE OPERATIONS
# ─────────────────────────────────────────────

def star_article(user_id, article):
    """
    Save an article to starred. Silently ignores if already starred
    (DO NOTHING means don't crash on duplicate URL).
    article is a dict from fetcher.py with ai_summary added.
    """
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO starred
            (user_id, title, source, url, published, saved_at, note, ai_summary)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, url) DO NOTHING
        """, (
            user_id,
            article.get("title", ""),
            article.get("source", ""),
            article.get("url", ""),
            str(article.get("published", "")),
            datetime.datetime.now().isoformat(),
            "",  # empty note by default
            json.dumps(article.get("ai_summary", {}))
        ))
        conn.commit()
        print(f"⭐ Starred: {article.get('title', '')[:50]}")

    finally:
        conn.close()


def unstar_article(user_id, url):
    """Remove an article from starred by URL."""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM starred WHERE user_id = %s AND url = %s",
        (user_id, url)
    )
    conn.commit()
    conn.close()
    print(f"✅ Unstarred article")


def is_starred(user_id, url):
    """Check if a specific article is already starred. Returns True/False."""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM starred WHERE user_id = %s AND url = %s",
        (user_id, url)
    )
    row = cursor.fetchone()
    conn.close()
    return row is not None  # True if found, False if not


def get_starred(user_id):
    """
    Get all starred articles for a user, newest first.
    Returns a list of dicts.
    """
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT title, source, url, published, saved_at, note, ai_summary
        FROM starred
        WHERE user_id = %s
        ORDER BY saved_at DESC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()

    articles = []
    for row in rows:
        articles.append({
            "title":      row[0],
            "source":     row[1],
            "url":        row[2],
            "published":  row[3],
            "saved_at":   row[4],
            "note":       row[5],
            "ai_summary": json.loads(row[6]) if row[6] else {}
        })
    return articles


def update_note(user_id, url, note):
    """Update the personal note on a starred article."""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE starred SET note = %s WHERE user_id = %s AND url = %s",
        (note, user_id, url)
    )
    conn.commit()
    conn.close()


def get_starred_count(user_id):
    """Returns how many articles are starred — used for sidebar badge."""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM starred WHERE user_id = %s",
        (user_id,)
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count


# ─────────────────────────────────────────────
# TEST BLOCK — only runs with: python3 database.py
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing PostgreSQL (Supabase) database...")

    # initialise database
    init_db()

    # create a test user
    user_id = create_user("Andrew", "andrew@email.com")
    print(f"User ID: {user_id}")

    # save a test profile
    save_profile(
        user_id=user_id,
        technical_level="Expert",
        focus_areas=["Gene & Cell Therapy", "Oncology"],
        what_matters=["The science", "The data"],
        companies="Moderna, Pfizer",
        keywords="liquid biopsy, CAR-T",
        digest_frequency="Weekly"
    )

    # read it back
    profile = get_profile(user_id)
    print(f"\nProfile: {profile}")

    # test starring an article
    test_article = {
        "title":      "CRISPR shows promise in lung cancer",
        "source":     "STAT News",
        "url":        "https://statnews.com/test",
        "published":  "2026-05-23",
        "ai_summary": {"technology": "CRISPR-Cas9...", "results": "45% ORR"}
    }
    star_article(user_id, test_article)

    # check if starred
    print(f"\nIs starred: {is_starred(user_id, 'https://statnews.com/test')}")

    # get all starred
    starred = get_starred(user_id)
    print(f"Starred count: {len(starred)}")
    print(f"First starred: {starred[0]['title']}")

    print("\n✅ All PostgreSQL database tests passed")
