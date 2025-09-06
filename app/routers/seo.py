# app/routers/seo.py
from __future__ import annotations

import os
import hashlib
import tempfile
import asyncio
import logging
import time
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import PlainTextResponse, Response, FileResponse
from sqlalchemy import text
from datetime import datetime, timezone
from app.helpers import slugify, clean_text_excerpt  # type: ignore

from app.db import SessionLocal

router = APIRouter()

# Limites (prudents pour la perf)
SITEMAP_LIMIT_QUESTIONS = 2000
SITEMAP_LIMIT_AUTHORS   = 1000
SITEMAP_LIMIT_FORMS     = 50

CACHE_ROBOTS = "public, max-age=86400"
CACHE_SITEMAP = "public, max-age=21600"
CACHE_OG_IMAGE = "public, max-age=604800"  # 1 semaine

# Configuration pour la génération d'images OG
OG_CACHE_DIR = Path(os.getenv("OG_CACHE_DIR", tempfile.gettempdir())) / "og_cache"
OG_CACHE_DIR.mkdir(exist_ok=True, parents=True)

# Configuration Playwright pour la production
PLAYWRIGHT_ARGS = [
    '--no-sandbox',
    '--disable-dev-shm-usage',
    '--disable-background-timer-throttling',
    '--disable-backgrounding-occluded-windows',
    '--disable-renderer-backgrounding',
    '--disable-features=TranslateUI',
    '--disable-gpu',
    '--no-first-run',
    '--disable-default-apps',
    '--disable-extensions',
    '--disable-sync',
    '--disable-background-networking',
    '--no-zygote'  # Pour les environnements Docker
]

# Pool global de navigateurs (sera initialisé à la première utilisation)
_browser_pool = None

# Logger spécialisé pour les images OG
logger = logging.getLogger("og_images")

async def _get_browser():
    """Obtient un navigateur Playwright optimisé pour la production"""
    global _browser_pool
    
    if _browser_pool is None:
        from playwright.async_api import async_playwright
        _browser_pool = await async_playwright().start()
    
    # Lance un nouveau navigateur avec les arguments optimisés
    browser = await _browser_pool.chromium.launch(args=PLAYWRIGHT_ARGS)
    return browser

def _fmt_iso(dt: datetime | None) -> str | None:
    if not dt:
        return None
    # force ISO8601 avec timezone si absente
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()

@router.api_route("/robots.txt", methods=["GET", "HEAD"], name="robots_txt")
def robots_txt(request: Request):
    # construit l'URL absolue du sitemap
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    netloc = request.headers.get("x-forwarded-host") or request.url.netloc
    base = f"{scheme}://{netloc}"
    body = f"""User-agent: *
Allow: /
Sitemap: {base}/sitemap.xml
"""
    if request.method == "HEAD":
        return Response(status_code=200, headers={"Cache-Control": CACHE_ROBOTS}, media_type="text/plain; charset=utf-8")
    return PlainTextResponse(body, headers={"Cache-Control": CACHE_ROBOTS})

