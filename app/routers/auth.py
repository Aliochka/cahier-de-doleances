from fastapi import APIRouter, Request, Form, HTTPException, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import logging
import re
import json

from app.services.auth import auth_service
from app.services.email import email_service
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

class EmailRequest(BaseModel):
    email: EmailStr

class LoginResponse(BaseModel):
    message: str
    success: bool

class ProfileUpdateRequest(BaseModel):
    nationalities: List[str]  # Liste des codes pays ISO (ex: ["FR", "DE"])

class ProfileUpdateResponse(BaseModel):
    message: str
    success: bool

class AnonymityToggleRequest(BaseModel):
    is_anonymous: bool
    display_name: Optional[str] = None  # Requis si is_anonymous=False

class AnonymityToggleResponse(BaseModel):
    message: str
    success: bool
    is_anonymous: bool

@router.post("/auth/send-link", response_model=LoginResponse)
async def send_magic_link(
    request: Request,
    email_data: EmailRequest
):
    """
    Envoie un lien magique de connexion par email
    """
    email = str(email_data.email).lower().strip()
    
    # Validation basique de l'email
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        raise HTTPException(status_code=400, detail="Email invalide")
    
    try:
        # Créer le token magique
        magic_token = auth_service.create_magic_token(email)
        
        # Construire l'URL du lien magique
        base_url = settings.BASE_URL
        if hasattr(request, 'headers'):
            scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
            netloc = request.headers.get("x-forwarded-host") or request.url.netloc
            base_url = f"{scheme}://{netloc}"
        
        magic_link = f"{base_url}/auth/verify/{magic_token}"
        
        # Envoyer l'email
        success = await email_service.send_magic_link(email, magic_link)
        
        if success:
            return LoginResponse(
                message="Un lien de connexion a été envoyé à votre adresse email.",
                success=True
            )
        else:
            raise HTTPException(
                status_code=500, 
                detail="Erreur lors de l'envoi de l'email. Veuillez réessayer."
            )
            
    except Exception as e:
        logger.error(f"Error sending magic link to {email}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Erreur interne. Veuillez réessayer plus tard."
        )

