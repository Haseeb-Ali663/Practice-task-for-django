from django.db import models

class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Author(models.Model):
    name = models.CharField(max_length=50)
    bio = models.TextField(max_length=200,default="")
    date_of_birth = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return self.name

class Book(models.Model):
    title = models.CharField(max_length=50)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    published_date = models.DateField()
    genres = models.ManyToManyField(Genre, blank=True, related_name='books')

    def __str__(self):
        return self.title

