# -*- coding: utf-8 -*-
"""
Coach IA Psycho-éducatif (local, perso) — MVP complet
Fonctions:
- Écran consentement + mode doux + bouton "Panic"
- Évaluation initiale (soft) multi-axes + scoring
- Journaling guidé + mini-défis hebdo
- Bibliothèque d'exercices (CBT/ACT/DBT) non médicamenteux
- Coach IA (OpenAI) avec contexte et historique local
- Graphiques d’évolution (matplotlib)
- Stockage local SQLite (SQLAlchemy)
Avertissement: Outil d’auto-soin et d’éducation. Pas un dispositif médical. Pas de diagnostic.
"""

import os
import datetime as dt
from typing import List, Dict

import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine, text

APP_NAME = "Coach IA Psycho-éducatif (MVP perso)"
DB_PATH = "coach_trauma_local.db"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "INSÈRE_TA_CLÉ_ICI")
OPENAI_MODEL = "gpt-4o-mini"

try:
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
except Exception:
    client = None

engine = create_engine(f"sqlite:///{DB_PATH}", future=True)


def init_db():
    with engine.begin() as conn:
        conn.execute(text(
            """
        CREATE TABLE IF NOT EXISTS user_profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            created_at TEXT,
            mode_doux INTEGER DEFAULT 0,
            consent INTEGER DEFAULT 0
        )
        """
        ))
        conn.execute(text(
            """
        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            security_score INTEGER,
            family_score INTEGER,
            siblings_score INTEGER,
            emotional_abuse_score INTEGER,
            self_esteem_score INTEGER,
            conflict_score INTEGER,
            hypervigilance_score INTEGER,
            dissociation_score INTEGER,
            impact_now_score INTEGER,
            total_score INTEGER
        )
        """
        ))
        conn.execute(text(
            """
        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            trigger TEXT,
            thoughts TEXT,
            reframed TEXT,
            action TEXT,
            gratitude TEXT
        )
        """
        ))
        conn.execute(text(
            """
        CREATE TABLE IF NOT EXISTS coach_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            role TEXT,
            content TEXT
        )
        """
        ))
        conn.execute(text(
            """
        CREATE TABLE IF NOT EXISTS challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            title TEXT,
            done INTEGER
        )
        """
        ))
        conn.execute(text(
            """
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            goal TEXT
        )
        """
        ))
        conn.execute(text(
            """
        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            title TEXT,
            note TEXT
        )
        """
        ))


def get_user_profile():
    with engine.begin() as conn:
        row = conn.execute(text("SELECT id, mode_doux, consent FROM user_profile WHERE id=1")).fetchone()
        if not row:
            conn.execute(
                text(
                    "INSERT INTO user_profile (id, created_at, mode_doux, consent) VALUES (1, :created, 0, 0)"
                ),
                {"created": dt.datetime.utcnow().isoformat()},
            )
            return {"mode_doux": 0, "consent": 0}
        return {"mode_doux": row[1], "consent": row[2]}


def set_user_profile(mode_doux: int | None = None, consent: int | None = None):
    with engine.begin() as conn:
        if mode_doux is not None:
            conn.execute(text("UPDATE user_profile SET mode_doux=:md WHERE id=1"), {"md": mode_doux})
        if consent is not None:
            conn.execute(text("UPDATE user_profile SET consent=:c WHERE id=1"), {"c": consent})


LIKERT = {
    "Jamais": 0,
    "Rarement": 1,
    "Parfois": 2,
    "Souvent": 3,
    "Très souvent": 4,
}


def likert_input(label, key):
    return st.select_slider(label, options=list(LIKERT.keys()), value="Parfois", key=key)


def panic_button():
    st.warning("Besoin d’une pause immédiate ?")
    if st.button("PANIC — J’ai besoin d’une pause"):
        st.session_state["panic"] = True


