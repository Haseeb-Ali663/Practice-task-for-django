from datetime import date
from rest_framework import serializers
from books_app.models import Book, Author, Genre


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


class AuthorSerializer(serializers.HyperlinkedModelSerializer):
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

class BookSerializer(serializers.HyperlinkedModelSerializer):
    # author = AuthorSerializer(read_only=True)
    author = serializers.SerializerMethodField()
    author_custom = AuthorCustomField(read_only=True, source='author')
    time_since_published = serializers.SerializerMethodField()

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
        fields = ['url', 'id', 'title', 'author', 'author_custom', 'author_id', 'genre_names', 'genre_ids', 'published_date', 'time_since_published']
        extra_kwargs = {
            'title': {'error_messages': {'blank': 'Title cannot be blank.'}},
        }

    def get_author(self, obj):
        return {
            "id": obj.author.id,
            "name": obj.author.name,
            "bio": obj.author.bio,
            "date_of_birth": obj.author.date_of_birth
        }

    def get_time_since_published(self, obj):
        if obj.published_date:
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
        return None

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
