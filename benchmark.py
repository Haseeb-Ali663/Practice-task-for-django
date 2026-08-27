"""
Performance Optimization Benchmark Script.
Run with: python benchmark.py
"""

import os
import time
from datetime import date

import django

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "books.settings")
django.setup()

from django.conf import settings
from django.db import connection, reset_queries
from books_app.models import Author, Book, Genre

# Enable SQL query tracking
settings.DEBUG = True


def setup_sample_data(num_books=20):
    """Seed sample authors, genres, and books for benchmarking."""
    print("=" * 65)
    print(f"[+] Setting up test database with {num_books} books...")

    # Clear existing data
    Book.objects.all().delete()
    Author.objects.all().delete()
    Genre.objects.all().delete()

    genres = [Genre.objects.create(name=f"Genre-{i}") for i in range(1, 5)]
    authors = [
        Author.objects.create(name=f"Author-{i}", date_of_birth=date(1980, 1, 1))
        for i in range(1, 6)
    ]

    for i in range(1, num_books + 1):
        book = Book.objects.create(
            title=f"Sample Book {i:02d}",
            author=authors[i % len(authors)],
            published_date=date(2000 + (i % 20), 1, 1),
        )
        book.genres.set(genres[: (i % 4) + 1])

    print("[+] Sample data ready.\n")


def run_benchmark():
    num_books = Book.objects.count()

    print("=" * 65)
    print(f"[*] RUNNING BENCHMARK ({num_books} Books in Database)")
    print("=" * 65)

    # -------------------------------------------------------------
    # 1. UNOPTIMIZED TRAVERSAL (N+1 Query Problem)
    # -------------------------------------------------------------
    reset_queries()
    start_unopt = time.perf_counter()

    unopt_books = list(Book.objects.all())
    unopt_results = []
    for b in unopt_books:
        unopt_results.append(
            {
                "title": b.title,
                "author": b.author.name,  # Triggers 1 SELECT per book
                "genres": [g.name for g in b.genres.all()],  # Triggers 1 SELECT per book
            }
        )

    time_unopt = (time.perf_counter() - start_unopt) * 1000  # in ms
    queries_unopt = len(connection.queries)

    # -------------------------------------------------------------
    # 2. FULLY OPTIMIZED (select_related + prefetch_related)
    # -------------------------------------------------------------
    reset_queries()
    start_opt = time.perf_counter()

    opt_books = list(
        Book.objects.select_related("author").prefetch_related("genres")
    )
    opt_results = []
    for b in opt_books:
        opt_results.append(
            {
                "title": b.title,
                "author": b.author.name,  # 0 extra queries (JOINed in 1st query)
                "genres": [g.name for g in b.genres.all()],  # 0 extra queries (prefetched in 2nd query)
            }
        )

    time_opt = (time.perf_counter() - start_opt) * 1000  # in ms
    queries_opt = len(connection.queries)

    # -------------------------------------------------------------
    # 3. CONDITIONAL PREFETCHING (?fields=title,published_date)
    # -------------------------------------------------------------
    reset_queries()
    start_cond = time.perf_counter()

    cond_books = list(Book.objects.only("id", "title", "published_date"))
    cond_results = [{"title": b.title} for b in cond_books]

    time_cond = (time.perf_counter() - start_cond) * 1000  # in ms
    queries_cond = len(connection.queries)

    # -------------------------------------------------------------
    # RESULTS TABLE
    # -------------------------------------------------------------
    query_reduction = ((queries_unopt - queries_opt) / queries_unopt) * 100

    print(f"{'Strategy':<35} | {'SQL Queries':<12} | {'Time (ms)':<10}")
    print("-" * 65)
    print(f"{'1. Unoptimized (N+1 Problem)':<35} | {queries_unopt:<12} | {time_unopt:<10.2f}")
    print(f"{'2. select_related + prefetch_related':<35} | {queries_opt:<12} | {time_opt:<10.2f}")
    print(f"{'3. Conditional Prefetch (?fields=title)':<35} | {queries_cond:<12} | {time_cond:<10.2f}")
    print("-" * 65)
    print(f"\n[Result] Query Reduction: {query_reduction:.1f}% fewer SQL queries ({queries_unopt} -> {queries_opt})")
    print(f"[Result] Time Improvement: {time_unopt / max(time_opt, 0.001):.1f}x faster\n")
    print("=" * 65)


if __name__ == "__main__":
    setup_sample_data(num_books=25)
    run_benchmark()
