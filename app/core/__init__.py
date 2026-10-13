from flask import Blueprint
from app import pm, sm
from .permissions import permissions
from .module import module

core = Blueprint("core", __name__, template_folder="templates")
pm.register_many(permissions)
sm.register_module(module, blueprint=core)

from app.core import routes
