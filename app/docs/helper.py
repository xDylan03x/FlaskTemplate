import shutil
from dataclasses import dataclass, field
from pathlib import Path
import markdown
import yaml
from flask import current_app, url_for
from markupsafe import Markup
import re
from whoosh import index
from whoosh.analysis import StemmingAnalyzer
from whoosh.fields import Schema, ID, TEXT, KEYWORD, NUMERIC
from whoosh.qparser import MultifieldParser, OrGroup
from whoosh.scoring import BM25F

from app.model_managers import SystemManager


@dataclass
class Article:
    title: str
    description: str
    group: str
    visibility: str
    order: int
    topics: list[str]
    content: str
    slug: str
    breadcrumbs: list[dict] = field(default_factory=list)

    @property
    def html_content(self):
        context = {
            "article": self,
            "doc_link_search": self._doc_link_search,
            "doc_link_article": self._doc_link_article,
            "image_link": self._image_link,
            "get_system_setting": SystemManager.get_setting
        }
        current_app.update_template_context(context)
        rendered_markdown = current_app.jinja_env.from_string(self.content).render(context)
        raw_html = markdown.markdown(
            rendered_markdown,
            extensions=["fenced_code", "tables", "toc", "sane_lists"],
            output_format="html5",
        )
        return Markup(raw_html)

    @property
    def searchable_content(self) -> str:
        value = re.sub(r"```.*?```", " ", self.content, flags=re.DOTALL)
        value = re.sub(r"`([^`]*)`", r"\1", value)
        value = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", value)
        value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
        value = re.sub(r"[#>*_\-]+", " ", value)
        value = re.sub(r"\s+", " ", value)
        return value.strip()

    @staticmethod
    def _doc_link_search(query: str) -> str:
        return url_for("docs.articles", query=query)

    @staticmethod
    def _doc_link_article(slug: str) -> str:
        return url_for("docs.articles", slug=slug)

    @staticmethod
    def _image_link(path: str):
        return url_for("static", filename=f"images/docs/{path}")


