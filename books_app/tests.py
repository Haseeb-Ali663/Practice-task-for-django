from datetime import date, timedelta
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase, APIRequestFactory
from rest_framework import status

from books_app.models import Author, Book, Genre
from books_app.serializers import AuthorSerializer, BookSerializer, GenreSerializer


# ──────────────────────────────────────────────
#  1. SERIALIZER TESTS
# ──────────────────────────────────────────────

class AuthorSerializerTest(TestCase):
    """Test serialization, deserialization, and validation for AuthorSerializer."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.author = Author.objects.create(
            name="George Orwell",
            bio="English novelist and essayist.",
            date_of_birth=date(1903, 6, 25),
        )

    # --- Serialization ---
    def test_author_serialization(self):
        """AuthorSerializer should correctly serialize an Author instance."""
        request = self.factory.get("/authors/")
        serializer = AuthorSerializer(self.author, context={"request": request})
        data = serializer.data
        self.assertEqual(data["name"], "George Orwell")
        self.assertEqual(data["bio"], "English novelist and essayist.")
        self.assertEqual(data["date_of_birth"], "1903-06-25")
        self.assertIn("url", data)

    # --- Deserialization ---
    def test_author_deserialization_valid(self):
        """Valid input data should deserialize into a new Author."""
        request = self.factory.post("/authors/")
        payload = {
            "name": "Jane Austen",
            "bio": "English novelist.",
            "date_of_birth": "1775-12-16",
        }
        serializer = AuthorSerializer(data=payload, context={"request": request})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        author = serializer.save()
        self.assertEqual(author.name, "Jane Austen")

    # --- Field-level validation ---
    def test_author_name_too_short(self):
        """Name shorter than 3 characters should be rejected."""
        request = self.factory.post("/authors/")
        payload = {"name": "AB", "bio": "Short name author."}
        serializer = AuthorSerializer(data=payload, context={"request": request})
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

    def test_author_future_date_of_birth(self):
        """Date of birth in the future should be rejected."""
        request = self.factory.post("/authors/")
        future = date.today() + timedelta(days=365)
        payload = {
            "name": "Future Author",
            "bio": "Born in the future.",
            "date_of_birth": future.isoformat(),
        }
        serializer = AuthorSerializer(data=payload, context={"request": request})
        self.assertFalse(serializer.is_valid())
        self.assertIn("date_of_birth", serializer.errors)


class BookSerializerTest(TestCase):
    """Test serialization, deserialization, and validation for BookSerializer."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.author = Author.objects.create(
            name="George Orwell",
            bio="English novelist.",
            date_of_birth=date(1903, 6, 25),
        )
        self.genre_fiction = Genre.objects.create(name="Fiction")
        self.genre_dystopian = Genre.objects.create(name="Dystopian")
        self.book = Book.objects.create(
            title="1984",
            author=self.author,
            published_date=date(1949, 6, 8),
        )
        self.book.genres.set([self.genre_fiction, self.genre_dystopian])

    # --- Serialization ---
    def test_book_serialization_fields(self):
        """BookSerializer should include all expected fields."""
        request = self.factory.get("/books/")
        serializer = BookSerializer(self.book, context={"request": request})
        data = serializer.data
        self.assertEqual(data["title"], "1984")
        self.assertEqual(data["published_date"], "1949-06-08")
        self.assertIn("author", data)
        self.assertIn("author_custom", data)
        self.assertIn("time_since_published", data)
        self.assertIn("genre_names", data)

    def test_book_nested_author(self):
        """The 'author' field should return nested author data via SerializerMethodField."""
        request = self.factory.get("/books/")
        serializer = BookSerializer(self.book, context={"request": request})
        author_data = serializer.data["author"]
        self.assertEqual(author_data["id"], self.author.id)
        self.assertEqual(author_data["name"], "George Orwell")

    def test_book_custom_author_field(self):
        """The 'author_custom' field should show 'Name (born: YYYY-MM-DD)'."""
        request = self.factory.get("/books/")
        serializer = BookSerializer(self.book, context={"request": request})
        self.assertEqual(
            serializer.data["author_custom"],
            "George Orwell (born: 1903-06-25)",
        )

    def test_book_custom_author_field_no_dob(self):
        """Author with no date_of_birth should show '(born: unknown)'."""
        author_no_dob = Author.objects.create(name="Unknown Author", bio="No DOB.")
        book = Book.objects.create(
            title="Mystery Book",
            author=author_no_dob,
            published_date=date(2020, 1, 1),
        )
        request = self.factory.get("/books/")
        serializer = BookSerializer(book, context={"request": request})
        self.assertEqual(
            serializer.data["author_custom"],
            "Unknown Author (born: unknown)",
        )

    def test_book_time_since_published(self):
        """time_since_published should return a non-empty string."""
        request = self.factory.get("/books/")
        serializer = BookSerializer(self.book, context={"request": request})
        self.assertIsNotNone(serializer.data["time_since_published"])
        self.assertIsInstance(serializer.data["time_since_published"], str)

    def test_book_genre_names_serialization(self):
        """genre_names should return a list of genre name strings."""
        request = self.factory.get("/books/")
        serializer = BookSerializer(self.book, context={"request": request})
        genre_names = serializer.data["genre_names"]
        self.assertIsInstance(genre_names, list)
        self.assertIn("Fiction", genre_names)
        self.assertIn("Dystopian", genre_names)

    # --- Deserialization ---
    def test_book_deserialization_valid(self):
        """Valid payload should create a Book with genres."""
        request = self.factory.post("/books/")
        payload = {
            "title": "Animal Farm",
            "author_id": self.author.pk,
            "published_date": "1945-08-17",
            "genre_ids": [self.genre_fiction.pk],
        }
        serializer = BookSerializer(data=payload, context={"request": request})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        book = serializer.save()
        self.assertEqual(book.title, "Animal Farm")
        self.assertIn(self.genre_fiction, book.genres.all())

    # --- Field-level validation ---
    def test_book_future_published_date(self):
        """Published date in the future should be rejected."""
        request = self.factory.post("/books/")
        future = date.today() + timedelta(days=30)
        payload = {
            "title": "Future Book",
            "author_id": self.author.pk,
            "published_date": future.isoformat(),
        }
        serializer = BookSerializer(data=payload, context={"request": request})
        self.assertFalse(serializer.is_valid())
        self.assertIn("published_date", serializer.errors)

    # --- Object-level validation ---
    def test_book_published_before_author_born(self):
        """Published date before the author's birth should be rejected."""
        request = self.factory.post("/books/")
        payload = {
            "title": "Impossible Book",
            "author_id": self.author.pk,
            "published_date": "1800-01-01",  # before Orwell's 1903 birth
        }
        serializer = BookSerializer(data=payload, context={"request": request})
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)