@router.api_route("/sitemap.xml", methods=["GET", "HEAD"], name="sitemap_xml")
def sitemap_xml(request: Request):
    if request.method == "HEAD":
        return Response(status_code=200, headers={"Cache-Control": CACHE_SITEMAP}, media_type="application/xml; charset=utf-8")

    # base absolue
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    netloc = request.headers.get("x-forwarded-host") or request.url.netloc
    base = f"{scheme}://{netloc}"

    urls: list[tuple[str, str | None]] = []

    with SessionLocal() as db:
        # lastmod global (homepage) = dernière contribution
        home_lastmod = db.execute(text("SELECT MAX(submitted_at) FROM contributions")).scalar()
        urls.append((f"{base}/", _fmt_iso(home_lastmod)))
        
        # Pages de recherche principales
        urls.append((f"{base}/search/questions", _fmt_iso(home_lastmod)))
        urls.append((f"{base}/search/answers", _fmt_iso(home_lastmod)))

        # Questions: canonical slug + lastmod = max(submitted_at des réponses)
        q_rows = db.execute(text("""
            SELECT q.id, q.prompt, MAX(c.submitted_at) AS lastmod
            FROM questions q
            JOIN answers a       ON a.question_id = q.id
            JOIN contributions c ON c.id = a.contribution_id
            WHERE a.text IS NOT NULL
            GROUP BY q.id, q.prompt
            ORDER BY lastmod DESC NULLS LAST, q.id DESC
            LIMIT :lim
        """), {"lim": SITEMAP_LIMIT_QUESTIONS}).mappings().all()

        for r in q_rows:
            qslug = slugify(r["prompt"] or f"question-{r['id']}")
            urls.append((f"{base}/questions/{r['id']}-{qslug}", _fmt_iso(r["lastmod"])))

        # Auteurs: canonical slug + lastmod = max(submitted_at)
        a_rows = db.execute(text("""
            SELECT au.id, au.name, MAX(c.submitted_at) AS lastmod
            FROM authors au
            JOIN contributions c ON c.author_id = au.id
            JOIN answers a       ON a.contribution_id = c.id
            WHERE a.text IS NOT NULL
            GROUP BY au.id, au.name
            ORDER BY lastmod DESC NULLS LAST, au.id DESC
            LIMIT :lim
        """), {"lim": SITEMAP_LIMIT_AUTHORS}).mappings().all()

        for r in a_rows:
            name = r["name"] or f"Auteur #{r['id']}"
            aslug = slugify(name)
            urls.append((f"{base}/authors/{r['id']}-{aslug}", _fmt_iso(r["lastmod"])))

        # Formulaires: lastmod = max(submitted_at des contributions liées)
        f_rows = db.execute(text("""
            SELECT f.id, f.name, MAX(c.submitted_at) AS lastmod
            FROM forms f
            JOIN questions q ON q.form_id = f.id
            JOIN answers a ON a.question_id = q.id
            JOIN contributions c ON c.id = a.contribution_id
            WHERE a.text IS NOT NULL
            GROUP BY f.id, f.name
            ORDER BY lastmod DESC NULLS LAST, f.id DESC
            LIMIT :lim
        """), {"lim": SITEMAP_LIMIT_FORMS}).mappings().all()

        for r in f_rows:
            urls.append((f"{base}/forms/{r['id']}", _fmt_iso(r["lastmod"])))

    # Rend XML
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, lastmod in urls:
        parts.append("<url>")
        parts.append(f"<loc>{loc}</loc>")
        if lastmod:
            parts.append(f"<lastmod>{lastmod}</lastmod>")
        parts.append("</url>")
    parts.append("</urlset>")
    xml = "\n".join(parts)

    return Response(
        content=xml,
        media_type="application/xml; charset=utf-8",
        headers={"Cache-Control": CACHE_SITEMAP},
    )


def _generate_cache_key(answer_data: dict) -> str:
    """Génère une clé de cache basée sur le contenu de la réponse"""
    content = f"{answer_data['question_prompt']}-{answer_data['answer_text']}-{answer_data['author_name']}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]


def _generate_cache_key_question(question_data: dict) -> str:
    """Génère une clé de cache basée sur le contenu de la question"""
    chart_str = ""
    if question_data.get('chart_data'):
        chart_str = f"-{question_data['chart_data']['labels']}-{question_data['chart_data']['data']}"
    content = f"q-{question_data['question_id']}-{question_data['question_prompt']}-{question_data['question_type']}-{question_data['answers_count']}{chart_str}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]


def _create_og_html_template(answer_data: dict) -> str:
    """Crée le HTML temporaire pour la génération d'image OG"""
    question_prompt = answer_data['question_prompt'] or f"Question #{answer_data['question_id']}"
    answer_excerpt = clean_text_excerpt(answer_data['answer_text'] or "", max_chars=200)
    author_name = answer_data['author_name'] or f"Auteur #{answer_data['author_id']}"
    
    html = f'''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <title>OG Image</title>
    <style>
        body {{
            margin: 0;
            padding: 60px;
            width: 1200px;
            height: 630px;
            box-sizing: border-box;
            font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif;
            background: linear-gradient(135deg, #f2f1ea 0%, #fbfaf6 100%);
            color: #2B2A26;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}
        
        .container {{
            max-width: 1080px;
            margin: 0 auto;
        }}
        
        .question {{
            font-size: 42px;
            font-weight: 700;
            line-height: 1.2;
            margin-bottom: 30px;
            color: #2B2A26;
        }}
        
        .answer {{
            font-size: 32px;
            line-height: 1.4;
            margin-bottom: 40px;
            color: #2B2A26;
            font-style: italic;
        }}
        
        .author {{
            font-size: 24px;
            color: #6b6258;
            text-align: right;
        }}
        
        .brand {{
            position: absolute;
            bottom: 30px;
            left: 60px;
            font-size: 20px;
            color: #6b6258;
            font-weight: 500;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="question">{question_prompt}</div>
        <div class="answer">"{answer_excerpt}"</div>
        <div class="author">— {author_name}</div>
    </div>
    <div class="brand">Cahier de doléances</div>
</body>
</html>'''
    
    return html


