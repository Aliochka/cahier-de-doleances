"""
Internationalization routes
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from app.i18n import LANGUAGES

router = APIRouter()



@router.get("/set-language/{language_code}")
async def set_language(language_code: str, request: Request):
    """
    Set the user's language preference
    """
    if language_code not in LANGUAGES:
        raise HTTPException(status_code=400, detail="Unsupported language")
    
    # Store in session (if session middleware is available)
    if "session" in request.scope:
        request.session['language'] = language_code
    
    # Redirect back to the referring page or home
    referer = request.headers.get('referer')
    if referer:
        # Remove any existing lang parameter and add new one
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        parsed = urlparse(referer)
        query_params = parse_qs(parsed.query)
        query_params['lang'] = [language_code]
        new_query = urlencode(query_params, doseq=True)
        new_url = urlunparse((
            parsed.scheme, parsed.netloc, parsed.path,
            parsed.params, new_query, parsed.fragment
        ))
        return RedirectResponse(new_url, status_code=302)
    else:
        # Fallback to home with language parameter
        return RedirectResponse(f"/?lang={language_code}", status_code=302)