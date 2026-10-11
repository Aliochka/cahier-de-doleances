import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import jwt
from jwt import InvalidTokenError as JWTError
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Author, User

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"


class AuthService:
    """Service d'authentification avec magic links"""

    def create_magic_token(self, email: str, expires_delta: Optional[timedelta] = None) -> str:
        """
        Crée un token JWT pour un magic link
        """
        if expires_delta is None:
            expires_delta = timedelta(minutes=15)  # Magic link valide 15 minutes

        expire = datetime.now(timezone.utc) + expires_delta
        to_encode = {
            "sub": email,
            "exp": expire,
            "type": "magic_link",
            "jti": secrets.token_urlsafe(16),  # JWT ID unique
        }

        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    def verify_magic_token(self, token: str) -> Optional[str]:
        """
        Vérifie un magic token et retourne l'email s'il est valide
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
            email: str = payload.get("sub")
            token_type: str = payload.get("type")

            if email is None or token_type != "magic_link":
                return None

            return email
        except JWTError:
            logger.warning("Invalid magic token received")
            return None

    def create_session_token(self, user_id: int, expires_delta: Optional[timedelta] = None) -> str:
        """
        Crée un token de session JWT pour un utilisateur connecté
        """
        if expires_delta is None:
            expires_delta = timedelta(days=7)  # Session valide 7 jours

        expire = datetime.now(timezone.utc) + expires_delta
        to_encode = {
            "sub": str(user_id),
            "exp": expire,
            "type": "session",
            "iat": datetime.now(timezone.utc),
        }

        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    def verify_session_token(self, token: str) -> Optional[int]:
        """
        Vérifie un token de session et retourne l'user_id s'il est valide
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
            user_id_str: str = payload.get("sub")
            token_type: str = payload.get("type")

            if user_id_str is None or token_type != "session":
                return None

            user_id = int(user_id_str)
            return user_id
        except (JWTError, ValueError):
            return None

    def get_or_create_user(self, email: str) -> User:
        """
        Récupère un utilisateur par email ou le crée s'il n'existe pas
        Crée automatiquement un Author associé pour les nouveaux utilisateurs
        """
        with SessionLocal() as db:
            # Chercher l'utilisateur existant
            user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()

            if user is None:
                # Créer un Author vide d'abord (anonyme par défaut)
                author = Author(
                    is_anonymous=True,
                    name=None,
                    user_id=None,  # Sera mis à jour après création du User
                )
                db.add(author)
                db.flush()  # Pour obtenir l'ID de l'author

                # Créer l'utilisateur avec l'author_id
                user = User(
                    email=email,
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                    author_id=author.id,
                )
                db.add(user)
                db.flush()  # Pour obtenir l'ID du user

                # Lier l'author au user
                author.user_id = user.id

                db.commit()
                db.refresh(user)
                logger.info(f"Created new user: {email} with author_id: {author.id}")
            else:
                # Mettre à jour la date de dernière connexion
                user.last_login = datetime.now(timezone.utc)
                db.commit()
                db.refresh(user)
                logger.info(f"User login: {email}")

            return user

    def get_current_user(self, token: Optional[str]) -> Optional[User]:
        """
        Récupère l'utilisateur actuellement connecté à partir du token de session
        """
        if not token:
            return None

        user_id = self.verify_session_token(token)
        if not user_id:
            return None

        with SessionLocal() as db:
            user = db.execute(
                select(User).where(User.id == user_id, User.is_active.is_(True))
            ).scalar_one_or_none()

            return user

    def update_user_profile(self, user_id: int, nationalities: List[str]) -> Optional[User]:
        """
        Met à jour le profil utilisateur avec les nationalités
        """
        with SessionLocal() as db:
            user = db.execute(
                select(User).where(User.id == user_id, User.is_active.is_(True))
            ).scalar_one_or_none()

            if not user:
                return None

            # Convertir les nationalités en JSON
            user.nationalities = json.dumps(nationalities)
            user.profile_completed = True

            db.commit()
            db.refresh(user)

            logger.info(
                f"Updated profile for user {user.email} with nationalities: {nationalities}"
            )
            return user


# Singleton
auth_service = AuthService()
