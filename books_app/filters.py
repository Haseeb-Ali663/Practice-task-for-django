from datetime import date, datetime

import django_filters
from django.db.models import Count, Q
from django_filters.rest_framework import FilterSet
from rest_framework.exceptions import ValidationError
from rest_framework.filters import BaseFilterBackend

from .models import Book
from .query_params import int_param


class BookFilter(FilterSet):
    """
    Declarative filters for Book, driven by DjangoFilterBackend.
    Supports partial matches on title/author and a released/unreleased flag.
    """

    title = django_filters.CharFilter(
        lookup_expr="icontains",
        help_text="Filter books by title (case-insensitive partial match).",
    )
    author = django_filters.CharFilter(
        method="filter_by_author",
        help_text="Filter books by author (partial match on author name).",
    )
    is_published = django_filters.BooleanFilter(
        method="filter_by_published",
        help_text="True: published on or before today. False: future-dated (not yet released).",
    )

    class Meta:
        model = Book
        fields = ["title", "author", "is_published"]

    def filter_by_author(self, queryset, name, value):
        """
        Allow filtering by author name using partial match.
        Example: ?author=orwell -> Orwell, george orwell, G. Orwell, etc.
        """
        if not value:
            return queryset
        # case-insensitive partial match on author name
        return queryset.filter(author__name__icontains=value).distinct()

    def filter_by_published(self, queryset, name, value):
        """
        Filter by released / not-yet-released.

        `published_date` is non-nullable on the model, so a NULL-based check can
        never match anything; "published" is therefore defined against today:
        - True:  published_date <= today (already out)
        - False: published_date >  today (future-dated)
        """
        if value is True:
            return queryset.filter(published_date__lte=date.today())
        if value is False:
            return queryset.filter(published_date__gt=date.today())
        return queryset


class SmartBookFilterBackend(BaseFilterBackend):
    """
    Custom filter backend for query logic a declarative FilterSet cannot express:
    multi-term relevance search, named eras, date windows and genre set-matching.

    Query parameters
        q=<terms>                  every whitespace-separated term must match the
                                   title, the author name, or a genre name
        era=classic|modern|contemporary
        published_between=YYYY-MM-DD,YYYY-MM-DD   inclusive window
        genres=fantasy,fiction     comma-separated genre names
        genres_match=any|all       how to combine `genres` (default: any)
        min_genres=<int>           books carrying at least N genres

    Invalid input raises ValidationError (HTTP 400) rather than being ignored.
    """

    ERAS = {
        "classic": (None, date(1899, 12, 31)),
        "modern": (date(1900, 1, 1), date(1979, 12, 31)),
        "contemporary": (date(1980, 1, 1), None),
    }
    SEARCH_FIELDS = ("title", "author__name", "genres__name")
    MAX_TERMS = 8

    def filter_queryset(self, request, queryset, view):
        # Only narrow collection endpoints; a stray param must not 404 a detail route.
        if getattr(view, "detail", False):
            return queryset
        if queryset.model is not Book:
            return queryset

        params = request.query_params
        queryset = self._apply_terms(queryset, params.get("q"))
        queryset = self._apply_era(queryset, params.get("era"))
        queryset = self._apply_window(queryset, params.get("published_between"))
        queryset = self._apply_genres(
            queryset, params.get("genres"), params.get("genres_match", "any")
        )
        return self._apply_min_genres(
            queryset, int_param(params, "min_genres", minimum=0)
        )

    @staticmethod
    def _any_of(lookups):
        """OR together Q objects built from (lookup, value) pairs."""
        clause = Q()
        for lookup, value in lookups:
            clause |= Q(**{lookup: value})
        return clause

    # -- q -----------------------------------------------------------------
    def _apply_terms(self, queryset, raw):
        if not raw or not raw.strip():
            return queryset

        terms = raw.split()
        if len(terms) > self.MAX_TERMS:
            raise ValidationError({"q": f"Too many search terms (max {self.MAX_TERMS})."})

        # One .filter() per term, deliberately not a single combined Q: each call
        # gets its own join over the genres M2M, so a book matches when *every*
        # term is found in *some* field. Folding these into one .filter() would
        # instead demand that a single genre row satisfy every term at once.
        for term in terms:
            queryset = queryset.filter(
                self._any_of((f"{field}__icontains", term) for field in self.SEARCH_FIELDS)
            )
        return queryset.distinct()

    # -- era ---------------------------------------------------------------
    def _apply_era(self, queryset, raw):
        if not raw:
            return queryset

        try:
            start, end = self.ERAS[raw.strip().lower()]
        except KeyError:
            raise ValidationError(
                {"era": f"Invalid era. Choose from: {', '.join(sorted(self.ERAS))}."}
            )

        if start is not None:
            queryset = queryset.filter(published_date__gte=start)
        if end is not None:
            queryset = queryset.filter(published_date__lte=end)
        return queryset

    # -- published_between -------------------------------------------------
    def _apply_window(self, queryset, raw):
        if not raw:
            return queryset

        parts = [p.strip() for p in raw.split(",")]
        if len(parts) != 2 or not all(parts):
            raise ValidationError(
                {"published_between": "Expected two dates: YYYY-MM-DD,YYYY-MM-DD."}
            )

        try:
            start, end = (datetime.strptime(p, "%Y-%m-%d").date() for p in parts)
        except ValueError:
            raise ValidationError(
                {"published_between": "Dates must be in YYYY-MM-DD format."}
            )

        if start > end:
            raise ValidationError(
                {"published_between": "Start date must not be after end date."}
            )
        return queryset.filter(published_date__range=(start, end))

    # -- genres / genres_match ---------------------------------------------
    def _apply_genres(self, queryset, raw, match):
        if not raw:
            return queryset

        names = [n.strip() for n in raw.split(",") if n.strip()]
        if not names:
            raise ValidationError({"genres": "Provide at least one genre name."})

        match = (match or "any").strip().lower()
        if match not in ("any", "all"):
            raise ValidationError({"genres_match": "Must be either 'any' or 'all'."})

        if match == "any":
            clause = self._any_of(("genres__name__iexact", name) for name in names)
            return queryset.filter(clause).distinct()

        # 'all': chained filters, one join per genre, so every name must be present.
        for name in names:
            queryset = queryset.filter(genres__name__iexact=name)
        return queryset.distinct()

    # -- min_genres --------------------------------------------------------
    def _apply_min_genres(self, queryset, minimum):
        if minimum is None:
            return queryset

        return queryset.annotate(_genre_count=Count("genres", distinct=True)).filter(
            _genre_count__gte=minimum
        )

    # -- OpenAPI -----------------------------------------------------------
    def get_schema_operation_parameters(self, view):
        def param(name, description, schema=None):
            return {
                "name": name,
                "required": False,
                "in": "query",
                "description": description,
                "schema": schema or {"type": "string"},
            }

        return [
            param("q", "Every term must match title, author name, or genre name."),
            param(
                "era",
                "Named publication era.",
                {"type": "string", "enum": sorted(self.ERAS)},
            ),
            param("published_between", "Inclusive window: YYYY-MM-DD,YYYY-MM-DD."),
            param("genres", "Comma-separated genre names."),
            param(
                "genres_match",
                "Combine `genres` with any (OR) or all (AND). Default: any.",
                {"type": "string", "enum": ["any", "all"]},
            ),
            param("min_genres", "Minimum number of genres.", {"type": "integer"}),
        ]
