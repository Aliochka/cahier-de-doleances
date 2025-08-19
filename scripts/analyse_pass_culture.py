#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ================= Imports =================
import os, re
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import spacy
from wordcloud import WordCloud
import stopwordsiso as stopiso

from sklearn.cluster import MiniBatchKMeans
from sklearn.feature_extraction.text import TfidfVectorizer

from transformers import pipeline, XLMRobertaTokenizer, AutoModelForSequenceClassification

# --- (optionnel mais recommandé) BERTopic ---
BER_TOPIC_AVAILABLE = True
try:
    from bertopic import BERTopic
    from sentence_transformers import SentenceTransformer
    from hdbscan import HDBSCAN
except Exception:
    BER_TOPIC_AVAILABLE = False

# ================= Paths / config =================
IN_CSV  = "data/pass_culture.csv"      # colonnes: id,title,text
OUT_DIR = "analyse"
os.makedirs(OUT_DIR, exist_ok=True)

SNIPPETS_CSV        = os.path.join(OUT_DIR, "pass_snippets.csv")
SENTIMENT_CSV       = os.path.join(OUT_DIR, "pass_snippets_sentiment.csv")
CLUSTERS_CSV        = os.path.join(OUT_DIR, "pass_snippets_clusters.csv")
CLUSTER_TERMS_CSV   = os.path.join(OUT_DIR, "pass_snippets_cluster_terms.csv")
CROSSTAB_CSV        = os.path.join(OUT_DIR, "pass_snippets_theme_x_sentiment.csv")
WC_POSITIVE_PNG     = os.path.join(OUT_DIR, "pass_snippets_wc_positive.png")
WC_NEGATIVE_PNG     = os.path.join(OUT_DIR, "pass_snippets_wc_negative.png")

# BERTopic HTML
BT_TOPICS_HTML      = os.path.join(OUT_DIR, "pass_snippets_topics.html")
BT_BARCHART_HTML    = os.path.join(OUT_DIR, "pass_snippets_topics_barchart.html")
BT_HIER_HTML        = os.path.join(OUT_DIR, "pass_snippets_topics_hierarchy.html")
BT_DOCS_HTML        = os.path.join(OUT_DIR, "pass_snippets_documents.html")

# Clustering léger
N_CLUSTERS = 6
TOP_TERMS  = 12

# ================= 1) Lire & segmenter en phrases =================
df = pd.read_csv(IN_CSV)
df["text"] = df["text"].astype(str).fillna("")
print(f"{len(df)} contributions chargées depuis {IN_CSV}")

nlp = spacy.load("fr_core_news_sm", disable=["ner","tagger","lemmatizer"])
nlp.enable_pipe("senter")

KEY_PATTERNS = [
    r"\bpass[-\s]?culture\b",
    r"\bjeun(?:e|esse|es)\b",
    r"\bmjc\b",
    r"\béducation populaire\b",
    r"\bétudiant(?:e|s)?\b|\betudiant(?:e|s)?\b",
    r"\blycéen(?:ne|s)?\b|\blyceen(?:ne|s)?\b",
    r"\bcollégien(?:ne|s)?\b|\bcollegien(?:ne|s)?\b",
]
KEY_RE = re.compile("|".join(KEY_PATTERNS), flags=re.IGNORECASE)

rows = []
for _, r in df.iterrows():
    sents = list(nlp(r["text"]).sents)
    for i, s in enumerate(sents):
        txt = s.text.strip()
        if KEY_RE.search(txt):
            rows.append({
                "id": r.get("id"),
                "title": r.get("title"),
                "sentence": txt,
                "prev": sents[i-1].text.strip() if i-1 >= 0 else "",
                "next": sents[i+1].text.strip() if i+1 < len(sents) else "",
                "sent_idx": i
            })