@router.get("/auth/verify/{token}")
async def verify_magic_link(token: str, request: Request):
    """
    Vérifie un lien magique et connecte l'utilisateur
    """
    # Vérifier le token magique
    email = auth_service.verify_magic_token(token)
    
    if not email:
        # Token invalide ou expiré
        return HTMLResponse("""
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <meta charset="utf-8">
            <title>Lien invalide</title>
            <style>
                body { font-family: system-ui, sans-serif; text-align: center; padding: 50px; }
                .error { color: #dc3545; }
            </style>
        </head>
        <body>
            <h1 class="error">Lien invalide ou expiré</h1>
            <p>Ce lien de connexion n'est plus valide. Veuillez en demander un nouveau.</p>
            <a href="/">Retour à l'accueil</a>
        </body>
        </html>
        """, status_code=400)
    
    try:
        # Créer ou récupérer l'utilisateur
        user = auth_service.get_or_create_user(email)
        
        # Créer un token de session
        session_token = auth_service.create_session_token(user.id)
        
        # Rediriger vers l'accueil avec le token en cookie
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(
            key="session_token",
            value=session_token,
            max_age=60 * 60 * 24 * 7,  # 7 jours
            httponly=True,
            secure=True,  # HTTPS uniquement en production
            samesite="lax"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error during magic link verification: {str(e)}")
        return HTMLResponse("""
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <meta charset="utf-8">
            <title>Erreur de connexion</title>
            <style>
                body { font-family: system-ui, sans-serif; text-align: center; padding: 50px; }
                .error { color: #dc3545; }
            </style>
        </head>
        <body>
            <h1 class="error">Erreur de connexion</h1>
            <p>Une erreur est survenue lors de la connexion. Veuillez réessayer.</p>
            <a href="/">Retour à l'accueil</a>
        </body>
        </html>
        """, status_code=500)

@router.post("/auth/logout")
async def logout():
    """
    Déconnecte l'utilisateur en supprimant le cookie de session
    """
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie(
        key="session_token",
        httponly=True,
        secure=True,
        samesite="lax"
    )
    return response

@router.get("/auth/me")
async def get_current_user_info(session_token: Optional[str] = Cookie(None)):
    """
    Retourne les informations de l'utilisateur connecté (pour les requêtes AJAX)
    """
    user = auth_service.get_current_user(session_token)
    
    if not user:
        raise HTTPException(status_code=401, detail="Non connecté")
    
    # Retourner les nationalités parsées
    nationalities = []
    if user.nationalities:
        try:
            nationalities = json.loads(user.nationalities)
        except (json.JSONDecodeError, TypeError):
            nationalities = []
    
    return {
        "id": user.id,
        "email": user.email,
        "is_authenticated": True,
        "created_at": user.created_at.isoformat(),
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "nationalities": nationalities,
        "profile_completed": user.profile_completed or False
    }

@router.post("/auth/complete-profile", response_model=ProfileUpdateResponse)
async def complete_profile(
    profile_data: ProfileUpdateRequest,
    session_token: Optional[str] = Cookie(None)
):
    """
    Complète le profil utilisateur avec les nationalités
    """
    user = auth_service.get_current_user(session_token)
    
    if not user:
        raise HTTPException(status_code=401, detail="Non connecté")
    
    # Validation des codes pays (ISO 3166-1 alpha-2)
    valid_country_codes = {
        "AD", "AE", "AF", "AG", "AI", "AL", "AM", "AO", "AQ", "AR", "AS", "AT", 
        "AU", "AW", "AX", "AZ", "BA", "BB", "BD", "BE", "BF", "BG", "BH", "BI", 
        "BJ", "BL", "BM", "BN", "BO", "BQ", "BR", "BS", "BT", "BV", "BW", "BY", 
        "BZ", "CA", "CC", "CD", "CF", "CG", "CH", "CI", "CK", "CL", "CM", "CN", 
        "CO", "CR", "CU", "CV", "CW", "CX", "CY", "CZ", "DE", "DJ", "DK", "DM", 
        "DO", "DZ", "EC", "EE", "EG", "EH", "ER", "ES", "ET", "FI", "FJ", "FK", 
        "FM", "FO", "FR", "GA", "GB", "GD", "GE", "GF", "GG", "GH", "GI", "GL", 
        "GM", "GN", "GP", "GQ", "GR", "GS", "GT", "GU", "GW", "GY", "HK", "HM", 
        "HN", "HR", "HT", "HU", "ID", "IE", "IL", "IM", "IN", "IO", "IQ", "IR", 
        "IS", "IT", "JE", "JM", "JO", "JP", "KE", "KG", "KH", "KI", "KM", "KN", 
        "KP", "KR", "KW", "KY", "KZ", "LA", "LB", "LC", "LI", "LK", "LR", "LS", 
        "LT", "LU", "LV", "LY", "MA", "MC", "MD", "ME", "MF", "MG", "MH", "MK", 
        "ML", "MM", "MN", "MO", "MP", "MQ", "MR", "MS", "MT", "MU", "MV", "MW", 
        "MX", "MY", "MZ", "NA", "NC", "NE", "NF", "NG", "NI", "NL", "NO", "NP", 
        "NR", "NU", "NZ", "OM", "PA", "PE", "PF", "PG", "PH", "PK", "PL", "PM", 
        "PN", "PR", "PS", "PT", "PW", "PY", "QA", "RE", "RO", "RS", "RU", "RW", 
        "SA", "SB", "SC", "SD", "SE", "SG", "SH", "SI", "SJ", "SK", "SL", "SM", 
        "SN", "SO", "SR", "SS", "ST", "SV", "SX", "SY", "SZ", "TC", "TD", "TF", 
        "TG", "TH", "TJ", "TK", "TL", "TM", "TN", "TO", "TR", "TT", "TV", "TW", 
        "TZ", "UA", "UG", "UM", "US", "UY", "UZ", "VA", "VC", "VE", "VG", "VI", 
        "VN", "VU", "WF", "WS", "YE", "YT", "ZA", "ZM", "ZW"
    }
    
    # Valider les codes pays
    for country_code in profile_data.nationalities:
        if country_code not in valid_country_codes:
            raise HTTPException(
                status_code=400, 
                detail=f"Code pays invalide: {country_code}"
            )
    
    # Limiter à maximum 3 nationalités
    if len(profile_data.nationalities) > 3:
        raise HTTPException(
            status_code=400, 
            detail="Maximum 3 nationalités autorisées"
        )
    
    # Au moins une nationalité requise
    if len(profile_data.nationalities) == 0:
        raise HTTPException(
            status_code=400, 
            detail="Au moins une nationalité est requise"
        )
    
    try:
        # Mettre à jour le profil utilisateur
        updated_user = auth_service.update_user_profile(
            user.id, 
            nationalities=profile_data.nationalities
        )
        
        if updated_user:
            logger.info(f"Profile completed for user {user.email}")
            return ProfileUpdateResponse(
                message="Profil complété avec succès",
                success=True
            )
        else:
            raise HTTPException(
                status_code=500, 
                detail="Erreur lors de la mise à jour du profil"
            )
            
    except Exception as e:
        logger.error(f"Error updating profile for user {user.email}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Erreur interne lors de la mise à jour du profil"
        )

@router.post("/auth/toggle-anonymity", response_model=AnonymityToggleResponse)
async def toggle_author_anonymity(
    anonymity_data: AnonymityToggleRequest,
    session_token: Optional[str] = Cookie(None)
):
    """
    Bascule l'anonymat de la page author de l'utilisateur connecté
    """
    user = auth_service.get_current_user(session_token)
    
    if not user:
        raise HTTPException(status_code=401, detail="Non connecté")
    
    # Si l'utilisateur veut rendre son profil public, un nom d'affichage est requis
    if not anonymity_data.is_anonymous:
        if not anonymity_data.display_name or not anonymity_data.display_name.strip():
            raise HTTPException(
                status_code=400, 
                detail="Un nom d'affichage est requis pour rendre le profil public"
            )
        
        # Valider la longueur du nom d'affichage
        display_name = anonymity_data.display_name.strip()
        if len(display_name) < 2:
            raise HTTPException(
                status_code=400, 
                detail="Le nom d'affichage doit contenir au moins 2 caractères"
            )
        if len(display_name) > 100:
            raise HTTPException(
                status_code=400, 
                detail="Le nom d'affichage ne peut pas dépasser 100 caractères"
            )
    
    try:
        # Basculer l'anonymat de l'author
        updated_user = auth_service.toggle_author_anonymity(
            user.id,
            is_anonymous=anonymity_data.is_anonymous,
            display_name=anonymity_data.display_name
        )
        
        if updated_user:
            message = "Profil rendu anonyme" if anonymity_data.is_anonymous else f"Profil rendu public sous le nom '{anonymity_data.display_name}'"
            logger.info(f"Anonymity toggled for user {user.email}: is_anonymous={anonymity_data.is_anonymous}")
            
            return AnonymityToggleResponse(
                message=message,
                success=True,
                is_anonymous=anonymity_data.is_anonymous
            )
        else:
            raise HTTPException(
                status_code=500, 
                detail="Erreur lors de la mise à jour de l'anonymat"
            )
            
    except Exception as e:
        logger.error(f"Error toggling anonymity for user {user.email}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Erreur interne lors de la mise à jour de l'anonymat"
        )

@router.get("/auth/author-info")
async def get_author_info(session_token: Optional[str] = Cookie(None)):
    """
    Retourne les informations author de l'utilisateur connecté
    """
    user = auth_service.get_current_user(session_token)
    
    if not user:
        raise HTTPException(status_code=401, detail="Non connecté")
    
    if not user.author_id:
        raise HTTPException(status_code=404, detail="Aucune page author associée")
    
    # Récupérer les informations de l'author
    from app.db import SessionLocal
    from app.models import Author
    from sqlalchemy import select
    
    with SessionLocal() as db:
        author = db.execute(
            select(Author).where(Author.id == user.author_id)
        ).scalar_one_or_none()
        
        if not author:
            raise HTTPException(status_code=404, detail="Page author introuvable")
        
        return {
            "author_id": author.id,
            "is_anonymous": author.is_anonymous,
            "display_name": author.name,
            "author_url": f"/authors/{author.id}"
        }