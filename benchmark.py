"""
Performance Optimization Benchmark Script (Strictly Read-Only).
Run with: python benchmark.py

This script NEVER modifies, adds, or deletes any data in your database.
It evaluates whatever records currently exist in your database.
"""

import os
import time

import django

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "books.settings")
django.setup()

from django.conf import settings
from django.db import connection, reset_queries
from books_app.models import Book

# Enable SQL query tracking
settings.DEBUG = True


def run_benchmark():
    total_books = Book.objects.count()

    print("=" * 65)
    print(f"[*] READ-ONLY BENCHMARK ({total_books} Books Found in Database)")
    print("=" * 65)

    if total_books == 0:
        print("[!] No books found in your database.")
        print("[!] Add some books through your API or admin, then run this again.\n")
        return

    # -------------------------------------------------------------
    # 1. UNOPTIMIZED TRAVERSAL (N+1 Query Problem)
    # -------------------------------------------------------------
    reset_queries()
    start_unopt = time.perf_counter()

    unopt_books = list(Book.objects.all())
    for b in unopt_books:
        _ = b.author.name          # Triggers 1 extra query per book
        _ = [g.name for g in b.genres.all()]  # Triggers 1 extra query per book

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
    for b in opt_books:
        _ = b.author.name          # 0 extra queries (JOINed in query 1)
        _ = [g.name for g in b.genres.all()]  # 0 extra queries (prefetched in query 2)

    time_opt = (time.perf_counter() - start_opt) * 1000  # in ms
    queries_opt = len(connection.queries)

    # -------------------------------------------------------------
    # 3. CONDITIONAL PREFETCHING (?fields=title,published_date)
    # -------------------------------------------------------------
    reset_queries()
    start_cond = time.perf_counter()

    cond_books = list(Book.objects.only("id", "title", "published_date"))
    _ = [b.title for b in cond_books]

    time_cond = (time.perf_counter() - start_cond) * 1000  # in ms
    queries_cond = len(connection.queries)

    # -------------------------------------------------------------
    # RESULTS TABLE
    # -------------------------------------------------------------
    query_reduction = (
        ((queries_unopt - queries_opt) / queries_unopt) * 100
        if queries_unopt > 0
        else 0
    )

    print(f"{'Strategy':<35} | {'SQL Queries':<12} | {'Time (ms)':<10}")
    print("-" * 65)
    print(f"{'1. Unoptimized (N+1 Problem)':<35} | {queries_unopt:<12} | {time_unopt:<10.2f}")
    print(f"{'2. select_related + prefetch_related':<35} | {queries_opt:<12} | {time_opt:<10.2f}")
    print(f"{'3. Conditional Prefetch (?fields=title)':<35} | {queries_cond:<12} | {time_cond:<10.2f}")
    print("-" * 65)
    print(f"\n[Result] Query Reduction: {query_reduction:.1f}% fewer SQL queries ({queries_unopt} -> {queries_opt})")
    print(f"[Result] Time Improvement: {time_unopt / max(time_opt, 0.001):.1f}x faster\n")
    print("=" * 65)
    print("[+] Database was read only. Zero records added, modified, or deleted.\n")


if __name__ == "__main__":
    run_benchmark()