class GenreSerializerTest(TestCase):
    """Test GenreSerializer."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.genre = Genre.objects.create(name="Science Fiction")

    def test_genre_serialization(self):
        request = self.factory.get("/genres/")
        serializer = GenreSerializer(self.genre, context={"request": request})
        data = serializer.data
        self.assertEqual(data["name"], "Science Fiction")
        self.assertIn("url", data)

    def test_genre_deserialization(self):
        request = self.factory.post("/genres/")
        payload = {"name": "Horror"}
        serializer = GenreSerializer(data=payload, context={"request": request})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        genre = serializer.save()
        self.assertEqual(genre.name, "Horror")


# ──────────────────────────────────────────────
#  2. VIEW TESTS (CRUD)
# ──────────────────────────────────────────────

class BookViewTest(APITestCase):
    """Test Book API endpoints."""

    def setUp(self):
        self.author = Author.objects.create(
            name="George Orwell",
            bio="English novelist.",
            date_of_birth=date(1903, 6, 25),
        )
        self.genre = Genre.objects.create(name="Fiction")
        self.book = Book.objects.create(
            title="1984",
            author=self.author,
            published_date=date(1949, 6, 8),
        )
        self.book.genres.add(self.genre)

    def test_list_books(self):
        """GET /books/ should return 200 with a list of books."""
        response = self.client.get(reverse("book-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "1984")

    def test_create_book(self):
        """POST /books/ with valid data should return 201."""
        payload = {
            "title": "Animal Farm",
            "author_id": self.author.pk,
            "published_date": "1945-08-17",
            "genre_ids": [self.genre.pk],
        }
        response = self.client.post(reverse("book-list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Book.objects.count(), 2)

    def test_create_book_invalid(self):
        """POST /books/ with future date should return 400."""
        future = (date.today() + timedelta(days=30)).isoformat()
        payload = {
            "title": "Bad Book",
            "author_id": self.author.pk,
            "published_date": future,
        }
        response = self.client.post(reverse("book-list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_book(self):
        """GET /books/<pk>/ should return a single book."""
        response = self.client.get(reverse("book-detail", args=[self.book.pk]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "1984")

    def test_update_book(self):
        """PUT /books/<pk>/ should update the book."""
        payload = {
            "title": "Nineteen Eighty-Four",
            "author_id": self.author.pk,
            "published_date": "1949-06-08",
        }
        response = self.client.put(
            reverse("book-detail", args=[self.book.pk]), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.book.refresh_from_db()
        self.assertEqual(self.book.title, "Nineteen Eighty-Four")

    def test_delete_book(self):
        """DELETE /books/<pk>/ should remove the book."""
        response = self.client.delete(reverse("book-detail", args=[self.book.pk]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Book.objects.count(), 0)


class AuthorViewTest(APITestCase):
    """Test Author API endpoints."""

    def setUp(self):
        self.author = Author.objects.create(
            name="George Orwell",
            bio="English novelist.",
            date_of_birth=date(1903, 6, 25),
        )

    def test_list_authors(self):
        response = self.client.get(reverse("author-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_create_author(self):
        payload = {
            "name": "Jane Austen",
            "bio": "English novelist.",
            "date_of_birth": "1775-12-16",
        }
        response = self.client.post(reverse("author-list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Author.objects.count(), 2)

    def test_create_author_name_too_short(self):
        """Author name < 3 chars should fail with 400."""
        payload = {"name": "AB", "bio": "Too short."}
        response = self.client.post(reverse("author-list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_author(self):
        response = self.client.get(reverse("author-detail", args=[self.author.pk]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "George Orwell")

    def test_update_author(self):
        payload = {
            "name": "Eric Arthur Blair",
            "bio": "George Orwell's real name.",
            "date_of_birth": "1903-06-25",
        }
        response = self.client.put(
            reverse("author-detail", args=[self.author.pk]), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.author.refresh_from_db()
        self.assertEqual(self.author.name, "Eric Arthur Blair")

    def test_delete_author(self):
        response = self.client.delete(reverse("author-detail", args=[self.author.pk]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Author.objects.count(), 0)


class GenreViewTest(APITestCase):
    """Test Genre API endpoints."""

    def setUp(self):
        self.genre = Genre.objects.create(name="Fantasy")

    def test_list_genres(self):
        response = self.client.get(reverse("genre-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_create_genre(self):
        payload = {"name": "Thriller"}
        response = self.client.post(reverse("genre-list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Genre.objects.count(), 2)

    def test_retrieve_genre(self):
        response = self.client.get(reverse("genre-detail", args=[self.genre.pk]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Fantasy")

    def test_delete_genre(self):
        response = self.client.delete(reverse("genre-detail", args=[self.genre.pk]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Genre.objects.count(), 0)
