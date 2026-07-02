from sqlalchemy import func
import sqlalchemy as sa


class SearchableMixin:
    @classmethod
    def search(cls, search_term, base_query=None):
        if not search_term:
            return base_query or None

        if not hasattr(cls, "__searchable__"):
            raise AttributeError(f"{cls.__name__} is missing __searchable__")

        ts_query = func.websearch_to_tsquery("english", search_term)
        vector = None

        for field_name, weight in cls.__searchable__.items():
            column = getattr(cls, field_name)
            weighted_vector = func.setweight(func.to_tsvector("english", func.coalesce(column, "")), weight)
            vector = weighted_vector if vector is None else vector.op("||")(weighted_vector)

        rank = func.ts_rank_cd(vector, ts_query)
        query = base_query

        return query.filter(vector.op("@@")(ts_query)).order_by(sa.desc(rank))