class ArticleRegistry:
    def __init__(self, content_directory: str, index_directory: str):
        self.articles: dict[str, Article] = {}
        self.content_directory = Path(content_directory)
        self.index_directory = Path(index_directory)
        self.load()
        self.rebuild_search_index()

    def load(self):
        self.articles.clear()
        if not self.content_directory.exists():
            return
        for path in self.content_directory.rglob("*.md"):
            article = self._load_article(path)
            if article:
                self.articles[article.slug] = article

    def get_menu_items(self, include_private: bool = False) -> list[dict]:
        all_articles = self.get_articles(include_private=include_private)
        return all_articles

    def rebuild_search_index(self):
        self.index_directory.mkdir(parents=True, exist_ok=True)

        if self._index_exists():
            shutil.rmtree(self.index_directory)
            self.index_directory.mkdir(parents=True, exist_ok=True)

        schema = self._search_schema()
        ix = index.create_in(str(self.index_directory), schema)

        writer = ix.writer()

        for article in self.articles.values():
            writer.add_document(
                slug=article.slug,
                title=article.title,
                description=article.description,
                group=article.group,
                group_slug=self.slugify(article.group),
                visibility=article.visibility,
                order=article.order,
                topics=" ".join(article.topics or []),
                content=article.searchable_content,
            )

        writer.commit()

    def get_article_by_slug(self, slug: str) -> Article | None:
        return self.articles.get(slug)

    def get_articles(self, group_slug: str | None = None, include_private: bool = False) -> list[dict]:
        if group_slug is not None:
            group_slug = group_slug.strip("/")
        grouped: dict[str, dict] = {}

        for article in self.articles.values():
            group_key = self.slugify(article.group)
            if group_slug is not None:
                if self.slugify(group_key) != group_slug:
                    continue
            if article.visibility == "private" and not include_private:
                continue
            if group_key not in grouped:
                grouped[group_key] = {
                    "title": article.group,
                    "slug": group_key,
                    "articles": [],
                }
            grouped[group_key]["articles"].append(article)
        # Sort articles inside each group
        for group in grouped.values():
            group["articles"].sort(key=lambda article: (article.order, article.title.lower()))

        # Sort groups by their lowest article order, then group title
        return sorted(
            grouped.values(),
            key=lambda group: (group["articles"][0].order if group["articles"] else 100, group["title"].lower())
        )

    def search_articles(self, query: str, include_private: bool = False) -> list[Article]:
        query = query.strip()

        if not query:
            return []

        if not self._index_exists():
            self.rebuild_search_index()

        ix = index.open_dir(str(self.index_directory))

        parser = MultifieldParser(["title", "description", "content", "topics", "group"], schema=ix.schema, group=OrGroup.factory(0.9))
        parsed_query = parser.parse(query)
        results = []
        with ix.searcher(
                weighting=BM25F(
                    field_B={
                        "title": 1.0,
                        "topics": 0.75,
                        "description": 1.0,
                        "content": 0.75,
                        "group": 1.0,
                    },
                    title_B=1.0,
                    topics_B=1.0,
                    description_B=1.0,
                    content_B=0.75,
                    group_B=1.0,
                )
        ) as searcher:
            hits = searcher.search(parsed_query, limit=50)

            for hit in hits:
                article = self.get_article_by_slug(hit["slug"])

                if article is None:
                    continue

                if article.visibility == "private" and not include_private:
                    continue

                article.search_score = hit.score
                results.append(article)

        return sorted(results, key=lambda article: article.search_score, reverse=True)

    def _index_exists(self) -> bool:
        return self.index_directory.exists() and index.exists_in(str(self.index_directory))

    def _search_schema(self) -> Schema:
        analyzer = StemmingAnalyzer()

        return Schema(
            slug=ID(stored=True, unique=True),
            title=TEXT(stored=True, analyzer=analyzer, field_boost=5.0),
            description=TEXT(stored=True, analyzer=analyzer, field_boost=2.0),
            group=TEXT(stored=True, analyzer=analyzer, field_boost=2.0),
            group_slug=ID(stored=True),
            visibility=ID(stored=True),
            order=NUMERIC(stored=True, sortable=True),
            topics=KEYWORD(
                stored=True,
                commas=False,
                lowercase=True,
                scorable=True,
                field_boost=4.0,
            ),
            content=TEXT(stored=False, analyzer=analyzer, field_boost=1.0),
        )

    def _load_article(self, path: Path) -> Article | None:
        raw = path.read_text(encoding="utf-8")
        metadata, content = self._parse_frontmatter(raw)

        if metadata.get("title", None) is None or metadata.get("group", None) is None:
            return None

        slug = self._build_slug(metadata.get("title"), metadata.get("group"))
        article = Article(
            title=metadata.get("title"),
            description=metadata.get("description", ""),
            group=metadata.get("group"),
            visibility=metadata.get("visibility", "private"),
            order=int(metadata.get("order", 100)),
            topics=metadata.get("topics", []),
            content=content,
            slug=slug
        )
        article.breadcrumbs = self._build_breadcrumbs(article)

        return article

    @staticmethod
    def _build_slug(title: str, group: str) -> str:
        return f"{ArticleRegistry.slugify(group)}/{ArticleRegistry.slugify(title)}"

    @staticmethod
    def slugify(value: str) -> str:
        value = value.lower().strip()
        value = re.sub(r"[^a-z0-9]+", "-", value)
        value = re.sub(r"-+", "-", value)
        return value.strip("-")

    def _build_breadcrumbs(self, article: Article) -> list[dict]:
        group_slug = self.slugify(article.group)
        article_slug = article.slug
        return [
            {
                "label": "Docs",
                "url": "/docs/",
                "active": False,
            },
            {
                "label": article.group,
                "url": f"/docs/{group_slug}",
                "active": False,
            },
            {
                "label": article.title,
                "url": f"/docs/{article_slug}",
                "active": True,
            },
        ]

    @staticmethod
    def _parse_frontmatter(raw: str) -> tuple[dict, str]:
        if raw.startswith("---"):
            parts = raw.split("---", 2)

            if len(parts) == 3:
                metadata = yaml.safe_load(parts[1]) or {}
                body = parts[2].lstrip()
                return metadata, body

        return {}, raw

