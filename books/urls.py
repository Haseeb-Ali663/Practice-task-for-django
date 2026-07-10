from django.contrib import admin
from django.urls import path
from books_app.views import book_list

urlpatterns = [
    path('admin/', admin.site.urls),
    path('books/', book_list, name='book_list'),
]
