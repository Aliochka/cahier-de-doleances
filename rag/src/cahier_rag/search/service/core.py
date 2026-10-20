"""H1 public persistant : BGE-M3, lexical RAG-027, ANN ef1000 et RRF 60."""

import hashlib
import threading
import time
import unicodedata
from dataclasses import asdict, dataclass

from cahier_rag.contracts import TextUnit
from cahier_rag.embeddings.core import EmbeddingError, EmbeddingInput, InputTooLong
from cahier_rag.fullcorpus.audit import fingerprint
from cahier_rag.search.hybrid.core import HybridConfig, fuse
from cahier_rag.search.preparation import tokenize
from cahier_rag.search.service.control import (
    Budget,
    InvalidQuery,
    SearchBusy,
    SearchError,
    SearchNotReady,
)
from cahier_rag.tuning.lexical import TunedSearch
from cahier_rag.tuning.vector import AnnConfig, ann_search

RECIPE_VERSION = "h1-public-v1"


@dataclass(frozen=True)
class SearchRecipe:
    """50 est une référence expérimentale, pas la capacité du contrat de sortie.

    Le lecteur actuel accepte jusqu'à 100 candidats par branche. Une expérience
    au-delà devra étendre ce lecteur, pas remplacer le service ou son contrat.
    """

    depth: int = 50
    result_limit: int = 50
    rrf_k: int = 60
    ann: AnnConfig = AnnConfig(ef_search=1000, candidates=400)
    version: str = RECIPE_VERSION

    def __post_init__(self):
        HybridConfig(depth=self.depth, k=self.rrf_k)
        if type(self.result_limit) is not int or not 1 <= self.result_limit <= 2 * self.depth:
            raise ValueError("Limite de classement comprise entre 1 et deux profondeurs requise.")
        if (
            not isinstance(self.ann, AnnConfig)
            or not isinstance(self.version, str)
            or not self.version
        ):
            raise ValueError("Recette de recherche invalide.")

    @property
    def fingerprint(self):
        return fingerprint(asdict(self))


@dataclass(frozen=True)
class Segment:
    index: int
    representation_id: str
    start_offset: int
    end_offset: int


@dataclass(frozen=True)
class Hit:
    # TextUnit est immuable et distingue les IDs historiques de document_id.
    # Ce contrat interne n'est pas une réponse JSON publique.
    document: TextUnit
    rrf_score: float
    lexical_rank: int | None
    vector_rank: int | None
    segment: Segment | None


@dataclass(frozen=True)
class Timings:
    validation: float
    encoding: float
    lexical: float
    vector: float
    fusion: float
    total: float


@dataclass(frozen=True)
class Ranking:
    generation: str
    hits: tuple[Hit, ...]
    timings: Timings
    recipe_hash: str
    recipe_version: str = RECIPE_VERSION


def validate_query(query):
    if not isinstance(query, str) or len(query) > 512:
        raise InvalidQuery("La recherche est limitée à 512 caractères.")
    value = unicodedata.normalize("NFC", query).strip()
    if not value or not any(c.isalnum() for c in value):
        raise InvalidQuery("Saisissez une question ou des mots significatifs.")
    try:
        tokenize(value)
    except ValueError as exc:
        raise InvalidQuery(str(exc)) from None
    return value


