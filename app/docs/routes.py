from flask_login import current_user
from app.docs import docs
from flask import render_template, request, current_app, abort
import os
from app.model_managers import SystemManager
from .helper import ArticleRegistry


@docs.route('')
@docs.route('/<path:slug>')
def articles(slug=None):
    if SystemManager.get_setting('restrict_docs') and current_user.is_anonymous:
        abort(403)
    query = request.args.get("query", "").strip()
    include_private = current_user.is_authenticated
    htmx = request.headers.get('HX-Request', False)

    content_path = os.path.join(current_app.root_path, "docs", "content")
    index_path = os.path.join(current_app.root_path, "docs", "index")
    am = ArticleRegistry(content_path, index_path)
    menu_items = am.get_menu_items(include_private=include_private)

    # If the user searched for something
    if query:
        searched_articles = am.search_articles(query.strip(), include_private)
        return render_template("catalog.html", title="Article Search", tab="all", menu_items=menu_items, query=True, articles=searched_articles, htmx=htmx)

    # If the user is looking for a specific article or group
    if slug is not None:
        article = am.get_article_by_slug(slug)

        # If the user is looking for a specific article
        if article is not None:
            if article.visibility == "private" and not include_private:
                abort(403)
            return render_template("article.html", tab=slug, menu_items=menu_items, title=article.title, article=article, htmx=htmx)

        # If the user is looking for a specific group
        grouped_articles = am.get_articles(group_slug=slug, include_private=include_private)
        if grouped_articles:
            return render_template("catalog.html", title=f"Articles in {slug.title()}", tab=slug, menu_items=menu_items, query=None, articles=grouped_articles, htmx=htmx)

        # If no article or group was found
        abort(404)

    # If the user is just browsing the catalog of all articles
    grouped_articles = am.get_articles(include_private=include_private)
    return render_template("catalog.html", title="All Articles", tab="all", menu_items=menu_items, query=None, articles=grouped_articles, htmx=htmx)
