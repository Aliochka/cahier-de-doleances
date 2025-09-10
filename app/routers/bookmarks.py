from fastapi import APIRouter, Request, HTTPException, Cookie, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from typing import Optional
import logging

from app.services.auth import auth_service
from app.models import User, Bookmark
from app.db import SessionLocal
from app.web import templates

router = APIRouter()
logger = logging.getLogger(__name__)

def get_current_user(session_token: Optional[str] = Cookie(None)) -> User:
    """Dependency pour récupérer l'utilisateur connecté"""
    user = auth_service.get_current_user(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Connexion requise")
    return user

@router.post("/bookmarks/{page_type}/{page_id}")
async def add_bookmark(
    page_type: str,
    page_id: int,
    user: User = Depends(get_current_user)
):
    """
    Ajoute un marque-page pour l'utilisateur connecté
    """
    # Valider les types de pages acceptés
    valid_types = ["question", "answer", "author"]
    if page_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Type de page non valide. Types acceptés: {valid_types}")
    
    with SessionLocal() as db:
        # Vérifier si le marque-page existe déjà
        existing = db.execute(
            select(Bookmark).where(
                Bookmark.user_id == user.id,
                Bookmark.page_type == page_type,
                Bookmark.page_id == page_id
            )
        ).scalar_one_or_none()
        
        if existing:
            return {"message": "Marque-page déjà existant", "success": True}
        
        # Créer le nouveau marque-page
        bookmark = Bookmark(
            user_id=user.id,
            page_type=page_type,
            page_id=page_id
        )
        
        db.add(bookmark)
        db.commit()
        
        logger.info(f"User {user.email} bookmarked {page_type}:{page_id}")
        
        return {
            "message": "Marque-page ajouté avec succès",
            "success": True,
            "bookmark_id": bookmark.id
        }

@router.delete("/bookmarks/{page_type}/{page_id}")
async def remove_bookmark(
    page_type: str,
    page_id: int,
    user: User = Depends(get_current_user)
):
    """
    Supprime un marque-page pour l'utilisateur connecté
    """
    # Valider les types de pages acceptés
    valid_types = ["question", "answer", "author"]
    if page_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Type de page non valide. Types acceptés: {valid_types}")
    
    with SessionLocal() as db:
        # Supprimer le marque-page s'il existe
        result = db.execute(
            delete(Bookmark).where(
                Bookmark.user_id == user.id,
                Bookmark.page_type == page_type,
                Bookmark.page_id == page_id
            )
        )
        
        db.commit()
        
        if result.rowcount > 0:
            logger.info(f"User {user.email} removed bookmark {page_type}:{page_id}")
            return {"message": "Marque-page supprimé avec succès", "success": True}
        else:
            return {"message": "Marque-page introuvable", "success": False}

@router.get("/bookmarks")
async def list_user_bookmarks(
    request: Request,
    user: User = Depends(get_current_user)
):
    """
    Affiche la page des marque-pages de l'utilisateur
    """
    with SessionLocal() as db:
        # Récupérer tous les marque-pages de l'utilisateur
        bookmarks = db.execute(
            select(Bookmark)
            .where(Bookmark.user_id == user.id)
            .order_by(Bookmark.created_at.desc())
        ).scalars().all()
        
        # Grouper par type de page pour un affichage organisé
        bookmarks_by_type = {
            "question": [],
            "answer": [],
            "author": []
        }
        
        for bookmark in bookmarks:
            if bookmark.page_type in bookmarks_by_type:
                bookmarks_by_type[bookmark.page_type].append(bookmark)
        
        return templates.TemplateResponse("bookmarks/list.html", {
            "request": request,
            "user": user,
            "bookmarks_by_type": bookmarks_by_type,
            "total_bookmarks": len(bookmarks)
        })

@router.get("/bookmarks/check/{page_type}/{page_id}")
async def check_bookmark_status(
    page_type: str,
    page_id: int,
    user: User = Depends(get_current_user)
):
    """
    Vérifie si une page est dans les marque-pages de l'utilisateur
    """
    # Valider les types de pages acceptés
    valid_types = ["question", "answer", "author"]
    if page_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Type de page non valide. Types acceptés: {valid_types}")
    
    with SessionLocal() as db:
        bookmark = db.execute(
            select(Bookmark).where(
                Bookmark.user_id == user.id,
                Bookmark.page_type == page_type,
                Bookmark.page_id == page_id
            )
        ).scalar_one_or_none()
        
        return {
            "is_bookmarked": bookmark is not None,
            "bookmark_id": bookmark.id if bookmark else None
        }