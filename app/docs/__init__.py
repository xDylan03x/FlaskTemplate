from flask import Blueprint

docs = Blueprint("docs", __name__, template_folder="templates")

from app.docs import routes