def render_panic_screen():
    st.header("Calm Space")
    st.write("Respire doucement. Inspire 4 temps, expire 6 temps. Répète 1 minute.")
    st.audio(data=None, format="audio/wav")
    st.markdown(
        """
    **Ancrage 5-4-3-2-1**  
    - Regarde 5 choses  
    - Touche 4 textures  
    - Écoute 3 sons  
    - Sens 2 odeurs  
    - Goûte 1 chose
    """
    )
    if st.button("Reprendre"):
        st.session_state["panic"] = False


def section_divider():
    st.markdown("---")


ASSESSMENT_QUESTIONS = {
    "Sécurité passée": [
        "Enfant, te sentais-tu en sécurité à la maison ?",
        "Enfance: avais-tu un adulte de confiance à qui parler ?",
    ],
    "Relations familiales": [
        "A-t-on souvent minimisé tes émotions ou besoins ?",
        "Te sentais-tu entendu·e quand tu étais en détresse ?",
    ],
    "Fratrie": [
        "Un frère/une sœur t’a-t-il déjà fait peur ou blessé·e ?",
        "Conflits fratricides t’ont-ils souvent épuisé·e ?",
    ],
    "Abus émotionnel": [
        "A-t-on utilisé moqueries, humiliations ou menaces envers toi ?",
        "T’es-tu souvent senti·e honteux·se ‘d’exister’ chez toi ?",
    ],
    "Estime de soi": [
        "As-tu intériorisé ‘je suis nul·le / de trop’ ?",
        "Te sens-tu rarement ‘suffisant·e’ comme tu es ?",
    ],
    "Conflit / autorité": [
        "Quand quelqu’un se fâche, ton corps panique-t-il ?",
        "Évites-tu d’exprimer des limites par peur de réactions ?",
    ],
    "Hypervigilance": [
        "Surveilles-tu beaucoup l’ambiance et les gens autour de toi ?",
        "Les bruits soudains te crispent-ils longtemps ?",
    ],
    "Dissociation": [
        "As-tu parfois l’impression d’être ‘déconnecté·e’ de toi-même ?",
        "Te sens-tu parfois ‘vide’ quand c’est trop intense ?",
    ],
    "Impact actuel": [
        "Des situations actuelles réveillent-elles des peurs anciennes ?",
        "Cela affecte-t-il tes relations, études, travail aujourd’hui ?",
    ],
}

CATEGORIES = list(ASSESSMENT_QUESTIONS.keys())


EXERCISES = [
    {
        "title": "Restructuration cognitive (CBT)",
        "steps": [
            "Identifie la pensée automatique: ‘Je suis nul·le’.",
            "Preuves pour/contre: note 3 faits contre cette pensée.",
            "Reformulation équilibrée: ‘Je traverse un moment difficile, ça ne définit pas ma valeur.’",
        ],
    },
    {
        "title": "Ancrage sensoriel 5-4-3-2-1 (DBT)",
        "steps": [
            "Regarde 5 choses autour de toi.",
            "Touche 4 textures différentes.",
            "Écoute 3 sons.",
            "Sens 2 odeurs.",
            "Goûte 1 chose.",
        ],
    },
    {
        "title": "Respiration 4-6",
        "steps": [
            "Inspire 4 temps par le nez.",
            "Expire 6 temps par la bouche.",
            "Répète 10 cycles, épaules détendues.",
        ],
    },
    {
        "title": "Auto-compassion (ACT)",
        "steps": [
            "Décris la situation douloureuse.",
            "Imagine ce que tu dirais à un.e ami.e dans la même situation.",
            "Écris cette réponse bienveillante pour toi.",
        ],
    },
    {
        "title": "Exposition graduelle douce",
        "steps": [
            "Choisis une peur minuscule (niveau 2/10).",
            "Exposition 5 minutes avec respiration 4-6.",
            "Note le niveau d’anxiété avant/après.",
        ],
    },
]