def _create_og_html_template_question(question_data: dict) -> str:
    """Crée le HTML temporaire pour la génération d'image OG d'une question"""
    question_prompt = question_data['question_prompt'] or f"Question #{question_data['question_id']}"
    answers_count = question_data['answers_count'] or 0
    question_type = question_data.get('question_type', 'text')
    chart_data = question_data.get('chart_data')
    
    # Styles de base
    base_style = '''
        body {
            margin: 0;
            padding: 60px;
            width: 1200px;
            height: 630px;
            box-sizing: border-box;
            font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif;
            background: linear-gradient(135deg, #f2f1ea 0%, #fbfaf6 100%);
            color: #2B2A26;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        
        .container {
            max-width: 1080px;
            margin: 0 auto;
        }
        
        .question {
            font-size: 48px;
            font-weight: 700;
            line-height: 1.2;
            margin-bottom: 40px;
            color: #2B2A26;
        }
        
        .stats {
            font-size: 24px;
            color: #6b6258;
            margin-bottom: 40px;
        }
        
        .brand {
            position: absolute;
            bottom: 30px;
            left: 60px;
            font-size: 20px;
            color: #6b6258;
            font-weight: 500;
        }
    '''
    
    # Template de base sans graphique
    if not chart_data or question_type not in ('single_choice', 'multi_choice'):
        html = f'''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <title>OG Question</title>
    <style>
        {base_style}
    </style>
</head>
<body>
    <div class="container">
        <div class="question">{question_prompt}</div>
        <div class="stats">{answers_count} réponse{'s' if answers_count != 1 else ''}</div>
    </div>
    <div class="brand">Cahier de doléances</div>
</body>
</html>'''
    
    else:
        # Template avec graphique (barres horizontales simple)
        chart_style = '''
        .chart {
            margin: 20px 0;
        }
        
        .chart-bar {
            display: flex;
            align-items: center;
            margin-bottom: 15px;
            font-size: 18px;
        }
        
        .chart-label {
            width: 300px;
            padding-right: 15px;
            color: #2B2A26;
            text-align: right;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .chart-bar-container {
            flex: 1;
            height: 25px;
            background: #e9ecef;
            border-radius: 12px;
            overflow: hidden;
            margin-right: 15px;
        }
        
        .chart-bar-fill {
            height: 100%;
            border-radius: 12px;
            transition: width 0.3s ease;
        }
        
        .chart-value {
            min-width: 40px;
            color: #6b6258;
            font-weight: 600;
        }
        '''
        
        # Calculer le max pour la largeur des barres
        max_count = max(chart_data['data']) if chart_data['data'] else 1
        
        # Générer les barres
        chart_bars = ""
        for i, (label, count, color) in enumerate(zip(chart_data['labels'][:5], chart_data['data'][:5], chart_data['colors'][:5])):
            width_percent = (count / max_count * 100) if max_count > 0 else 0
            # Tronquer les labels trop longs
            display_label = label[:40] + "..." if len(label) > 40 else label
            chart_bars += f'''
            <div class="chart-bar">
                <div class="chart-label">{display_label}</div>
                <div class="chart-bar-container">
                    <div class="chart-bar-fill" style="width: {width_percent}%; background-color: {color};"></div>
                </div>
                <div class="chart-value">{count}</div>
            </div>'''
        
        html = f'''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <title>OG Question Chart</title>
    <style>
        {base_style}
        {chart_style}
        
        .question {{
            font-size: 36px;
            margin-bottom: 20px;
        }}
        
        .stats {{
            font-size: 20px;
            margin-bottom: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="question">{question_prompt}</div>
        <div class="stats">{answers_count} réponse{'s' if answers_count != 1 else ''}</div>
        <div class="chart">
            {chart_bars}
        </div>
    </div>
    <div class="brand">Cahier de doléances</div>
</body>
</html>'''
    
    return html


