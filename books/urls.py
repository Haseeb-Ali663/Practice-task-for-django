from django.contrib import admin
from django.urls import path
from books_app.views import BookListCreate, BookDetailView, AuthorListCreate, AuthorDetailView, GenreListCreate, GenreDetailView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('books/', BookListCreate.as_view(), name='book-list'),
    path('books/<int:pk>/', BookDetailView.as_view(), name='book-detail'),
    path('authors/', AuthorListCreate.as_view(), name='author-list'),
    path('authors/<int:pk>/', AuthorDetailView.as_view(), name='author-detail'),
    path('genres/', GenreListCreate.as_view(), name='genre-list'),
    path('genres/<int:pk>/', GenreDetailView.as_view(), name='genre-detail'),
]