WEEKLY_CHALLENGES = [
    "Dire ‘non’ à une micro-demande qui déborde tes limites.",
    "Planifier 15 min d’activité plaisante sans culpabilité.",
    "Écrire 3 phrases de gratitude réaliste.",
    "Exprimer clairement un besoin à une personne safe.",
    "Faire 10 cycles de respiration 4-6 avant un conflit.",
]

SYSTEM_PROMPT = """Tu es un coach IA psycho-éducatif, bienveillant, concret, non médical.\nTu aides l’utilisateur à:\n- Observer ses déclencheurs (triggers)\n- Restructurer ses pensées (CBT)\n- Pratiquer des exercices (DBT/ACT)\n- Construire des habitudes saines\nTu ne poses aucun diagnostic. Tu évites les étiquettes. Tu normalises sans banaliser.\nToujours proposer: petit pas concret + validation + option de pause si c’est trop.\nLangue: Français. Ton: clair, chaleureux, direct.\n"""


def coach_reply(messages: List[Dict[str, str]]) -> str:
    if client is None or OPENAI_API_KEY.startswith("INSÈRE"):
        return "⚠️ Configure OPENAI_API_KEY pour activer le coach IA."
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.6,
            max_tokens=700,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:  # pragma: no cover - dépend de l’API
        return f"Erreur API: {exc}"


def add_chat_message(role: str, content: str):
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO coach_messages (created_at, role, content) VALUES (:ts, :r, :c)"
            ),
            {"ts": dt.datetime.utcnow().isoformat(), "r": role, "c": content},
        )


def load_chat_history(limit: int = 20) -> List[Dict[str, str]]:
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT role, content FROM coach_messages ORDER BY id DESC LIMIT :lim"),
            {"lim": limit},
        ).fetchall()
    hist = [{"role": r[0], "content": r[1]} for r in rows][::-1]
    return [{"role": "system", "content": SYSTEM_PROMPT}] + hist


def page_consent_and_settings():
    st.subheader("Consentement & Réglages")
    st.write(
        "Cet outil est une expérience **d’auto-soin** et de **psycho-éducation**. Il ne remplace pas une prise en charge médicale. Thèmes sensibles possibles. Tu peux arrêter à tout moment."
    )
    profile = get_user_profile()
    mode_doux = st.checkbox(
        "Activer le **Mode doux** (questions plus légères, feedback minimal)",
        value=bool(profile["mode_doux"]),
    )
    consent = st.checkbox(
        "Je comprends les limites et j’accepte d’utiliser l’outil pour mon usage personnel.",
        value=bool(profile["consent"]),
    )
    if st.button("Enregistrer"):
        set_user_profile(mode_doux=int(mode_doux), consent=int(consent))
        st.success("Préférences enregistrées.")

    section_divider()
    st.markdown("### Ressources d’aide")
    st.markdown(
        """
- Urgences: **112**
- Prévention Suicide (France): **3114**
- Enfance en danger: **119**
- Écoute (S.O.S Amitié): 09 72 39 40 50
    """
    )


