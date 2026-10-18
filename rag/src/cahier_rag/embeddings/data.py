"""Chargement borné de RAG-011 et exemples synthétiques, sans jugements humains."""

import json
from pathlib import Path

from cahier_rag.embeddings.core import EmbeddingError, EmbeddingInput
from cahier_rag.evaluation.sampling import digest
from cahier_rag.representations.artifacts import inspect_artifact

QUERIES = (
    "Comment alléger les prélèvements des ménages modestes ?",
    "Comment restaurer la confiance dans les banques ?",
    "Qui s’oppose à la fermeture des écoles rurales ?",
    "Comment se déplacer sans brûler de pétrole ?",
    "Comment faciliter les démarches administratives ?",
    "Comment donner plus de pouvoir de décision aux citoyens ?",
    "Comment rendre les soins accessibles dans les campagnes ?",
    "Comment réduire les déchets d’emballage ?",
)
SYNTHETIC_DOCUMENTS = (
    "Réduire l’impôt payé par les familles aux revenus les plus faibles.",
    "Renforcer le contrôle des établissements financiers et protéger les déposants.",
    "Une banque de données centralise les archives historiques de la commune.",
    "Question : Faut-il fermer les petites écoles des villages ?\nRéponse : Non.",
    "Non.",
    "Développer les pistes cyclables et encourager les trajets à vélo.",
    "La bibliothèque possède une collection de romans policiers.",
    "Proposer des rendez-vous médicaux dans les territoires ruraux.",
)


def query_inputs():
    return [
        EmbeddingInput(f"synthetic-query:{i}", text, digest(text)) for i, text in enumerate(QUERIES)
    ]


def synthetic_inputs():
    return [
        EmbeddingInput(f"synthetic-document:{i}", text, digest(text))
        for i, text in enumerate(SYNTHETIC_DOCUMENTS)
    ]


def read_representations(directory, scope):
    manifest = inspect_artifact(directory, scope=scope)
    if (
        manifest["statistics"]["target_units"] > 512
        or manifest["statistics"]["representations"] > 2048
        or set(manifest["statistics"]["by_split"]) != {"development"}
    ):
        raise EmbeddingError(
            "Expérience limitée à 512 cibles de développement et 2048 représentations."
        )
    inputs = []
    with (Path(directory) / "representations.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            inputs.append(
                EmbeddingInput(
                    row["representation_id"],
                    row["embedding_text"],
                    row["content_hash"],
                    row["primary"]["document_id"],
                )
            )
    return manifest, inputs
