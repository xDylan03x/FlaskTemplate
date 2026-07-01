from flask import Blueprint

apiv1 = Blueprint('api', __name__)

from app.api import routes
