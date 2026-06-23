from flask import Blueprint
from app import pm
from .permissions import permissions

core = Blueprint("core", __name__, template_folder="templates")
pm.register_many(permissions)

from app.core import routes
