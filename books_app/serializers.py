from datetime import date
from rest_framework import serializers
from books_app.models import Book, Author, Genre


class DynamicFieldsSerializerMixin:
    """
    A serializer mixin that dynamically adapts returned fields based on:
    1. Explicit `fields` / `exclude` iterable passed at instantiation, OR
    2. Query parameters `?fields=field1,field2` or `?exclude=field1,field2` from the request.

    Example requests:
        GET /books/?fields=title,author_name
        GET /books/1/?fields=title,published_date,time_since_published
        GET /authors/?fields=name,bio
    """

    def __init__(self, *args, **kwargs):
        fields = kwargs.pop('fields', None)
        exclude = kwargs.pop('exclude', None)

        super().__init__(*args, **kwargs)

        request = self.context.get('request')
        if request and hasattr(request, 'query_params'):
            if fields is None and 'fields' in request.query_params:
                raw = request.query_params.get('fields', '')
                fields = [f.strip() for f in raw.split(',') if f.strip()]
            if exclude is None and 'exclude' in request.query_params:
                raw_exclude = request.query_params.get('exclude', '')
                exclude = [f.strip() for f in raw_exclude.split(',') if f.strip()]

        if fields is not None:
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name, None)

        if exclude is not None:
            for field_name in set(exclude):
                self.fields.pop(field_name, None)


class AuthorCustomField(serializers.RelatedField):
    """
    A custom relational field that displays the author as
    'Name (born: YYYY-MM-DD)' and accepts an author PK on input.
    """

    def to_representation(self, value):
        dob = value.date_of_birth
        if dob:
            return f"{value.name} (born: {dob})"
        return f"{value.name} (born: unknown)"

    def to_internal_value(self, data):
        try:
            return Author.objects.get(pk=data)
        except Author.DoesNotExist:
            raise serializers.ValidationError(f"Author with id {data} does not exist.")


class GenreSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Genre
        fields = ['url', 'name']