async def _generate_og_image(answer_data: dict, cache_key: str) -> Path:
    """Génère l'image OG avec Playwright optimisé pour la production"""
    cache_path = OG_CACHE_DIR / f"{cache_key}.png"
    
    # Si l'image est déjà en cache, la retourner
    if cache_path.exists():
        logger.debug(f"Cache hit pour {cache_key}")
        return cache_path
    
    start_time = time.time()
    logger.info(f"Génération d'image OG pour answer - cache_key: {cache_key}")
    
    # Créer le HTML temporaire
    html_content = _create_og_html_template(answer_data)
    
    # Sauvegarder temporairement le HTML
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
        f.write(html_content)
        temp_html_path = f.name
    
    try:
        # Utiliser le navigateur optimisé
        browser = await _get_browser()
        
        try:
            page = await browser.new_page()
            
            # Configurer la taille de viewport pour 1200x630
            await page.set_viewport_size({"width": 1200, "height": 630})
            
            # Charger le HTML avec timeout
            await page.goto(f"file://{temp_html_path}", timeout=15000)
            
            # Attendre que la page soit complètement chargée
            await page.wait_for_load_state('networkidle', timeout=10000)
            
            # Prendre la capture d'écran
            await page.screenshot(path=str(cache_path), full_page=True)
            
            generation_time = time.time() - start_time
            logger.info(f"Image OG générée avec succès en {generation_time:.2f}s - taille: {cache_path.stat().st_size} bytes")
            
        finally:
            # Fermer le navigateur
            await browser.close()
            
    except Exception as e:
        logger.error(f"Erreur lors de la génération d'image OG: {str(e)}")
        raise
    finally:
        # Supprimer le fichier HTML temporaire
        os.unlink(temp_html_path)
    
    return cache_path


async def _generate_og_image_question(question_data: dict, cache_key: str) -> Path:
    """Génère l'image OG pour une question avec Playwright optimisé"""
    cache_path = OG_CACHE_DIR / f"{cache_key}.png"
    
    # Si l'image est déjà en cache, la retourner
    if cache_path.exists():
        logger.debug(f"Cache hit pour question {cache_key}")
        return cache_path
    
    start_time = time.time()
    logger.info(f"Génération d'image OG pour question - cache_key: {cache_key}")
    
    # Créer le HTML temporaire
    html_content = _create_og_html_template_question(question_data)
    
    # Sauvegarder temporairement le HTML
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
        f.write(html_content)
        temp_html_path = f.name
    
    try:
        # Utiliser le navigateur optimisé
        browser = await _get_browser()
        
        try:
            page = await browser.new_page()
            
            # Configurer la taille de viewport pour 1200x630
            await page.set_viewport_size({"width": 1200, "height": 630})
            
            # Charger le HTML avec timeout
            await page.goto(f"file://{temp_html_path}", timeout=15000)
            
            # Attendre que la page soit complètement chargée
            await page.wait_for_load_state('networkidle', timeout=10000)
            
            # Prendre la capture d'écran
            await page.screenshot(path=str(cache_path), full_page=True)
            
            generation_time = time.time() - start_time
            logger.info(f"Image OG question générée avec succès en {generation_time:.2f}s - taille: {cache_path.stat().st_size} bytes")
            
        finally:
            # Fermer le navigateur
            await browser.close()
            
    except Exception as e:
        logger.error(f"Erreur lors de la génération d'image OG question: {str(e)}")
        raise
    finally:
        # Supprimer le fichier HTML temporaire
        os.unlink(temp_html_path)
    
    return cache_path