snips = pd.DataFrame(rows)
snips.to_csv(SNIPPETS_CSV, index=False)
print(f"✅ {len(snips)} extraits ciblés → {SNIPPETS_CSV}")
if len(snips) == 0:
    raise SystemExit("Aucun extrait trouvé. Ajuste KEY_PATTERNS et relance.")

# ================= 2) Sentiment (CardiffNLP) =================
print("Chargement modèle sentiment (CardiffNLP)…")
MODEL = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
tokenizer = XLMRobertaTokenizer.from_pretrained(MODEL)   # slow → évite tiktoken
model = AutoModelForSequenceClassification.from_pretrained(MODEL)
clf = pipeline("sentiment-analysis", model=model, tokenizer=tokenizer)
print("✅ Modèle chargé.")

labs, scs = [], []
for t in snips["sentence"].astype(str):
    out = clf(t[:512])[0]
    labs.append(out["label"].upper())     # NEGATIVE / NEUTRAL / POSITIVE
    scs.append(float(out["score"]))
snips["sentiment"] = labs
snips["sentiment_score"] = scs
snips.to_csv(SENTIMENT_CSV, index=False)
print(f"✅ Sentiments ajoutés → {SENTIMENT_CSV}")
print("\n=== Répartition des sentiments (snippets) ===")
print(snips["sentiment"].value_counts())

# ================= 3) Prétraitement (TF-IDF / Wordclouds) =================
STOPWORDS = set(stopiso.stopwords(["fr", "en"]))
STOPWORDS |= {
    "france","français","francais","française","francaise",
    "service","services","public","publique","privé","prive",
    "citoyen","citoyenne","citoyens","citoyennes",
    "exemple","etc","ainsi","aussi","très","tres","plus","moins",
    "pass","culture","jeunes","jeunesse","étudiant","etudiant",
    "lycéen","lyceen","mjc","education","populaire"  # enlève sujets évidents des nuages
}

