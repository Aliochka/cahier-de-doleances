"""Fusion de rangs locale, sans dépendance ML ni chargement à l'import."""

from cahier_rag.search.hybrid.core import HybridConfig, HybridEngine, fuse

__all__ = ["HybridConfig", "HybridEngine", "fuse"]