def page_assessment():
    st.subheader("Évaluation initiale (soft)")
    panic_button()
    if st.session_state.get("panic"):
        render_panic_screen()
        return

    profile = get_user_profile()
    if not profile["consent"]:
        st.info("Valide le consentement dans l’onglet ‘Consentement & Réglages’.")
        return

    answers: Dict[str, int] = {}
    for cat in CATEGORIES:
        with st.expander(cat, expanded=False):
            for idx, question in enumerate(ASSESSMENT_QUESTIONS[cat]):
                key = f"{cat}_{idx}"
                ans = likert_input(question, key)
                answers[key] = LIKERT[ans]
    if st.button("Calculer mon profil"):
        scores: Dict[str, int] = {}
        for cat in CATEGORIES:
            keys = [k for k in answers if k.startswith(cat)]
            scores[cat] = int(np.sum([answers[k] for k in keys]))
        total = int(sum(scores.values()))
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
            INSERT INTO assessments (created_at, security_score, family_score, siblings_score, emotional_abuse_score,
                                     self_esteem_score, conflict_score, hypervigilance_score, dissociation_score,
                                     impact_now_score, total_score)
            VALUES (:ts, :s1, :s2, :s3, :s4, :s5, :s6, :s7, :s8, :s9, :tot)
                    """
                ),
                {
                    "ts": dt.datetime.utcnow().isoformat(),
                    "s1": scores["Sécurité passée"],
                    "s2": scores["Relations familiales"],
                    "s3": scores["Fratrie"],
                    "s4": scores["Abus émotionnel"],
                    "s5": scores["Estime de soi"],
                    "s6": scores["Conflit / autorité"],
                    "s7": scores["Hypervigilance"],
                    "s8": scores["Dissociation"],
                    "s9": scores["Impact actuel"],
                    "tot": total,
                },
            )
        st.success("Profil enregistré.")
        section_divider()
        st.markdown("### Restitution bienveillante")
        for cat in CATEGORIES:
            val = scores[cat]
            if val >= 6:
                tone = "élevée"
            elif val >= 3:
                tone = "modérée"
            else:
                tone = "basse"
            st.write(f"- Ta sensibilité **{cat.lower()}** semble **{tone}** (score {val}).")
        st.info("Ceci n’est pas un diagnostic. Tu peux explorer des exercices apaisants dans l’onglet ‘Exercices’.")


def page_progress():
    st.subheader("Progression")
    with engine.begin() as conn:
        df = pd.read_sql("SELECT * FROM assessments ORDER BY id ASC", conn)
    if df.empty:
        st.info("Pas encore de données. Fais une première évaluation.")
        return

    df["date"] = pd.to_datetime(df["created_at"]).dt.date
    metric_cols = [
        "security_score",
        "family_score",
        "siblings_score",
        "emotional_abuse_score",
        "self_esteem_score",
        "conflict_score",
        "hypervigilance_score",
        "dissociation_score",
        "impact_now_score",
        "total_score",
    ]
    selected = st.multiselect(
        "Choisis les axes à afficher", metric_cols, default=["total_score"]
    )
    if not selected:
        st.warning("Sélectionne au moins une métrique.")
        return

    fig = plt.figure()
    for column in selected:
        plt.plot(df["date"], df[column], marker="o", label=column)
    plt.xticks(rotation=45)
    plt.title("Évolution des sensibilités")
    plt.legend()
    st.pyplot(fig)


def page_journal():
    st.subheader("Journal guidé")
    panic_button()
    if st.session_state.get("panic"):
        render_panic_screen()
        return

    with st.form("journal_form"):
        trigger = st.text_area("Déclencheur (ce qui t’a activé·e récemment)", "")
        thoughts = st.text_area("Pensées automatiques (les phrases qui ont poppé)", "")
        reframed = st.text_area("Reformulation plus équilibrée (version plus juste)", "")
        action = st.text_area("Action minuscule que tu peux faire", "")
        gratitude = st.text_area("Gratitude réaliste (3 choses si possible)", "")
        submit = st.form_submit_button("Enregistrer")
    if submit:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
            INSERT INTO journal (created_at, trigger, thoughts, reframed, action, gratitude)
            VALUES (:ts, :tr, :th, :re, :ac, :gr)
                    """
                ),
                {
                    "ts": dt.datetime.utcnow().isoformat(),
                    "tr": trigger,
                    "th": thoughts,
                    "re": reframed,
                    "ac": action,
                    "gr": gratitude,
                },
            )
        st.success("Journal enregistré.")

    section_divider()
    st.markdown("### Historique")
    with engine.begin() as conn:
        df = pd.read_sql(
            "SELECT created_at, trigger, reframed, action, gratitude FROM journal ORDER BY id DESC",
            conn,
        )
    if df.empty:
        st.info("Ton journal est vide.")
    else:
        st.dataframe(df, use_container_width=True)


