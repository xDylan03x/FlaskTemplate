from flask import render_template, request

from app.core import core


@core.route('/')
def index():
    return render_template('index.html')


@core.route("/external-redirect")
def external_redirect():
    next_url = request.args.get("next", None)
    return render_template("external-redirect.html", url=next_url)
