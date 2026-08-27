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
        """GET /books/ should return 200 with a paginated list of books."""
        response = self.client.get(reverse("book-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("pagination", response.data)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["title"], "1984")

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

    def test_book_statistics_action(self):
        """GET /books/<pk>/statistics/ should return analytical statistics."""
        response = self.client.get(reverse("book-statistics", args=[self.book.pk]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data["book_id"], self.book.pk)
        self.assertEqual(data["title"], "1984")
        self.assertEqual(data["author_name"], "George Orwell")
        self.assertEqual(data["total_genres"], 1)
        self.assertEqual(data["author_total_books"], 1)
        self.assertEqual(data["title_word_count"], 1)
        self.assertEqual(data["title_character_count"], 4)
        self.assertIsNotNone(data["days_since_published"])
        self.assertIsNotNone(data["years_since_published"])
        self.assertEqual(data["author_age_at_publication"], 45)

    def test_featured_books_action(self):
        """GET /books/featured/ should return featured books sorted by genre count and recency."""
        # Create another genre and book with 2 genres
        genre2 = Genre.objects.create(name="Classic")
        book2 = Book.objects.create(
            title="Animal Farm",
            author=self.author,
            published_date=date(1945, 8, 17),
        )
        book2.genres.add(self.genre, genre2)

        response = self.client.get(reverse("book-featured"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # book2 has 2 genres so it should be first in the featured list
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["title"], "Animal Farm")
        self.assertEqual(response.data[1]["title"], "1984")

    def test_featured_books_action_with_limit(self):
        """GET /books/featured/?limit=1 should return only 1 book."""
        response = self.client.get(reverse("book-featured"), {"limit": 1})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


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
        self.assertIn("results", response.data)
        self.assertIn("pagination", response.data)
        self.assertEqual(len(response.data["results"]), 1)

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
        self.assertIn("results", response.data)
        self.assertIn("pagination", response.data)
        self.assertEqual(len(response.data["results"]), 1)

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


# ──────────────────────────────────────────────
#  4. PAGINATION TESTS
# ──────────────────────────────────────────────

class BookPaginationTest(APITestCase):
    """Tests for BookLimitOffsetPagination on GET /books/."""

    def setUp(self):
        self.author = Author.objects.create(
            name="Test Author",
            bio="A test author.",
            date_of_birth=date(1970, 1, 1),
        )
        # Create 15 books so we can paginate across them
        for i in range(1, 16):
            Book.objects.create(
                title=f"Book {i:02d}",
                author=self.author,
                published_date=date(2000 + i, 1, 1),
            )

    # -- Response envelope ------------------------------------------------

    def test_response_has_pagination_envelope(self):
        """List response must include 'pagination' and 'results' keys."""
        response = self.client.get(reverse("book-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("pagination", response.data)
        self.assertIn("results", response.data)

    def test_pagination_metadata_fields(self):
        """'pagination' block must carry all expected metadata fields."""
        response = self.client.get(reverse("book-list"))
        p = response.data["pagination"]
        for field in (
            "total_count", "limit", "offset",
            "page_count", "current_page",
            "next", "previous", "has_next", "has_previous",
        ):
            self.assertIn(field, p, msg=f"Missing pagination field: {field}")

    # -- Default behaviour ------------------------------------------------

    def test_default_limit_is_10(self):
        """Without ?limit the default of 10 results should be returned."""
        response = self.client.get(reverse("book-list"))
        self.assertEqual(len(response.data["results"]), 10)
        self.assertEqual(response.data["pagination"]["limit"], 10)

    def test_total_count(self):
        """total_count should reflect the full queryset size (15)."""
        response = self.client.get(reverse("book-list"))
        self.assertEqual(response.data["pagination"]["total_count"], 15)

    def test_default_offset_is_zero(self):
        """Without ?offset the offset should default to 0."""
        response = self.client.get(reverse("book-list"))
        self.assertEqual(response.data["pagination"]["offset"], 0)

    # -- Custom limit / offset --------------------------------------------

    def test_custom_limit(self):
        """?limit=5 should return 5 results."""
        response = self.client.get(reverse("book-list"), {"limit": 5})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 5)
        self.assertEqual(response.data["pagination"]["limit"], 5)

    def test_custom_offset(self):
        """?limit=5&offset=10 should return the last 5 of 15 books."""
        response = self.client.get(reverse("book-list"), {"limit": 5, "offset": 10})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 5)
        self.assertEqual(response.data["pagination"]["offset"], 10)

    def test_offset_beyond_count_returns_empty(self):
        """An offset past the end of the queryset should return an empty result list."""
        response = self.client.get(reverse("book-list"), {"offset": 100})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    # -- Computed metadata ------------------------------------------------

    def test_page_count(self):
        """15 books with limit=10 should give page_count=2."""
        response = self.client.get(reverse("book-list"), {"limit": 10})
        self.assertEqual(response.data["pagination"]["page_count"], 2)

    def test_current_page_first(self):
        """offset=0, limit=10 → current_page=1."""
        response = self.client.get(reverse("book-list"), {"limit": 10, "offset": 0})
        self.assertEqual(response.data["pagination"]["current_page"], 1)

    def test_current_page_second(self):
        """offset=10, limit=10 → current_page=2."""
        response = self.client.get(reverse("book-list"), {"limit": 10, "offset": 10})
        self.assertEqual(response.data["pagination"]["current_page"], 2)

    # -- Navigation links -------------------------------------------------

    def test_next_link_present_on_first_page(self):
        """First page should have a 'next' URL and has_next=True."""
        response = self.client.get(reverse("book-list"), {"limit": 10, "offset": 0})
        p = response.data["pagination"]
        self.assertTrue(p["has_next"])
        self.assertIsNotNone(p["next"])

    def test_previous_link_absent_on_first_page(self):
        """First page should have no 'previous' URL and has_previous=False."""
        response = self.client.get(reverse("book-list"), {"limit": 10, "offset": 0})
        p = response.data["pagination"]
        self.assertFalse(p["has_previous"])
        self.assertIsNone(p["previous"])

    def test_previous_link_present_on_second_page(self):
        """Second page should have a 'previous' URL and has_previous=True."""
        response = self.client.get(reverse("book-list"), {"limit": 10, "offset": 10})
        p = response.data["pagination"]
        self.assertTrue(p["has_previous"])
        self.assertIsNotNone(p["previous"])

    def test_next_link_absent_on_last_page(self):
        """Last page should have no 'next' URL and has_next=False."""
        response = self.client.get(reverse("book-list"), {"limit": 10, "offset": 10})
        p = response.data["pagination"]
        self.assertFalse(p["has_next"])
        self.assertIsNone(p["next"])


# ──────────────────────────────────────────────
#  5. PAGE-NUMBER PAGINATION TESTS
# ──────────────────────────────────────────────

class AuthorPageNumberPaginationTest(APITestCase):
    """
    Tests for BookPageNumberPagination on GET /authors/.

    Default page_size=5, configurable via ?page_size=N (max 50).
    Navigation via ?page=N.
    """

    def setUp(self):
        # Create 12 authors so we get 3 pages at default page_size=5
        # (page 1: 5, page 2: 5, page 3: 2)
        for i in range(1, 13):
            Author.objects.create(
                name=f"Author {i:02d}",
                bio=f"Bio for author {i}.",
            )

    # -- Response envelope ------------------------------------------------

    def test_response_has_pagination_envelope(self):
        """List response must include 'pagination' and 'results' keys."""
        response = self.client.get(reverse("author-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("pagination", response.data)
        self.assertIn("results", response.data)

    def test_pagination_metadata_fields(self):
        """'pagination' block must carry all expected metadata fields."""
        response = self.client.get(reverse("author-list"))
        p = response.data["pagination"]
        for field in (
            "total_count", "page_size", "page_count",
            "current_page", "next", "previous",
            "has_next", "has_previous",
        ):
            self.assertIn(field, p, msg=f"Missing pagination field: {field}")

    # -- Default behaviour ------------------------------------------------

    def test_default_page_size_is_5(self):
        """Without ?page_size the default of 5 results should be returned."""
        response = self.client.get(reverse("author-list"))
        self.assertEqual(len(response.data["results"]), 5)
        self.assertEqual(response.data["pagination"]["page_size"], 5)

    def test_total_count(self):
        """total_count should reflect the full queryset size (12)."""
        response = self.client.get(reverse("author-list"))
        self.assertEqual(response.data["pagination"]["total_count"], 12)

    def test_default_page_is_first(self):
        """Without ?page the first page (current_page=1) should be returned."""
        response = self.client.get(reverse("author-list"))
        self.assertEqual(response.data["pagination"]["current_page"], 1)

    # -- page_count -------------------------------------------------------

    def test_page_count_default_size(self):
        """12 authors at page_size=5 should give page_count=3."""
        response = self.client.get(reverse("author-list"))
        self.assertEqual(response.data["pagination"]["page_count"], 3)

    def test_page_count_custom_size(self):
        """12 authors at page_size=4 should give page_count=3."""
        response = self.client.get(reverse("author-list"), {"page_size": 4})
        self.assertEqual(response.data["pagination"]["page_count"], 3)

    # -- Custom page_size -------------------------------------------------

    def test_custom_page_size(self):
        """?page_size=3 should return 3 results on page 1."""
        response = self.client.get(reverse("author-list"), {"page_size": 3})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 3)
        self.assertEqual(response.data["pagination"]["page_size"], 3)

    def test_page_size_capped_at_max(self):
        """?page_size=999 should be silently capped at max_page_size=50."""
        response = self.client.get(reverse("author-list"), {"page_size": 999})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(response.data["pagination"]["page_size"], 50)

    # -- Navigation by page number ----------------------------------------

    def test_navigate_to_page_2(self):
        """?page=2 should return the second batch of results."""
        response = self.client.get(reverse("author-list"), {"page": 2})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pagination"]["current_page"], 2)
        self.assertEqual(len(response.data["results"]), 5)

    def test_last_page_has_remainder(self):
        """Page 3 of 12 authors at page_size=5 should have 2 results."""
        response = self.client.get(reverse("author-list"), {"page": 3})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

    def test_invalid_page_returns_404(self):
        """A page number beyond the last page should return 404."""
        response = self.client.get(reverse("author-list"), {"page": 999})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # -- Navigation links -------------------------------------------------

    def test_next_link_present_on_first_page(self):
        """First page should have a 'next' URL and has_next=True."""
        response = self.client.get(reverse("author-list"), {"page": 1})
        p = response.data["pagination"]
        self.assertTrue(p["has_next"])
        self.assertIsNotNone(p["next"])

    def test_previous_link_absent_on_first_page(self):
        """First page should have no 'previous' URL and has_previous=False."""
        response = self.client.get(reverse("author-list"), {"page": 1})
        p = response.data["pagination"]
        self.assertFalse(p["has_previous"])
        self.assertIsNone(p["previous"])

    def test_previous_link_present_on_page_2(self):
        """Page 2 should have a 'previous' URL and has_previous=True."""
        response = self.client.get(reverse("author-list"), {"page": 2})
        p = response.data["pagination"]
        self.assertTrue(p["has_previous"])
        self.assertIsNotNone(p["previous"])

    def test_next_link_absent_on_last_page(self):
        """Last page should have no 'next' URL and has_next=False."""
        response = self.client.get(reverse("author-list"), {"page": 3})
        p = response.data["pagination"]
        self.assertFalse(p["has_next"])
        self.assertIsNone(p["next"])


# ──────────────────────────────────────────────
#  6. CURSOR PAGINATION TESTS
# ──────────────────────────────────────────────

class GenreCursorPaginationTest(APITestCase):
    """
    Tests for BookCursorPagination on GET /genres/.

    Key properties of cursor pagination:
      - Results arrive in pages via opaque cursor tokens in 'next'/'previous' URLs.
      - NO total_count or page_count (by design: avoids expensive COUNT queries).
      - Ordering is always stable: by 'name' ASC, then 'id' ASC as tiebreaker.
      - Custom page size via ?page_size=N (default: 5, max: 50).
      - An invalid cursor token returns HTTP 404.
    """

    @staticmethod
    def _create_genres(count):
        """Helper: create `count` genres with predictable alphabetical names."""
        for i in range(1, count + 1):
            Genre.objects.create(name=f"Genre {i:02d}")

    # -- Response envelope ------------------------------------------------

    def test_response_has_pagination_envelope(self):
        """List response must include 'pagination' and 'results' keys."""
        self._create_genres(3)
        response = self.client.get(reverse("genre-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("pagination", response.data)
        self.assertIn("results", response.data)

    def test_pagination_metadata_fields(self):
        """'pagination' block must carry page_size, next, previous, has_next, has_previous."""
        self._create_genres(3)
        response = self.client.get(reverse("genre-list"))
        p = response.data["pagination"]
        for field in ("page_size", "next", "previous", "has_next", "has_previous"):
            self.assertIn(field, p, msg=f"Missing pagination field: {field}")

    def test_no_total_count_field(self):
        """
        Cursor pagination must NOT expose total_count or page_count.
        Those would require a COUNT(*) query, defeating cursor pagination's
        performance advantage.
        """
        self._create_genres(3)
        response = self.client.get(reverse("genre-list"))
        p = response.data["pagination"]
        self.assertNotIn("total_count", p)
        self.assertNotIn("page_count", p)
        self.assertNotIn("current_page", p)

    # -- Default behaviour ------------------------------------------------

    def test_default_page_size_is_5(self):
        """Without ?page_size the default of 5 results should be returned."""
        self._create_genres(8)
        response = self.client.get(reverse("genre-list"))
        self.assertEqual(len(response.data["results"]), 5)
        self.assertEqual(response.data["pagination"]["page_size"], 5)

    def test_all_results_fit_on_one_page(self):
        """When total items <= page_size, all items are returned in one shot."""
        self._create_genres(3)
        response = self.client.get(reverse("genre-list"))
        self.assertEqual(len(response.data["results"]), 3)

    # -- Custom page_size -------------------------------------------------

    def test_custom_page_size(self):
        """?page_size=3 should return 3 results."""
        self._create_genres(8)
        response = self.client.get(reverse("genre-list"), {"page_size": 3})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 3)
        self.assertEqual(response.data["pagination"]["page_size"], 3)

    def test_page_size_capped_at_max(self):
        """?page_size=999 should be silently capped at max_page_size=50."""
        self._create_genres(3)
        response = self.client.get(reverse("genre-list"), {"page_size": 999})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(response.data["pagination"]["page_size"], 50)

    # -- Navigation links on first page -----------------------------------

    def test_first_page_has_next_when_more_results(self):
        """First page has has_next=True and a non-null 'next' URL when there are more items."""
        self._create_genres(8)  # 8 genres, page_size=5 => 2 pages
        response = self.client.get(reverse("genre-list"))
        p = response.data["pagination"]
        self.assertTrue(p["has_next"])
        self.assertIsNotNone(p["next"])

    def test_first_page_has_no_previous(self):
        """First page has has_previous=False and previous=null."""
        self._create_genres(8)
        response = self.client.get(reverse("genre-list"))
        p = response.data["pagination"]
        self.assertFalse(p["has_previous"])
        self.assertIsNone(p["previous"])

    def test_single_page_has_no_next_or_previous(self):
        """When all results fit on one page, both next and previous must be null."""
        self._create_genres(3)  # 3 genres, page_size=5 => fits on one page
        response = self.client.get(reverse("genre-list"))
        p = response.data["pagination"]
        self.assertFalse(p["has_next"])
        self.assertIsNone(p["next"])
        self.assertFalse(p["has_previous"])
        self.assertIsNone(p["previous"])

    # -- Cursor traversal (follow 'next' link) ----------------------------

    def test_cursor_traversal_covers_all_items(self):
        """
        Following 'next' links from page 1 until exhausted must yield
        every item exactly once.
        """
        self._create_genres(12)  # 12 genres, page_size=5 => 3 pages
        collected_names = []
        url = reverse("genre-list")
        params = {"page_size": 5}

        while url:
            response = self.client.get(url, params)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            collected_names.extend(
                item["name"] for item in response.data["results"]
            )
            next_url = response.data["pagination"]["next"]
            # After the first request params are encoded in the cursor URL
            url = next_url
            params = {}  # cursor token already carries all state

        self.assertEqual(len(collected_names), 12)
        # Items must arrive in the declared ordering (name ASC)
        self.assertEqual(collected_names, sorted(collected_names))

    def test_second_page_has_previous_link(self):
        """The second page (reached via 'next') must have a 'previous' link."""
        self._create_genres(8)
        # Get first page
        first = self.client.get(reverse("genre-list"))
        next_url = first.data["pagination"]["next"]
        self.assertIsNotNone(next_url, "Expected a next URL from the first page")

        # Follow next to get second page
        second = self.client.get(next_url)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        p = second.data["pagination"]
        self.assertTrue(p["has_previous"])
        self.assertIsNotNone(p["previous"])

    def test_last_page_has_no_next(self):
        """The final page (no more items) must have has_next=False."""
        self._create_genres(8)  # 8 genres, page_size=5 => last page has 3
        # Navigate to the last page
        first = self.client.get(reverse("genre-list"))
        next_url = first.data["pagination"]["next"]
        last = self.client.get(next_url)

        self.assertEqual(last.status_code, status.HTTP_200_OK)
        p = last.data["pagination"]
        self.assertFalse(p["has_next"])
        self.assertIsNone(p["next"])
        # Last page should contain the remaining 3 genres
        self.assertEqual(len(last.data["results"]), 3)

    # -- Stable ordering --------------------------------------------------

    def test_results_ordered_by_name(self):
        """Results must arrive sorted by 'name' ASC (the declared cursor ordering)."""
        Genre.objects.create(name="Zebra")
        Genre.objects.create(name="Apple")
        Genre.objects.create(name="Mango")
        response = self.client.get(reverse("genre-list"))
        names = [item["name"] for item in response.data["results"]]
        self.assertEqual(names, sorted(names))

    # -- Invalid cursor ---------------------------------------------------

    def test_invalid_cursor_returns_404(self):
        """A tampered / invalid cursor token must return HTTP 404."""
        self._create_genres(3)
        response = self.client.get(reverse("genre-list"), {"cursor": "not-a-valid-cursor"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