@router.get("/og/answer/{answer_id}.png", name="og_answer_image")
async def og_answer_image(answer_id: int):
    """Génère une image OG pour une réponse spécifique"""
    
    with SessionLocal() as db:
        row = db.execute(text("""
            SELECT
                a.id            AS answer_id,
                a.text          AS answer_text,
                q.id            AS question_id,
                q.prompt        AS question_prompt,
                c.author_id     AS author_id,
                au.name         AS author_name,
                c.submitted_at  AS submitted_at
            FROM answers a
            JOIN contributions c ON c.id = a.contribution_id
            LEFT JOIN authors au  ON au.id = c.author_id
            JOIN questions q      ON q.id = a.question_id
            WHERE a.id = :aid
        """), {"aid": answer_id}).mappings().first()
    
    if not row:
        raise HTTPException(status_code=404, detail="Réponse introuvable")
    
    answer_data = dict(row)
    
    try:
        # Générer la clé de cache
        cache_key = _generate_cache_key(answer_data)
        
        # Générer l'image
        image_path = await _generate_og_image(answer_data, cache_key)
        
        # Retourner l'image
        return FileResponse(
            str(image_path), 
            media_type="image/png",
            headers={"Cache-Control": CACHE_OG_IMAGE}
        )
        
    except Exception as e:
        # En cas d'erreur, retourner une erreur 500
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération de l'image: {str(e)}")


def _generate_cache_key_form(form_data: dict) -> str:
    """Génère une clé de cache basée sur le contenu du formulaire"""
    content = f"form-{form_data['form_id']}-{form_data['form_name']}-{form_data['questions_count']}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]


def _create_og_html_template_form(form_data: dict) -> str:
    """Crée le HTML temporaire pour la génération d'image OG d'un formulaire"""
    form_name = form_data['form_name'] or f"Formulaire #{form_data['form_id']}"
    questions_count = form_data['questions_count'] or 0
    
    html = f'''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <title>OG Form</title>
    <style>
        body {{
            margin: 0;
            padding: 60px;
            width: 1200px;
            height: 630px;
            box-sizing: border-box;
            font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif;
            background: linear-gradient(135deg, #f2f1ea 0%, #fbfaf6 100%);
            color: #2B2A26;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}
        
        .container {{
            max-width: 1080px;
            margin: 0 auto;
            text-align: center;
        }}
        
        .form-title {{
            font-size: 48px;
            font-weight: 700;
            line-height: 1.2;
            margin-bottom: 40px;
            color: #2B2A26;
        }}
        
        .questions-count {{
            font-size: 28px;
            color: #6b6258;
            margin-bottom: 40px;
        }}
        
        .icon {{
            font-size: 80px;
            margin-bottom: 30px;
            color: #2B2A26;
        }}
        
        .brand {{
            position: absolute;
            bottom: 30px;
            left: 60px;
            font-size: 20px;
            color: #6b6258;
            font-weight: 500;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">📋</div>
        <div class="form-title">{form_name}</div>
        <div class="questions-count">{questions_count} question{'s' if questions_count != 1 else ''}</div>
    </div>
    <div class="brand">Cahier de doléances</div>
</body>
</html>'''
    
    return html


async def _generate_og_image_form(form_data: dict, cache_key: str) -> Path:
    """Génère l'image OG pour un formulaire avec Playwright"""
    cache_path = OG_CACHE_DIR / f"{cache_key}.png"
    
    # Si l'image est déjà en cache, la retourner
    if cache_path.exists():
        return cache_path
    
    # Créer le HTML temporaire
    html_content = _create_og_html_template_form(form_data)
    
    # Sauvegarder temporairement le HTML
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
        f.write(html_content)
        temp_html_path = f.name
    
    try:
        # Importer Playwright de manière asynchrone
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            # Lancer le navigateur
            browser = await p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage'])
            page = await browser.new_page()
            
            # Configurer la taille de viewport pour 1200x630
            await page.set_viewport_size({"width": 1200, "height": 630})
            
            # Charger le HTML
            await page.goto(f"file://{temp_html_path}")
            
            # Attendre que la page soit complètement chargée
            await page.wait_for_load_state('networkidle')
            
            # Prendre la capture d'écran
            await page.screenshot(path=str(cache_path), full_page=True)
            
            # Fermer le navigateur
            await browser.close()
            
    finally:
        # Supprimer le fichier HTML temporaire
        os.unlink(temp_html_path)
    
    return cache_path


