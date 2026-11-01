# profiler.py — onboarding UI
# shows 5 personalisation questions on first launch
# saves answers to SQLite database via database.py
# never shown again once profile exists

import streamlit as st
from database import create_user, save_profile

# onboarding questions and options
TECHNICAL_LEVELS = [
    "Beginner      — I'm new to biotech, keep it simple",
    "Intermediate  — I know the basics, some jargon is fine",
    "Expert        — Give me full molecular and clinical detail",
]

FOCUS_AREAS = [
    "Gene & Cell Therapy    — CRISPR, AAV, CAR-T, RNA, gene editing",
    "Oncology               — Cancer, tumors, immunotherapy, diagnostics",
    "Emerging Biology       — Synthetic bio, microbiome, longevity, aging",
    "Rare & Neurological    — Rare disease, Alzheimer's, Parkinson's, CNS",
    "Digital & Precision    — AI diagnostics, wearables, biomarkers, healthtech",
    "Business & Industry    — Deals, funding, FDA, acquisitions, VC, IPOs",
]

WHAT_MATTERS = [
    "The science        — How it works, mechanism, technology, biology",
    "The data           — Numbers, trial results, outcomes, statistics",
    "The opportunity    — Market size, commercial potential, next steps",
    "The patient impact — Why it matters, who it helps, clinical need",
    "The competition    — Who else is working on this, landscape",
    "The risk           — What could go wrong, safety, regulatory hurdles",
]

DIGEST_FREQUENCY = [
    "Weekly  — Monday morning digest, curated top 15",
    "Off     — I'll use the app directly, no emails",
]

#main prompt template for the AI summarizer — this is where the user profile is injected
def show_onboarding(default_email=""):
    """
    Renders the full onboarding UI.
    default_email pre-fills the email field — used when the identity gate in
    app.py already knows this is a brand-new email and is handing off here.
    Returns True when the user submits — signals app.py to reload.
    Returns False while still filling in the form.
    """
    
    st.markdown("""
        <div style="text-align: center; padding: 40px 0 20px 0;">
            <h1 style="font-size: 2.5rem;">🧬 Biotech Digest</h1>
            <p style="font-size: 1.1rem; opacity: 0.7;">
                Your personalised AI-powered weekly briefing.
                Answer 5 quick questions to tailor your digest.
            </p>
        </div>
    """, unsafe_allow_html=True)

    st.divider()
    
    # ── name and email ──
    st.subheader("First, tell us who you are")
    col1, col2 = st.columns(2)
    with col1:
        full_name = st.text_input(
            "Full name",
            placeholder="Andrew Batmunkh"
        )
    with col2:
        email = st.text_input(
            "Email address",
            value=default_email,
            placeholder="andrew@email.com"
        )

    st.divider()

    # ── Q1 — technical level ──
    st.subheader("Q1 — How technical do you want your summaries?")
    technical_choice = st.radio(
        label="technical_level",
        options=TECHNICAL_LEVELS,
        label_visibility="collapsed"
    )

    st.divider()

    # ── Q2 — focus areas ──
    st.subheader("Q2 — What areas of biotech interest you?")
    st.caption("Select as many as you want")
    focus_choices = []
    for area in FOCUS_AREAS:
        if st.checkbox(area, key=f"focus_{area}"):
            focus_choices.append(area)

    st.divider()

    # ── Q3 — what matters most ──
    st.subheader("Q3 — What matters most to you in an article?")
    st.caption("Select all that apply")
    matters_choices = []
    for matter in WHAT_MATTERS:
        if st.checkbox(matter, key=f"matter_{matter}"):
            matters_choices.append(matter)

    st.divider()

    # ── Q4 — keywords and companies ──
    st.subheader("Q4 — Any companies or keywords to track?")
    st.caption("Optional — separate with commas")
    col3, col4 = st.columns(2)
    with col3:
        companies = st.text_input(
            "Companies to watch",
            placeholder="Moderna, Pfizer, Recursion"
        )
    with col4:
        keywords = st.text_input(
            "Keywords to flag",
            placeholder="liquid biopsy, CAR-T, GLP-1"
        )

    st.divider()

    # ── Q5 — digest frequency ──
    st.subheader("Q5 — How often do you want your digest?")
    frequency_choice = st.radio(
        label="digest_frequency",
        options=DIGEST_FREQUENCY,
        label_visibility="collapsed"
    )

    st.divider()

    # ── validation and submit ──
    # check required fields before allowing submission
    errors = []
    if st.button("Build my digest →", type="primary", use_container_width=True):

        # validate required fields
        if not full_name.strip():
            errors.append("Please enter your full name")
        if not email.strip():
            errors.append("Please enter your email address")
        if not technical_choice:
            errors.append("Please select a technical level")
        if not focus_choices:
            errors.append("Please select at least one focus area")

        if errors:
            for error in errors:
                st.error(error)
            return False

        # ── save to database ──
        # extract just the label before the dash for cleaner storage
        # "Expert        — Give me full..." → "Expert"
        technical_level = technical_choice.split("—")[0].strip()
        digest_frequency = frequency_choice.split("—")[0].strip()

        # clean up focus and matters labels the same way
        focus_areas = [f.split("—")[0].strip() for f in focus_choices]
        what_matters = [m.split("—")[0].strip() for m in matters_choices]

        # save user to database first — get back their id
        user_id = create_user(full_name.strip(), email.strip())

        if user_id is None:
            st.error("Something went wrong saving your profile. Please try again.")
            return False

        # save profile linked to that user
        save_profile(
            user_id=user_id,
            technical_level=technical_level,
            focus_areas=focus_areas,
            what_matters=what_matters,
            companies=companies.strip(),
            keywords=keywords.strip(),
            digest_frequency=digest_frequency
        )

        # success message
        st.success(f"Welcome {full_name.split()[0]}! Building your digest...")
        st.balloons()

        # store user_id in session state so app.py knows who's logged in
        st.session_state["user_id"] = user_id
        st.session_state["user_name"] = full_name.split()[0]

        return True 

    return False 