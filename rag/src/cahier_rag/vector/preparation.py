"""Représentation B segmentée en tokens, positions Unicode dans la réponse intacte."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from cahier_rag.contracts import canonical_json
from cahier_rag.embeddings.registry import MODELS
from cahier_rag.evaluation.sampling import digest

VERSION = 1


@dataclass(frozen=True)
class TokenConfig:
    budget: int = 1024
    overlap: int = 128

    def __post_init__(self):
        if type(self.budget) is not int or not 32 <= self.budget <= 8192:
            raise ValueError("Budget entre 32 et 8192 tokens requis.")
        if type(self.overlap) is not int or not 0 <= self.overlap < self.budget // 2:
            raise ValueError("Chevauchement positif inférieur à la moitié du budget requis.")

    def to_dict(self):
        return asdict(self) | {"strategy": "B", "version": VERSION, "offsets": "unicode-codepoints"}


def contextualize(question, answer):
    return f"Question :\n{question}\n\nRéponse :\n{answer}"


def token_count(tokenizer, value):
    return len(tokenizer(value, truncation=False, add_special_tokens=True)["input_ids"])


def representation_identity(item):
    return "token-B:v1:" + digest(
        {
            key: item[key]
            for key in (
                "document_id",
                "source_hash",
                "configuration",
                "sample_hash",
                "start",
                "end",
            )
        }
    )


def segments(unit, tokenizer, config, sample_hash, split):
    """Recherche bornée du plus grand préfixe ; vérification exacte après frontières."""
    text = unit.text
    prefix = contextualize(unit.question_text, "")
    if token_count(tokenizer, prefix) + config.overlap + 8 >= config.budget:
        raise ValueError("Question trop longue pour le budget et le chevauchement configurés.")
    start, index = 0, 0
    while start < len(text):
        # Borne en caractères sûre pour éviter de tokeniser tout un texte immense à chaque étape.
        low, high = start + 1, min(len(text), start + config.budget * 32)
        best = None
        while low <= high:
            middle = (low + high) // 2
            if (
                token_count(tokenizer, contextualize(unit.question_text, text[start:middle]))
                <= config.budget
            ):
                best, low = middle, middle + 1
            else:
                high = middle - 1
        if best is None:
            raise ValueError("Aucun caractère de réponse ne tient dans le budget.")
        end = best
        if end < len(text):
            boundaries = list(re.finditer(r"\n\s*\n|[.!?](?:\s+|$)", text[start:end]))
            if boundaries and boundaries[-1].end() >= (end - start) // 2:
                end = start + boundaries[-1].end()
        value = contextualize(unit.question_text, text[start:end])
        count = token_count(tokenizer, value)
        if count > config.budget:
            raise ValueError("Segmentation hors budget ; aucune troncature autorisée.")
        item = {
            "version": VERSION,
            "configuration": config.to_dict(),
            "sample_hash": sample_hash,
            "document_id": unit.document_id,
            "source_hash": unit.content_hash,
            "split": split,
            "contribution_id": str(unit.contribution_id),
            "questionnaire_id": str(unit.questionnaire_id),
            "unit_type": unit.unit_type.value,
            "segment_index": index,
            "start": start,
            "end": end,
            "tokens": count,
            "text": value,
        }
        item["representation_id"] = representation_identity(item)
        item["content_hash"] = digest(item)
        yield item
        if end == len(text):
            break
        offsets = tokenizer(
            text[start:end], add_special_tokens=False, truncation=False, return_offsets_mapping=True
        )["offset_mapping"]
        next_start = (
            end if not config.overlap else start + offsets[max(0, len(offsets) - config.overlap)][0]
        )
        if next_start <= start:
            raise ValueError("Chevauchement empêchant la progression ; réduire overlap.")
        start, index = next_start, index + 1
        if index >= 1000:
            raise ValueError("Plafond de 1000 segments par unité atteint.")


def file_hash(path):
    checksum = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(part)
    return checksum.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(canonical_json(value) + "\n")
        stream.flush()
        import os

        os.fsync(stream.fileno())
    temporary.replace(path)


def prepare(repository, backend, directory, config):
    """Lecture par 25 unités, aucune connexion ouverte durant tokenization/écriture."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    backend.load_tokenizer()
    count, units, tokens, maximum = 0, 0, 0, 0
    ids = sorted(repository.scope.documents)
    temporary = directory / "representations.jsonl.tmp"
    with temporary.open("w", encoding="utf-8") as stream:
        for offset in range(0, len(ids), 25):
            batch = repository.fetch(ids[offset : offset + 25])
            for did in ids[offset : offset + 25]:
                for item in segments(
                    batch[did],
                    backend.tokenizer,
                    config,
                    repository.scope.sample_hash,
                    repository.scope.documents[did]["split"],
                ):
                    stream.write(canonical_json(item) + "\n")
                    count += 1
                    tokens += item["tokens"]
                    maximum = max(maximum, item["tokens"])
                units += 1
            if units % 1000 == 0:
                print(f"Préparation : {units}/{len(ids)} unités", flush=True)
    temporary.replace(directory / "representations.jsonl")
    manifest = {
        "version": VERSION,
        "configuration": config.to_dict(),
        "sample_hash": repository.scope.sample_hash,
        "units": units,
        "segments": count,
        "tokens": tokens,
        "max_tokens": maximum,
        "model": MODELS["bge-m3"].to_dict(),
        "snapshot_hash": backend.snapshot_hash,
        "data_hash": file_hash(directory / "representations.jsonl"),
    }
    manifest["manifest_hash"] = digest(manifest)
    atomic_json(directory / "manifest.json", manifest)
    return manifest


def load_prepared(directory, scope):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    check = dict(manifest)
    claimed = check.pop("manifest_hash")
    if (
        digest(check) != claimed
        or manifest["sample_hash"] != scope.sample_hash
        or manifest["units"] != len(scope.documents)
        or manifest["model"] != MODELS["bge-m3"].to_dict()
        or file_hash(directory / "representations.jsonl") != manifest["data_hash"]
    ):
        raise ValueError("Artefact préparé incompatible ou empreinte modifiée.")
    TokenConfig(manifest["configuration"]["budget"], manifest["configuration"]["overlap"])
    return manifest


def iter_units(directory, scope):
    """Une unité complète à la fois, taille de ligne et nombre de segments bornés."""
    expected = iter(sorted(scope.documents))
    wanted = next(expected, None)
    current = []
    with (Path(directory) / "representations.jsonl").open(encoding="utf-8") as stream:
        while line := stream.readline(4000001):
            if len(line) > 4000000:
                raise ValueError("Représentation dépassant le plafond de ligne.")
            item = json.loads(line)
            if item["document_id"] != wanted:
                if not current:
                    raise ValueError("Ordre ou document préparé invalide.")
                yield current
                current = []
                wanted = next(expected, None)
            check = dict(item)
            claimed = check.pop("content_hash")
            if (
                item["document_id"] != wanted
                or digest(check) != claimed
                or item["source_hash"] != scope.documents[wanted]["content_hash"]
                or item["split"] != scope.documents[wanted]["split"]
                or item["sample_hash"] != scope.sample_hash
                or item["segment_index"] != len(current)
            ):
                raise ValueError("Référence, ordre, partition ou empreinte incompatible.")
            current.append(item)
            if len(current) > 1000:
                raise ValueError("Trop de segments dans une unité.")
    if not current:
        raise ValueError("Artefact vide ou incomplet.")
    yield current
    if wanted is None or next(expected, None) is not None:
        raise ValueError("Artefact incomplet.")
