from flask import Blueprint
from app import pm
from .permissions import permissions

apiv1 = Blueprint('api', __name__)
pm.register_many(permissions)

from app.api import routes