class AuthorSerializer(DynamicFieldsSerializerMixin, serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Author
        fields = ['url', 'name', 'bio', 'date_of_birth']
        extra_kwargs = {
            'name': {'error_messages': {'blank': 'Name cannot be blank.'}},
        }

    def validate_name(self, value):
        if len(value) < 3:
            raise serializers.ValidationError("Name must be at least 3 characters long.")
        return value

    def validate_date_of_birth(self, value):
        if value and value > date.today():
            raise serializers.ValidationError("Date of birth cannot be in the future.")
        return value


class AuthorNestedSerializer(serializers.ModelSerializer):
    """Read-only author payload embedded in each book."""

    class Meta:
        model = Author
        fields = ['id', 'name', 'bio', 'date_of_birth']


class BookListSerializer(DynamicFieldsSerializerMixin, serializers.HyperlinkedModelSerializer):
    """
    Lightweight serializer optimized for collection/list endpoints.
    Excludes heavyweight nested objects and computed analytical properties.
    Supports dynamic field filtering via `?fields=...` query parameter.
    """
    author_name = serializers.CharField(source='author.name', read_only=True)
    genre_names = serializers.StringRelatedField(source='genres', many=True, read_only=True)

    class Meta:
        model = Book
        fields = [
            'url',
            'id',
            'title',
            'author_name',
            'genre_names',
            'published_date',
        ]


class BookDetailSerializer(DynamicFieldsSerializerMixin, serializers.HyperlinkedModelSerializer):
    """
    Comprehensive serializer for single-resource detail views and write actions.
    Includes nested author details, custom representations, validation logic,
    conditional fields based on permissions, and dynamic field filtering via `?fields=...`.
    """
    author = AuthorNestedSerializer(read_only=True)
    author_custom = AuthorCustomField(read_only=True, source='author')
    time_since_published = serializers.SerializerMethodField()
    admin_metadata = serializers.SerializerMethodField(read_only=True)

    # ManyToMany: show genre names on read
    genre_names = serializers.StringRelatedField(source='genres', many=True, read_only=True)
    # ManyToMany: accept genre PKs on write
    genre_ids = serializers.PrimaryKeyRelatedField(
        queryset=Genre.objects.all(),
        source='genres',
        many=True,
        write_only=True,
        required=False
    )
    
    # Required for creating a book, since the 'author' field above is read-only
    author_id = serializers.PrimaryKeyRelatedField(
        queryset=Author.objects.all(), 
        source='author', 
        write_only=True
    )
    
    class Meta:
        model = Book
        fields = [
            'url',
            'id',
            'title',
            'author',
            'author_custom',
            'author_id',
            'genre_names',
            'genre_ids',
            'published_date',
            'time_since_published',
            'admin_metadata',
        ]
        extra_kwargs = {
            'title': {'error_messages': {'blank': 'Title cannot be blank.'}},
        }

    def __init__(self, *args, **kwargs):
        """
        Dynamically include/exclude fields based on query parameters and permissions.
        """
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        is_staff = bool(user and getattr(user, "is_authenticated", False) and getattr(user, "is_staff", False))
        if not is_staff:
            self.fields.pop("admin_metadata", None)

    def get_admin_metadata(self, obj):
        return {
            "internal_code": f"LIB-BK-{obj.id:05d}",
            "author_id": obj.author_id,
            "genres_count": obj.genres.count(),
        }

    def get_time_since_published(self, obj):
        if not obj.published_date:
            return None

        today = date.today()
        years = today.year - obj.published_date.year
        months = today.month - obj.published_date.month
        days = today.day - obj.published_date.day

        if days < 0:
            months -= 1
            days += 30  # approximation for previous month's days
        if months < 0:
            years -= 1
            months += 12

        parts = []
        if years > 0:
            parts.append(f"{years} year{'s' if years > 1 else ''}")
        if months > 0:
            parts.append(f"{months} month{'s' if months > 1 else ''}")
        if days > 0 or not parts:
            parts.append(f"{days} day{'s' if days != 1 else ''}")

        return ", ".join(parts)

    def validate_published_date(self, value):
        if value > date.today():
            raise serializers.ValidationError("Published date cannot be in the future.")
        return value

    def validate(self, data):
        author = data.get('author') or getattr(self.instance, 'author', None)
        published_date = data.get('published_date') or getattr(self.instance, 'published_date', None)

        if author and author.date_of_birth and published_date:
            if published_date < author.date_of_birth:
                raise serializers.ValidationError(
                    "Published date cannot be before the author's date of birth."
                )
        return data


# Alias for backward compatibility
BookSerializer = BookDetailSerializer


class GenreAssignSerializer(serializers.Serializer):
    """Input for BookViewSet's 'add-genres' action: a list of existing Genre PKs."""

    genre_ids = serializers.PrimaryKeyRelatedField(
        queryset=Genre.objects.all(),
        many=True,
        allow_empty=False,
    )


class AuthorBookCountSerializer(AuthorSerializer):
    """AuthorSerializer plus the annotated `book_count` from the 'prolific' action."""

    book_count = serializers.IntegerField(read_only=True)

    class Meta(AuthorSerializer.Meta):
        fields = AuthorSerializer.Meta.fields + ['book_count']


class BookStatisticsSerializer(serializers.Serializer):
    """Statistics and analytical metrics for a specific book."""

    book_id = serializers.IntegerField(source='id')
    title = serializers.CharField()
    author_name = serializers.CharField(source='author.name')
    total_genres = serializers.SerializerMethodField()
    days_since_published = serializers.SerializerMethodField()
    years_since_published = serializers.SerializerMethodField()
    author_total_books = serializers.SerializerMethodField()
    author_age_at_publication = serializers.SerializerMethodField()
    title_word_count = serializers.SerializerMethodField()
    title_character_count = serializers.SerializerMethodField()

    def get_total_genres(self, obj):
        return obj.genres.count()

    def get_days_since_published(self, obj):
        if not obj.published_date:
            return None
        return (date.today() - obj.published_date).days

    def get_years_since_published(self, obj):
        if not obj.published_date:
            return None
        return round((date.today() - obj.published_date).days / 365.25, 2)

    def get_author_total_books(self, obj):
        return Book.objects.filter(author=obj.author).count()

    def get_author_age_at_publication(self, obj):
        if not obj.author.date_of_birth or not obj.published_date:
            return None
        dob = obj.author.date_of_birth
        pub = obj.published_date
        return pub.year - dob.year - ((pub.month, pub.day) < (dob.month, dob.day))

    def get_title_word_count(self, obj):
        return len(obj.title.split())

    def get_title_character_count(self, obj):
        return len(obj.title)

