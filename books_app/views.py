from datetime import date, timedelta

from django.db.models import Count
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from books_app.models import Book, Author, Genre
from books_app.serializers import (
    BookSerializer,
    AuthorSerializer,
    GenreSerializer,
    GenreAssignSerializer,
    AuthorBookCountSerializer,
)


class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer

    @action(detail=False, methods=['get'], url_path='recent')
    def recent(self, request):
        """GET /books/recent/?days=365 — books published within the last `days` days."""
        try:
            days = int(request.query_params.get('days', 365))
        except ValueError:
            return Response(
                {'days': 'Must be an integer.'}, status=status.HTTP_400_BAD_REQUEST
            )
        if days < 1:
            return Response(
                {'days': 'Must be a positive integer.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cutoff = date.today() - timedelta(days=days)
        books = self.get_queryset().filter(published_date__gte=cutoff).order_by('-published_date')
        serializer = self.get_serializer(books, many=True)
        return Response(serializer.data)

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

        book.genres.add(*serializer.validated_data['genre_ids'])
        return Response(
            BookSerializer(book, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )


class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer

    @action(detail=True, methods=['get'], serializer_class=BookSerializer)
    def books(self, request, pk=None):
        """GET /authors/<pk>/books/ — every book written by this author."""
        author = self.get_object()
        books = Book.objects.filter(author=author).order_by('-published_date')
        serializer = self.get_serializer(books, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], serializer_class=AuthorBookCountSerializer)
    def prolific(self, request):
        """GET /authors/prolific/?min_books=2 — authors with at least `min_books` books."""
        try:
            min_books = int(request.query_params.get('min_books', 2))
        except ValueError:
            return Response(
                {'min_books': 'Must be an integer.'}, status=status.HTTP_400_BAD_REQUEST
            )

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

    @action(detail=True, methods=['get'], serializer_class=BookSerializer)
    def books(self, request, pk=None):
        """GET /genres/<pk>/books/ — every book tagged with this genre."""
        genre = self.get_object()
        serializer = self.get_serializer(genre.books.order_by('-published_date'), many=True)
        return Response(serializer.data)
