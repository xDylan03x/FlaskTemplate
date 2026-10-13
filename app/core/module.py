from ..extensions.flask_settings import ModuleSpec
from .settings import settings

module = ModuleSpec(
    name="Core",
    description="Application layout, account preferences, and user and system administration.",
    settings=settings,
    version="1.3.0",
)