def page_exercises():
    st.subheader("Exercices psycho-éducatifs")
    panic_button()
    if st.session_state.get("panic"):
        render_panic_screen()
        return

    for exercise in EXERCISES:
        with st.expander(exercise["title"]):
            for idx, step in enumerate(exercise["steps"], start=1):
                st.write(f"{idx}. {step}")

    section_divider()
    st.markdown("### Défis hebdomadaires")
    choice = st.selectbox("Choisis un défi pour cette semaine", WEEKLY_CHALLENGES)
    if st.button("Marquer comme fait"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO challenges (created_at, title, done) VALUES (:ts, :t, 1)"
                ),
                {"ts": dt.datetime.utcnow().isoformat(), "t": choice},
            )
        st.success("Bravo. Petits pas, vrai impact.")


def page_goals():
    st.subheader("Objectifs personnels")
    with st.form("goals_form"):
        goal = st.text_input(
            "Un objectif simple (ex: poser une limite au travail sans m’excuser)"
        )
        submitted = st.form_submit_button("Ajouter")
    if submitted and goal.strip():
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO goals (created_at, goal) VALUES (:ts, :g)"),
                {"ts": dt.datetime.utcnow().isoformat(), "g": goal.strip()},
            )
        st.success("Objectif ajouté.")

    section_divider()
    with engine.begin() as conn:
        df = pd.read_sql("SELECT created_at, goal FROM goals ORDER BY id DESC", conn)
    if df.empty:
        st.info("Aucun objectif enregistré.")
    else:
        st.dataframe(df, use_container_width=True)


def page_coach():
    st.subheader("Coach IA")
    panic_button()
    if st.session_state.get("panic"):
        render_panic_screen()
        return

    st.caption("Le coach utilise un modèle IA pour proposer des pistes. Zéro diagnostic.")
    user_input = st.text_area("Dis au coach ce qui se passe (trigger, pensée, situation).")
    if st.button("Envoyer au coach"):
        if user_input.strip():
            add_chat_message("user", user_input.strip())
            history = load_chat_history(limit=30)
            reply = coach_reply(history)
            add_chat_message("assistant", reply)
            st.success("Réponse générée.")

    section_divider()
    st.markdown("### Conversation")
    with engine.begin() as conn:
        df = pd.read_sql(
            "SELECT created_at, role, content FROM coach_messages ORDER BY id DESC LIMIT 50",
            conn,
        )
    if df.empty:
        st.info("Aucun échange. Écris au coach pour commencer.")
    else:
        for _, row in df.iloc[::-1].iterrows():
            role = row["role"]
            content = row["content"]
            if role == "user":
                st.markdown(f"**Toi:** {content}")
            elif role == "assistant":
                st.markdown(f"**Coach:** {content}")
            else:
                st.markdown(f"*{role}*: {content}")


def main():
    st.set_page_config(page_title=APP_NAME, page_icon="🧭", layout="wide")
    st.title(APP_NAME)
    st.caption("Outil d’auto-soin. Pas un dispositif médical. Arrête si tu te sens mal.")

    init_db()
    if "panic" not in st.session_state:
        st.session_state["panic"] = False

    tabs = st.tabs(
        [
            "Consentement & Réglages",
            "Évaluation",
            "Progression",
            "Journal",
            "Exercices",
            "Objectifs",
            "Coach IA",
        ]
    )

    with tabs[0]:
        page_consent_and_settings()
    with tabs[1]:
        page_assessment()
    with tabs[2]:
        page_progress()
    with tabs[3]:
        page_journal()
    with tabs[4]:
        page_exercises()
    with tabs[5]:
        page_goals()
    with tabs[6]:
        page_coach()

    st.markdown("---")
    st.caption("En cas de détresse, contacte des professionnels. Tu n’es pas seul·e.")


if __name__ == "__main__":
    main()
