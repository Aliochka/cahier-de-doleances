import logging

from mailjet_rest import Client
from starlette.concurrency import run_in_threadpool

from app.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service d'envoi d'email avec Mailjet"""

    def __init__(self):
        if not settings.MAILJET_API_KEY or not settings.MAILJET_SECRET_KEY:
            logger.warning(
                "Mailjet not configured; delivery unavailable unless development logging is enabled"
            )
            self.client = None
        else:
            self.client = Client(
                auth=(settings.MAILJET_API_KEY, settings.MAILJET_SECRET_KEY), version="v3.1"
            )

    async def send_magic_link(self, email: str, magic_link: str) -> bool:
        """
        Envoie un lien magique de connexion par email
        """
        subject = "Connexion à votre compte - Cahier de doléances"

        html_content = f"""
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <meta charset="utf-8">
            <title>{subject}</title>
            <style>
                body {{ font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #f2f1ea 0%, #fbfaf6 100%); padding: 30px 20px; text-align: center; border-radius: 8px 8px 0 0; }}
                .content {{ background: white; padding: 30px 20px; border: 1px solid #eee; }}
                .button {{ display: inline-block; background: #2B2A26; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .footer {{ background: #f8f9fa; padding: 20px; text-align: center; border-radius: 0 0 8px 8px; font-size: 14px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Cahier de doléances</h1>
                </div>
                <div class="content">
                    <h2>Connexion à votre compte</h2>
                    <p>Bonjour,</p>
                    <p>Cliquez sur le bouton ci-dessous pour vous connecter à votre compte :</p>
                    <p style="text-align: center;">
                        <a href="{magic_link}" class="button">Se connecter</a>
                    </p>
                    <p><strong>Ce lien est valable pendant 15 minutes.</strong></p>
                    <p>Si vous n'avez pas demandé cette connexion, vous pouvez ignorer cet email.</p>
                </div>
                <div class="footer">
                    <p>Cahier de doléances • Plateforme de participation citoyenne</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
        Connexion à votre compte - Cahier de doléances
        
        Bonjour,
        
        Cliquez sur ce lien pour vous connecter à votre compte :
        {magic_link}
        
        Ce lien est valable pendant 15 minutes.
        
        Si vous n'avez pas demandé cette connexion, vous pouvez ignorer cet email.
        
        ---
        Cahier de doléances
        Plateforme de participation citoyenne
        """

        return await self._send_email(
            to_email=email, subject=subject, html_content=html_content, text_content=text_content
        )

    async def _send_email(
        self, to_email: str, subject: str, html_content: str, text_content: str
    ) -> bool:
        """Envoi d'email générique via Mailjet"""

        if not self.client:
            if not settings.LOG_MAGIC_LINKS:
                logger.error("Email delivery unavailable: configure Mailjet credentials")
                return False
            # En mode développement, extraire et afficher clairement le lien magique
            import re

            magic_link_match = re.search(
                r'http[s]?://[^\s<>"]+/auth/verify/[^\s<>"]+', text_content
            )

            print("\n" + "=" * 60)
            print("📧 EMAIL DE DÉVELOPPEMENT")
            print(f"À: {to_email}")
            print(f"Objet: {subject}")

            if magic_link_match:
                magic_link = magic_link_match.group()
                print("🔗 LIEN MAGIQUE À COPIER:")
                print(f"   {magic_link}")
            else:
                print("❌ Lien magique non trouvé dans le contenu")

            print("=" * 60 + "\n")

            # Log pour les fichiers de logs aussi
            logger.info(
                f"Magic link sent to {to_email}: {magic_link if magic_link_match else 'not found'}"
            )
            return True

        data = {
            "Messages": [
                {
                    "From": {"Email": settings.FROM_EMAIL, "Name": settings.FROM_NAME},
                    "To": [{"Email": to_email, "Name": ""}],
                    "Subject": subject,
                    "TextPart": text_content,
                    "HTMLPart": html_content,
                    "CustomID": f"magic-link-{to_email}",
                }
            ]
        }

        try:
            result = await run_in_threadpool(self.client.send.create, data=data)
            if result.status_code == 200:
                logger.info(f"Email sent successfully to {to_email}")
                return True
            else:
                logger.error(f"Failed to send email: HTTP {result.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {str(e)}")
            return False


# Singleton
email_service = EmailService()
