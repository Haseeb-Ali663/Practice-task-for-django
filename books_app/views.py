from rest_framework.decorators import api_view
from rest_framework.response import Response
from books_app.models import Book
from books_app.serializers import BookSerializer

@api_view(['GET'])
def book_list(request):
    books = Book.objects.all()
    serializer = BookSerializer(books, many=True)
    return Response(serializer.data)
