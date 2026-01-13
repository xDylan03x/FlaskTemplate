from flask import Blueprint

pm = Blueprint("pm", __name__, template_folder="templates")

from app.pm import routes
