from datetime import date, timedelta

from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from books_app.filters import BookFilter, SmartBookFilterBackend
from books_app.models import Author, Book, Genre
from books_app.pagination import BookCursorPagination, BookLimitOffsetPagination, BookPageNumberPagination
from books_app.query_params import int_param
from books_app.serializers import (
    BookSerializer,
    BookListSerializer,
    BookDetailSerializer,
    AuthorSerializer,
    GenreSerializer,
    GenreAssignSerializer,
    AuthorBookCountSerializer,
    BookStatisticsSerializer,
)


class BookViewSet(viewsets.ModelViewSet):
    serializer_class = BookDetailSerializer
    pagination_class = BookLimitOffsetPagination

    # Project defaults plus the Book-specific custom backend.
    filter_backends = [
        DjangoFilterBackend,
        SmartBookFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]
    filterset_class = BookFilter
    search_fields = ["title", "author__name"]
    ordering_fields = ["title", "published_date"]
    ordering = ["-published_date"]

    def get_queryset(self):
        """
        Dynamically optimize querysets based on action and requested fields:
        1. Base queryset: Book.objects.all()
        2. Conditional select_related('author'):
           - Joined only when author fields are needed (e.g. ?fields=title skips author join).
        3. Conditional prefetch_related('genres'):
           - Prefetched only when genre fields are needed (e.g. ?fields=title skips genre prefetch).
        """
        queryset = Book.objects.all()

        # Check requested fields if ?fields=... query param is provided
        fields_param = (
            self.request.query_params.get("fields")
            if hasattr(self, "request") and self.request
            else None
        )

        if fields_param:
            requested = {f.strip() for f in fields_param.split(",") if f.strip()}
            needs_author = bool({"author", "author_name", "author_custom", "author_id"} & requested)
            needs_genres = bool({"genres", "genre_names", "genre_ids"} & requested)
        else:
            needs_author = True
            needs_genres = True

        if needs_author:
            queryset = queryset.select_related("author")
        if needs_genres:
            queryset = queryset.prefetch_related("genres")

        return queryset

    def get_serializer_class(self):
        """
        Dynamically return serializer class based on action:
        - 'list', 'recent', 'featured': lightweight BookListSerializer
        - 'retrieve', 'create', 'update', 'partial_update': comprehensive BookDetailSerializer
        - custom actions: respects action serializer_class or falls back to default
        """
        if self.action in ["list", "recent", "featured"]:
            return BookListSerializer
        if self.action in ["retrieve", "create", "update", "partial_update"]:
            return BookDetailSerializer
        return super().get_serializer_class()

    @action(detail=False, methods=["get"])
    def recent(self, request):
        """GET /books/recent/?days=365 — books published within the last `days` days."""
        days = int_param(request.query_params, "days", default=365, minimum=1)
        cutoff = date.today() - timedelta(days=days)

        books = self.filter_queryset(self.get_queryset()).filter(
            published_date__gte=cutoff
        )
        serializer = self.get_serializer(books, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def featured(self, request):
        """GET /books/featured/?limit=5 — returns featured books ordered by genre richness and publication date."""
        limit = int_param(request.query_params, "limit", default=5, minimum=1)

        queryset = (
            self.filter_queryset(self.get_queryset())
            .annotate(genre_count=Count("genres"))
            .order_by("-genre_count", "-published_date")
        )
        featured_books = queryset[:limit] if limit else queryset
        serializer = self.get_serializer(featured_books, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], serializer_class=BookStatisticsSerializer)
    def statistics(self, request, pk=None):
        """GET /books/<pk>/statistics/ — analytical statistics for a single book."""
        book = self.get_object()
        serializer = self.get_serializer(book)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=['post'],
        url_path='add-genres',
        serializer_class=GenreAssignSerializer,
    )
    def add_genres(self, request, pk=None):
        """POST /books/<pk>/add-genres/ with {"genre_ids": [1, 2]} — attach genres to a book."""
        book = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return Response(
            BookSerializer(book, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )


class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer
    pagination_class = BookPageNumberPagination

    @action(detail=True, methods=['get'], serializer_class=BookSerializer)
    def books(self, request, pk=None):
        """GET /authors/<pk>/books/ — every book written by this author."""
        author = self.get_object()
        books = (
            Book.objects.filter(author=author)
            .select_related("author")
            .prefetch_related("genres")
            .order_by("-published_date")
        )
        serializer = self.get_serializer(books, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], serializer_class=AuthorBookCountSerializer)
    def prolific(self, request):
        """GET /authors/prolific/?min_books=2 — authors with at least `min_books` books."""
        min_books = int_param(request.query_params, "min_books", default=2, minimum=0)

        authors = (
            self.get_queryset()
            .annotate(book_count=Count('book'))
            .filter(book_count__gte=min_books)
            .order_by('-book_count', 'name')
        )
        serializer = self.get_serializer(authors, many=True)
        return Response(serializer.data)


class GenreViewSet(viewsets.ModelViewSet):
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer
    pagination_class = BookCursorPagination

    @action(detail=True, methods=['get'], serializer_class=BookSerializer)
    def books(self, request, pk=None):
        """GET /genres/<pk>/books/ — every book tagged with this genre."""
        genre = self.get_object()
        books = (
            genre.books.select_related('author')
            .prefetch_related('genres')
            .order_by('-published_date')
        )
        serializer = self.get_serializer(books, many=True)
        return Response(serializer.data)