@router.get("/og/form/{form_id}.png", name="og_form_image")
async def og_form_image(form_id: int):
    """Génère une image OG pour un formulaire spécifique"""
    
    with SessionLocal() as db:
        # Récupérer les données du formulaire
        row = db.execute(text("""
            SELECT
                f.id            AS form_id,
                f.name          AS form_name,
                COUNT(q.id)     AS questions_count
            FROM forms f
            LEFT JOIN questions q ON q.form_id = f.id
            WHERE f.id = :fid
            GROUP BY f.id, f.name
        """), {"fid": form_id}).mappings().first()
    
    if not row:
        raise HTTPException(status_code=404, detail="Formulaire introuvable")
    
    form_data = dict(row)
    
    try:
        # Générer la clé de cache
        cache_key = _generate_cache_key_form(form_data)
        
        # Générer l'image
        image_path = await _generate_og_image_form(form_data, cache_key)
        
        # Retourner l'image
        return FileResponse(
            str(image_path), 
            media_type="image/png",
            headers={"Cache-Control": CACHE_OG_IMAGE}
        )
        
    except Exception as e:
        # En cas d'erreur, retourner une erreur 500
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération de l'image: {str(e)}")


@router.get("/og/question/{question_id}.png", name="og_question_image")
async def og_question_image(question_id: int):
    """Génère une image OG pour une question spécifique"""
    
    with SessionLocal() as db:
        # Récupérer les données de la question
        row = db.execute(text("""
            SELECT
                q.id            AS question_id,
                q.prompt        AS question_prompt,
                q.type          AS question_type,
                COUNT(a.id)     AS answers_count
            FROM questions q
            LEFT JOIN answers a ON a.question_id = q.id
            WHERE q.id = :qid
            GROUP BY q.id, q.prompt, q.type
        """), {"qid": question_id}).mappings().first()
    
    if not row:
        raise HTTPException(status_code=404, detail="Question introuvable")
    
    question_data = dict(row)
    
    # Pour les questions single/multi choice, récupérer les stats
    chart_data = None
    if question_data['question_type'] in ('single_choice', 'multi_choice'):
        try:
            # Récupérer les statistiques
            if question_data['question_type'] == 'single_choice':
                stats_rows = db.execute(text("""
                    SELECT 
                        o.label,
                        COALESCE(COUNT(ao.option_id), 0) as count
                    FROM options o
                    LEFT JOIN answer_options ao ON ao.option_id = o.id
                    WHERE o.question_id = :qid
                    GROUP BY o.id, o.label, o.position
                    ORDER BY o.position
                    LIMIT 6
                """), {"qid": question_id}).mappings().all()
            else:  # multi_choice
                # Analyser les réponses texte avec pipes
                answers_rows = db.execute(text("""
                    SELECT a.text
                    FROM answers a
                    JOIN contributions c ON c.id = a.contribution_id
                    WHERE a.question_id = :qid
                      AND a.text IS NOT NULL
                      AND a.text LIKE '%|%'
                """), {"qid": question_id}).mappings().all()
                
                option_counts = {}
                for row in answers_rows:
                    if row["text"]:
                        options = [opt.strip() for opt in row["text"].split("|") if opt.strip()]
                        for option in options:
                            option_counts[option] = option_counts.get(option, 0) + 1
                
                # Prendre les 6 plus populaires
                stats_rows = [{"label": label, "count": count} 
                             for label, count in sorted(option_counts.items(), key=lambda x: x[1], reverse=True)[:6]]
            
            if stats_rows:
                chart_data = {
                    "labels": [row["label"] for row in stats_rows],
                    "data": [row["count"] for row in stats_rows],
                    "colors": ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#06b6d4"][:len(stats_rows)]
                }
                
        except Exception:
            # Si erreur avec les stats, on passe en mode texte simple
            chart_data = None
    
    question_data['chart_data'] = chart_data
    
    try:
        # Générer la clé de cache
        cache_key = _generate_cache_key_question(question_data)
        
        # Générer l'image
        image_path = await _generate_og_image_question(question_data, cache_key)
        
        # Retourner l'image
        return FileResponse(
            str(image_path), 
            media_type="image/png",
            headers={"Cache-Control": CACHE_OG_IMAGE}
        )
        
    except Exception as e:
        # En cas d'erreur, retourner une erreur 500
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération de l'image: {str(e)}")