def normalize(s: str) -> str:
    s = s.lower()
    s = re.sub(r"http\S+", " ", s)
    s = re.sub(r"[^a-zàâçéèêëîïôûùüÿñæœ\s-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def filter_tokens(txt: str) -> str:
    txt = normalize(txt)
    toks = [w for w in txt.split() if len(w) > 2 and w not in STOPWORDS]
    return " ".join(toks)

snips["clean"] = snips["sentence"].astype(str).apply(filter_tokens)

# ================= 4) Clustering léger (TF-IDF + KMeans) =================
vectorizer = TfidfVectorizer(
    max_features=5000,
    ngram_range=(1,2),
    min_df=2,
    stop_words=list(STOPWORDS)
)
X = vectorizer.fit_transform(snips["clean"])
terms = vectorizer.get_feature_names_out()

print(f"Clustering en {N_CLUSTERS} sous-thèmes…")
kmeans = MiniBatchKMeans(n_clusters=N_CLUSTERS, random_state=42, batch_size=256, n_init="auto")
snips["cluster"] = kmeans.fit_predict(X)

# Top termes par cluster
rows = []
for c in range(N_CLUSTERS):
    idx = (snips["cluster"] == c).values
    if idx.sum() == 0:
        rows.append({"cluster": c, "top_terms": ""})
        continue
    mean_tfidf = X[idx].mean(axis=0).A1
    top_idx = mean_tfidf.argsort()[::-1][:TOP_TERMS]
    rows.append({"cluster": c, "top_terms": ", ".join([terms[i] for i in top_idx])})
cluster_terms = pd.DataFrame(rows)
cluster_terms.to_csv(CLUSTER_TERMS_CSV, index=False)
print(f"✅ Top termes par cluster → {CLUSTER_TERMS_CSV}")

snips.to_csv(CLUSTERS_CSV, index=False)
print(f"✅ Snippets + clusters → {CLUSTERS_CSV}")

# ================= 5) Tableau croisé “thème × tonalité” =================
def short_label(s):
    return " / ".join([t.strip() for t in s.split(",")[:3]]) if s else "cluster"
label_map = {r["cluster"]: short_label(r["top_terms"]) for _, r in cluster_terms.iterrows()}
snips["theme"] = snips["cluster"].map(label_map)

crosstab = pd.crosstab(snips["theme"], snips["sentiment"]).sort_index()
crosstab.to_csv(CROSSTAB_CSV)
print(f"✅ Tableau croisé thème × tonalité → {CROSSTAB_CSV}")
print("\n=== Thème × Tonalité ===")
print(crosstab)

# ================= 6) Wordclouds POSITIF / NÉGATIF =================
def build_wc(texts, out_png):
    toks = []
    for t in texts:
        toks.extend(filter_tokens(t).split())
    if not toks:
        with open(out_png.replace(".png", ".txt"), "w", encoding="utf-8") as f:
            f.write("Aucun terme pertinent pour générer un nuage.")
        return
    freq = Counter(toks)
    wc = WordCloud(width=1400, height=900, background_color="white").generate_from_frequencies(freq)
    plt.figure(figsize=(14,9))
    plt.imshow(wc, interpolation="bilinear")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(out_png)
    plt.close()

build_wc(snips[snips["sentiment"]=="POSITIVE"]["sentence"].tolist(), WC_POSITIVE_PNG)
print(f"✅ Nuage POSITIF → {WC_POSITIVE_PNG}")
build_wc(snips[snips["sentiment"]=="NEGATIVE"]["sentence"].tolist(), WC_NEGATIVE_PNG)
print(f"✅ Nuage NÉGATIF → {WC_NEGATIVE_PNG}")

# ================= 7) Topics BERTopic (optionnel) =================
if BER_TOPIC_AVAILABLE:
    print("BERTopic disponible — topics sur les snippets…")
    embedder = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = embedder.encode(
        snips["sentence"].tolist(),
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True
    )
    hdb = HDBSCAN(min_cluster_size=3, min_samples=1, metric="euclidean", prediction_data=True)
    topic_model = BERTopic(
        embedding_model=embedder,
        hdbscan_model=hdb,
        min_topic_size=3,
        language="french",
        calculate_probabilities=False,
        verbose=False,
    )
    topics, _ = topic_model.fit_transform(snips["sentence"].tolist(), embeddings)

    topic_info = topic_model.get_topic_info()
    topic_info.to_csv(os.path.join(OUT_DIR, "pass_snippets_topic_info.csv"), index=False)
    print("✅ Infos topics → analyse/pass_snippets_topic_info.csv")

    valid_topics = topic_info[topic_info.Topic != -1]
    if len(valid_topics) >= 2:
        fig_topics = topic_model.visualize_topics(width=1200, height=800)   # pas d'arg embeddings en 0.17.x
        fig_topics.write_html(BT_TOPICS_HTML)
        print(f"✅ Topics (UMAP) → {BT_TOPICS_HTML}")
    else:
        print("ℹ️ Moins de 2 topics valides : UMAP des topics non générée.")

    fig_bar = topic_model.visualize_barchart(top_n_topics=10)
    fig_bar.write_html(BT_BARCHART_HTML)
    print(f"✅ Barchart topics → {BT_BARCHART_HTML}")

    fig_hier = topic_model.visualize_hierarchy()
    fig_hier.write_html(BT_HIER_HTML)
    print(f"✅ Hiérarchie topics → {BT_HIER_HTML}")

    # UMAP des documents (ici on peut passer embeddings)
    try:
        fig_docs = topic_model.visualize_documents(
            snips["sentence"].tolist(),
            embeddings=embeddings,
            hide_annotations=True,
            width=1200, height=800
        )
        fig_docs.write_html(BT_DOCS_HTML)
        print(f"✅ UMAP documents → {BT_DOCS_HTML}")
    except Exception as e:
        print(f"ℹ️ visualize_documents indisponible ({e}).")
else:
    print("ℹ️ BERTopic non installé — section topics ignorée.")

print("\nTerminé ✅")
