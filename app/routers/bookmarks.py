import logging
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import joinedload

from app.db import SessionLocal
from app.helpers import public_author
from app.models import Answer, Author, Bookmark, Contribution, Question, User
from app.services.auth import auth_service
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
async def add_bookmark(page_type: str, page_id: int, user: User = Depends(get_current_user)):
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
        # Vérifier si le marque-page existe déjà
        existing = db.execute(
            select(Bookmark).where(
                Bookmark.user_id == user.id,
                Bookmark.page_type == page_type,
                Bookmark.page_id == page_id,
            )
        ).scalar_one_or_none()

        if existing:
            return {"message": "Marque-page déjà existant", "success": True}

        # Créer le nouveau marque-page
        bookmark = Bookmark(user_id=user.id, page_type=page_type, page_id=page_id)

        db.add(bookmark)
        db.commit()

        logger.info(f"User {user.email} bookmarked {page_type}:{page_id}")

        return {
            "message": "Marque-page ajouté avec succès",
            "success": True,
            "bookmark_id": bookmark.id,
        }


@router.delete("/bookmarks/{page_type}/{page_id}")
async def remove_bookmark(page_type: str, page_id: int, user: User = Depends(get_current_user)):
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


@router.get("/bookmarks")
async def list_user_bookmarks(request: Request, user: User = Depends(get_current_user)):
    """
    Affiche la page des marque-pages de l'utilisateur
    """
    with SessionLocal() as db:
        # Récupérer tous les marque-pages de l'utilisateur
        bookmarks = (
            db.execute(
                select(Bookmark)
                .where(Bookmark.user_id == user.id)
                .order_by(Bookmark.created_at.desc())
            )
            .scalars()
            .all()
        )

        # Grouper par type de page et enrichir avec les données associées
        bookmarks_by_type = {"question": [], "answer": [], "author": []}

        for bookmark in bookmarks:
            if bookmark.page_type in bookmarks_by_type:
                # Enrichir avec les données selon le type
                if bookmark.page_type == "question":
                    question = db.execute(
                        select(Question).where(Question.id == bookmark.page_id)
                    ).scalar_one_or_none()

                    if question:
                        bookmark.content = question
                        bookmarks_by_type[bookmark.page_type].append(bookmark)

                elif bookmark.page_type == "answer":
                    answer = db.execute(
                        select(Answer)
                        .options(joinedload(Answer.question))
                        .where(Answer.id == bookmark.page_id)
                    ).scalar_one_or_none()

                    if answer:
                        # Préparer les données pour le template answers/_card.html
                        answer.body = answer.text  # Adapter le nom du champ
                        answer.question_title = answer.question.prompt if answer.question else None
                        answer.question_prompt = answer.question.prompt if answer.question else None
                        # Les questions n'ont pas de slug dans ce modèle, on peut les ignorer
                        answer.question_slug = None

                        # Récupérer les infos d'auteur si disponibles via contribution
                        if answer.contribution_id:
                            contribution = db.execute(
                                select(Contribution)
                                .options(joinedload(Contribution.author))
                                .where(Contribution.id == answer.contribution_id)
                            ).scalar_one_or_none()

                            if contribution and contribution.author:
                                answer.author_id = contribution.author.id
                                answer.author_name = public_author(
                                    contribution.author.id,
                                    contribution.author.name,
                                    contribution.author.is_anonymous,
                                )["name"]
                                answer.author_slug = None  # Pas de slug dans ce modèle

                        bookmark.content = answer
                        bookmarks_by_type[bookmark.page_type].append(bookmark)

                elif bookmark.page_type == "author":
                    author = db.execute(
                        select(Author).where(Author.id == bookmark.page_id)
                    ).scalar_one_or_none()

                    if author:
                        # Calculer le nombre de réponses via les contributions
                        answers_count = db.execute(
                            select(func.count(Answer.id))
                            .join(Contribution, Answer.contribution_id == Contribution.id)
                            .where(Contribution.author_id == author.id)
                        ).scalar()

                        bookmark.content = {
                            **public_author(author.id, author.name, author.is_anonymous),
                            "answers_count": answers_count or 0,
                        }
                        bookmarks_by_type[bookmark.page_type].append(bookmark)

        return templates.TemplateResponse(
            request,
            "bookmarks/list.html",
            {
                "request": request,
                "user": user,
                "bookmarks_by_type": bookmarks_by_type,
                "total_bookmarks": len(bookmarks),
            },
        )


@router.get("/bookmarks/check/{page_type}/{page_id}")
async def check_bookmark_status(
    page_type: str, page_id: int, user: User = Depends(get_current_user)
):
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
