# Application-only layer. Supply the preserved tag of the current CPU image.
ARG P6_BASE_IMAGE
FROM ${P6_BASE_IMAGE}

# Refuse an unreviewed runtime layout or baseline, without loading any model.
RUN /opt/venv/bin/python -c "import hashlib; from pathlib import Path; from cahier_rag.search.service import core; p=Path(core.__file__); assert str(p)=='/build/rag/src/cahier_rag/search/service/core.py'; assert hashlib.sha256(p.read_bytes()).hexdigest()=='8ad39615726d51748cc9b2ca1e7ad1ad791274607a599bfe57201e813e449813'"
COPY --chown=app:app rag/src/cahier_rag/search/service/core.py /build/rag/src/cahier_rag/search/service/core.py
RUN /opt/venv/bin/python -c "from cahier_rag.search.service.core import H1LexicalSearch, SearchRecipe; from cahier_rag.tuning.lexical import TunedSearch; assert SearchRecipe().version=='h1-public-v2-ts-rank'; p={}; s=H1LexicalSearch.score_expression([dict(query=\"'test'\",idf=1.0,total=1.0)],p); assert 'ts_rank(' in s and 'ts_rank_cd(' not in s; assert H1LexicalSearch.lexical is TunedSearch.lexical"
