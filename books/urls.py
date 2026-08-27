from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from books_app.views import BookViewSet, AuthorViewSet, GenreViewSet

router = DefaultRouter()
router.register(r'books', BookViewSet, basename='book')
router.register(r'authors', AuthorViewSet, basename='author')
router.register(r'genres', GenreViewSet, basename='genre')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include(router.urls)),
]
