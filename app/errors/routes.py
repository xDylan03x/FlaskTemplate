from app.errors import errors
from flask import current_app, render_template
from app import db


@errors.app_errorhandler(404)
def not_found_error(error):
    if current_app.config["DEBUG"]:
        return render_template("404.html", error=error), 404
    return render_template('404.html'), 404


@errors.app_errorhandler(405)
def not_found_error(error):
    if current_app.config["DEBUG"]:
        return render_template("405.html", error=error), 405
    return render_template('405.html'), 405


@errors.app_errorhandler(500)
def internal_error(error):
    db.session.rollback()
    if current_app.config["DEBUG"]:
        return render_template("500.html", error=error), 500
    return render_template('500.html'), 500