def _generate_cache_key_form(form_data: dict) -> str:
    """Génère une clé de cache basée sur le contenu du formulaire"""
    content = f"form-{form_data['form_id']}-{form_data['form_name']}-{form_data['questions_count']}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]


def _create_og_html_template_form(form_data: dict) -> str:
    """Crée le HTML temporaire pour la génération d'image OG d'un formulaire"""
    form_name = form_data['form_name'] or f"Formulaire #{form_data['form_id']}"
    questions_count = form_data['questions_count'] or 0
    
    html = f'''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <title>OG Form</title>
    <style>
        body {{
            margin: 0;
            padding: 60px;
            width: 1200px;
            height: 630px;
            box-sizing: border-box;
            font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif;
            background: linear-gradient(135deg, #f2f1ea 0%, #fbfaf6 100%);
            color: #2B2A26;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}
        
        .container {{
            max-width: 1080px;
            margin: 0 auto;
            text-align: center;
        }}
        
        .form-title {{
            font-size: 48px;
            font-weight: 700;
            line-height: 1.2;
            margin-bottom: 40px;
            color: #2B2A26;
        }}
        
        .questions-count {{
            font-size: 28px;
            color: #6b6258;
            margin-bottom: 40px;
        }}
        
        .icon {{
            font-size: 80px;
            margin-bottom: 30px;
            color: #2B2A26;
        }}
        
        .brand {{
            position: absolute;
            bottom: 30px;
            left: 60px;
            font-size: 20px;
            color: #6b6258;
            font-weight: 500;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">📋</div>
        <div class="form-title">{form_name}</div>
        <div class="questions-count">{questions_count} question{'s' if questions_count != 1 else ''}</div>
    </div>
    <div class="brand">Cahier de doléances</div>
</body>
</html>'''
    
    return html


async def _generate_og_image_form(form_data: dict, cache_key: str) -> Path:
    """Génère l'image OG pour un formulaire avec Playwright"""
    cache_path = OG_CACHE_DIR / f"{cache_key}.png"
    
    # Si l'image est déjà en cache, la retourner
    if cache_path.exists():
        return cache_path
    
    # Créer le HTML temporaire
    html_content = _create_og_html_template_form(form_data)
    
    # Sauvegarder temporairement le HTML
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
        f.write(html_content)
        temp_html_path = f.name
    
    try:
        # Importer Playwright de manière asynchrone
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            # Lancer le navigateur
            browser = await p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage'])
            page = await browser.new_page()
            
            # Configurer la taille de viewport pour 1200x630
            await page.set_viewport_size({"width": 1200, "height": 630})
            
            # Charger le HTML
            await page.goto(f"file://{temp_html_path}")
            
            # Attendre que la page soit complètement chargée
            await page.wait_for_load_state('networkidle')
            
            # Prendre la capture d'écran
            await page.screenshot(path=str(cache_path), full_page=True)
            
            # Fermer le navigateur
            await browser.close()
            
    finally:
        # Supprimer le fichier HTML temporaire
        os.unlink(temp_html_path)
    
    return cache_path


@router.get("/og/form/{form_id}.png", name="og_form_image")
async def og_form_image(form_id: int):
    """Génère une image OG pour un formulaire spécifique"""
    
    with SessionLocal() as db:
        # Récupérer les données du formulaire
        row = db.execute(text("""
            SELECT
                f.id            AS form_id,
                f.name          AS form_name,
                COUNT(q.id)     AS questions_count
            FROM forms f
            LEFT JOIN questions q ON q.form_id = f.id
            WHERE f.id = :fid
            GROUP BY f.id, f.name
        """), {"fid": form_id}).mappings().first()
    
    if not row:
        raise HTTPException(status_code=404, detail="Formulaire introuvable")
    
    form_data = dict(row)
    
    try:
        # Générer la clé de cache
        cache_key = _generate_cache_key_form(form_data)
        
        # Générer l'image
        image_path = await _generate_og_image_form(form_data, cache_key)
        
        # Retourner l'image
        return FileResponse(
            str(image_path), 
            media_type="image/png",
            headers={"Cache-Control": CACHE_OG_IMAGE}
        )
        
    except Exception as e:
        # En cas d'erreur, retourner une erreur 500
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération de l'image: {str(e)}")
