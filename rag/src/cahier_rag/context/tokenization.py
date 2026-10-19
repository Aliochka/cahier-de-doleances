"""Comptage exact hors ligne avec un tokenizer déjà téléchargé, sans poids ni GPU."""

import hashlib
import importlib.metadata
from collections import OrderedDict


class LocalTokenizer:
    def __init__(self, path, *, repository, revision, expected_sha256):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
            raise ValueError("Tokenizer modifié.")
        from tokenizers import Tokenizer

        self.tokenizer = Tokenizer.from_file(str(path))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        self.cache = OrderedDict()
        self.description = {
            "library_version": importlib.metadata.version("tokenizers"),
            "repository": repository,
            "revision": revision,
            "sha256": expected_sha256,
            "add_special_tokens": False,
            "truncation": False,
            "padding": False,
            "counting": "exact UTF-8 canonical JSON; no chat template",
        }

    def count(self, text):
        if text in self.cache:
            self.cache.move_to_end(text)
            return self.cache[text]
        value = len(self.tokenizer.encode(text, add_special_tokens=False).ids)
        if len(text) < 32768:
            self.cache[text] = value
            if len(self.cache) > 128:
                self.cache.popitem(last=False)
        return value
