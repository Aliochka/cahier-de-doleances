"""
Internationalization support for FastAPI
"""
import os
import json
from typing import Optional
from babel import Locale
from babel.support import Translations
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# Supported languages
LANGUAGES = {
    'fr': 'Français',
    'en': 'English'
}
DEFAULT_LANGUAGE = 'fr'

# Global translation objects
_translations = {}


def load_translations():
    """Load all translation files"""
    global _translations
    
    for lang_code in LANGUAGES.keys():
        try:
            translations = Translations.load(
                dirname='translations',
                locales=[lang_code],
                domain='messages'
            )
            _translations[lang_code] = translations
        except Exception as e:
            print(f"Warning: Could not load translations for {lang_code}: {e}")
            # Create a null translations object as fallback
            _translations[lang_code] = Translations()


def get_translation(language_code: str) -> Translations:
    """Get translation object for a specific language"""
    return _translations.get(language_code, _translations.get(DEFAULT_LANGUAGE))


def translate(message: str, language_code: str = DEFAULT_LANGUAGE) -> str:
    """Translate a message"""
    translation = get_translation(language_code)
    return translation.gettext(message)


def ngettext(singular: str, plural: str, count: int, language_code: str = DEFAULT_LANGUAGE) -> str:
    """Translate a message with plural support"""
    translation = get_translation(language_code)
    return translation.ngettext(singular, plural, count)


class I18nMiddleware(BaseHTTPMiddleware):
    """Middleware to handle language detection and context"""
    
    async def dispatch(self, request: Request, call_next):
        # Skip i18n for static files
        if request.url.path.startswith('/static/'):
            return await call_next(request)
            
        # Language detection priority:
        # 1. URL parameter (?lang=en)
        # 2. Session
        # 3. Accept-Language header
        # 4. Default language
        
        language = None
        
        # 1. URL parameter
        if 'lang' in request.query_params:
            lang = request.query_params['lang']
            if lang in LANGUAGES:
                language = lang
                # Store in session for future requests
                if "session" in request.scope:
                    request.session['language'] = language
        
        # 2. Session (only if SessionMiddleware is available)
        if not language and "session" in request.scope:
            language = request.session.get('language')
        
        # 3. Accept-Language header
        if not language:
            accept_language = request.headers.get('accept-language', '')
            for lang_code in LANGUAGES.keys():
                if lang_code in accept_language:
                    language = lang_code
                    break
        
        # 4. Default
        if not language or language not in LANGUAGES:
            language = DEFAULT_LANGUAGE
        
        # Store language in request state
        request.state.language = language
        
        # Continue processing
        response = await call_next(request)
        return response


def get_current_language(request: Request) -> str:
    """Get the current language from request"""
    return getattr(request.state, 'language', DEFAULT_LANGUAGE)


# Template functions
def _(message: str, request: Request = None) -> str:
    """Main translation function for templates"""
    if request:
        lang = get_current_language(request)
        return translate(message, lang)
    return translate(message, DEFAULT_LANGUAGE)


def ngettext_template(singular: str, plural: str, count: int, request: Request = None) -> str:
    """Plural translation function for templates"""
    if request:
        lang = get_current_language(request)
        return ngettext(singular, plural, count, lang)
    return ngettext(singular, plural, count, DEFAULT_LANGUAGE)


# Initialize translations on import
load_translations()