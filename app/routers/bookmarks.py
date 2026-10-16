import logging
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.db import SessionLocal
from app.models import Bookmark, User
from app.services.auth import auth_service

router = APIRouter()
logger = logging.getLogger(__name__)


def get_current_user(session_token: Optional[str] = Cookie(None)) -> User:
    """Dependency pour récupérer l'utilisateur connecté"""
    user = auth_service.get_current_user(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Connexion requise")
    return user


@router.post("/bookmarks/{page_type}/{page_id}")
def add_bookmark(page_type: str, page_id: int, user: User = Depends(get_current_user)):
    """
    Ajoute un marque-page pour l'utilisateur connecté
    """
    # Valider les types de pages acceptés
    valid_types = ["question", "answer", "author"]
    if page_type not in valid_types:
        raise HTTPException(
            status_code=400, detail=f"Type de page non valide. Types acceptés: {valid_types}"
        )

    with SessionLocal() as db:
        # La contrainte arbitre aussi les insertions concurrentes en base.
        bookmark_id = db.execute(
            insert(Bookmark)
            .values(user_id=user.id, page_type=page_type, page_id=page_id)
            .on_conflict_do_nothing(constraint="unique_user_bookmark")
            .returning(Bookmark.id)
        ).scalar_one_or_none()
        db.commit()

        if bookmark_id is None:
            return {"message": "Marque-page déjà existant", "success": True}

        logger.info(f"User {user.email} bookmarked {page_type}:{page_id}")

        return {
            "message": "Marque-page ajouté avec succès",
            "success": True,
            "bookmark_id": bookmark_id,
        }


@router.delete("/bookmarks/{page_type}/{page_id}")
def remove_bookmark(page_type: str, page_id: int, user: User = Depends(get_current_user)):
    """
    Supprime un marque-page pour l'utilisateur connecté
    """
    # Valider les types de pages acceptés
    valid_types = ["question", "answer", "author"]
    if page_type not in valid_types:
        raise HTTPException(
            status_code=400, detail=f"Type de page non valide. Types acceptés: {valid_types}"
        )

    with SessionLocal() as db:
        # Supprimer le marque-page s'il existe
        result = db.execute(
            delete(Bookmark).where(
                Bookmark.user_id == user.id,
                Bookmark.page_type == page_type,
                Bookmark.page_id == page_id,
            )
        )

        db.commit()

        if result.rowcount > 0:
            logger.info(f"User {user.email} removed bookmark {page_type}:{page_id}")
            return {"message": "Marque-page supprimé avec succès", "success": True}
        else:
            return {"message": "Marque-page introuvable", "success": False}


@router.get("/bookmarks/check/{page_type}/{page_id}")
def check_bookmark_status(page_type: str, page_id: int, user: User = Depends(get_current_user)):
    """
    Vérifie si une page est dans les marque-pages de l'utilisateur
    """
    # Valider les types de pages acceptés
    valid_types = ["question", "answer", "author"]
    if page_type not in valid_types:
        raise HTTPException(
            status_code=400, detail=f"Type de page non valide. Types acceptés: {valid_types}"
        )

    with SessionLocal() as db:
        bookmark = db.execute(
            select(Bookmark).where(
                Bookmark.user_id == user.id,
                Bookmark.page_type == page_type,
                Bookmark.page_id == page_id,
            )
        ).scalar_one_or_none()

        return {
            "is_bookmarked": bookmark is not None,
            "bookmark_id": bookmark.id if bookmark else None,
        }
