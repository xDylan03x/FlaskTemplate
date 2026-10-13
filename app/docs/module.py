from ..extensions.flask_settings import ModuleSpec
from .settings import settings

module = ModuleSpec(
    name="Documentation",
    description="Browsable and searchable application documentation.",
    settings=settings,
    version="0.1.0",
)