class HybridSearch:
    """Service synchrone à appeler hors event loop via SearchWorker.

    Le modèle est injecté (EmbeddingEngine en usage réel), les essais peuvent
    injecter un encodeur léger. La lecture du corpus est également injectée.
    Aucune dépendance à l'API, aux campagnes ou à la génération de réponses.
    """

    def __init__(self, reader, encoder, *, recipe=SearchRecipe()):
        if not isinstance(recipe, SearchRecipe):
            raise ValueError("Une SearchRecipe immuable est requise.")
        self.reader, self.encoder = reader, encoder
        self.recipe = recipe
        self._lock = threading.Lock()
        self.ready = False
        self.closed = False
        self.load_seconds = None

    def start(self, budget=None):
        with self._lock:
            if self.closed:
                raise SearchNotReady("Le service est arrêté.")
            if self.ready:
                return
            budget = budget or Budget(120)
            try:
                with budget.monitor(), budget.phase("startup"):
                    self.reader.validate(budget)
                    started = time.monotonic()
                    self.encoder.load()
                    self.load_seconds = time.monotonic() - started
                    self._encode("Préparation du service de recherche")
                    budget.check()
                self.ready = True
            except Exception as exc:
                self.encoder.close()
                if isinstance(exc, SearchError):
                    raise
                raise SearchNotReady("Initialisation du moteur impossible.") from None

    def _encode(self, query):
        item = EmbeddingInput("query", query, hashlib.sha256(query.encode()).hexdigest())
        return next(self.encoder.encode_queries([item])).vectors[0]

    def retrieve(self, query, *, budget=None, question_id=None):
        # Préparé pour le chantier Questions ; aucun filtre ignoré silencieusement.
        if question_id is not None:
            raise InvalidQuery("La recherche filtrée par question n'est pas encore disponible.")
        query = validate_query(query)
        if not self._lock.acquire(blocking=False):
            raise SearchBusy("Un calcul de recherche est déjà en cours.")
        try:
            if not self.ready or self.closed:
                raise SearchNotReady("Le moteur de recherche n'est pas prêt.")
            recipe = self.recipe
            budget = budget or Budget()
            started = time.monotonic()
            with budget.monitor():
                with budget.phase("corpus"):
                    generation = self.reader.validate(budget)
                validated = time.monotonic()
                with budget.phase("encoding", 3):
                    try:
                        vector = self._encode(query)
                    except InputTooLong:
                        raise InvalidQuery("La requête dépasse la fenêtre du modèle.") from None
                    except EmbeddingError:
                        budget.check()
                        self.ready = False
                        raise SearchNotReady("Encodeur de recherche indisponible.") from None
                encoded = time.monotonic()
                store = self.reader.store(budget)
                # Un nouvel objet par appel : pas de diagnostics mutables partagés.
                lexical = TunedSearch(store, statistics=True, prefilter=None)
                with budget.phase("sql", 10):
                    try:
                        left = lexical.lexical(query, limit=recipe.depth)
                    except ValueError as exc:
                        if str(exc) == "Au plus 32 lexèmes significatifs.":
                            raise InvalidQuery(str(exc)) from None
                        raise
                    lexical_end = time.monotonic()
                    right, trace = ann_search(store, vector, recipe.ann, limit=recipe.depth)
                vector_end = time.monotonic()
                with budget.phase("fusion"):
                    results, traces = fuse({"lexical": left, "vector": right}, k=recipe.rrf_k)
                    winners = {row["document_id"]: row for row in trace["winners"]}
                    hits = []
                    for result in results[: recipe.result_limit]:
                        did = result.document.document_id
                        winner = winners.get(did)
                        hits.append(
                            Hit(
                                document=result.document,
                                rrf_score=result.score,
                                lexical_rank=traces[did].get("lexical", {}).get("rank"),
                                vector_rank=traces[did].get("vector", {}).get("rank"),
                                segment=Segment(
                                    winner["segment_index"],
                                    winner["representation_id"],
                                    winner["start_offset"],
                                    winner["end_offset"],
                                )
                                if winner
                                else None,
                            )
                        )
                ended = time.monotonic()
            return Ranking(
                generation,
                tuple(hits),
                Timings(
                    validation=validated - started,
                    encoding=encoded - validated,
                    lexical=lexical_end - encoded,
                    vector=vector_end - lexical_end,
                    fusion=ended - vector_end,
                    total=ended - started,
                ),
                recipe.fingerprint,
                recipe.version,
            )
        except SearchNotReady:
            self.ready = False
            raise
        except ValueError:
            self.ready = False
            raise SearchNotReady("Corpus ou résultats de recherche incompatibles.") from None
        finally:
            self._lock.release()

    def close(self):
        # Attend la fin effective d'une inférence ; jamais de déchargement concurrent.
        with self._lock:
            if not self.closed:
                self.ready = False
                self.closed = True
                try:
                    self.encoder.close()
                finally:
                    self.reader.close()
