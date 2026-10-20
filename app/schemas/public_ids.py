from typing import Annotated

from pydantic import Field

PublicId = Annotated[
    str,
    Field(
        pattern=r"^[0-9]+$",
        description="Identifiant historique BIGINT, chaîne décimale sans perte de précision.",
    ),
]
