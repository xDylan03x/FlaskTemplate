from flask import Blueprint
from app import pm, sm
from .permissions import permissions
from .settings import settings

core = Blueprint("core", __name__, template_folder="templates")
pm.register_many(permissions)
sm.register_many(settings)

from app.core import routes
