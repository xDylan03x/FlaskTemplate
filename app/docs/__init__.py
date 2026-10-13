from flask import Blueprint
from app import sm
from .module import module

docs = Blueprint("docs", __name__, template_folder="templates")
sm.register_module(module, blueprint=docs)

from app.docs import routes
