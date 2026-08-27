"""Custom pagination classes for the books API."""

from rest_framework.pagination import CursorPagination, LimitOffsetPagination, PageNumberPagination
from rest_framework.response import Response


class BookLimitOffsetPagination(LimitOffsetPagination):
    """
    LimitOffsetPagination with extra metadata in the response envelope.

    Query parameters
    ----------------
    limit   : number of results per page  (default: 10, max: 100)
    offset  : zero-based starting index   (default: 0)

    Response shape
    --------------
    {
        "pagination": {
            "total_count"  : total number of matching objects,
            "limit"        : effective limit,
            "offset"       : effective offset,
            "page_count"   : total number of pages,
            "current_page" : 1-based current page number,
            "next"         : URL of the next page or null,
            "previous"     : URL of the previous page or null,
            "has_next"     : bool,
            "has_previous" : bool
        },
        "results": [ ... ]
    }
    """

    default_limit = 10
    max_limit = 100
    limit_query_param = "limit"
    offset_query_param = "offset"

    def get_paginated_response(self, data):
        total = self.count
        limit = self.limit
        offset = self.offset

        page_count = (total + limit - 1) // limit if limit else 1
        current_page = (offset // limit) + 1 if limit else 1

        return Response(
            {
                "pagination": {
                    "total_count": total,
                    "limit": limit,
                    "offset": offset,
                    "page_count": page_count,
                    "current_page": current_page,
                    "next": self.get_next_link(),
                    "previous": self.get_previous_link(),
                    "has_next": self.get_next_link() is not None,
                    "has_previous": self.get_previous_link() is not None,
                },
                "results": data,
            }
        )

    def get_paginated_response_schema(self, schema):
        """OpenAPI schema for the paginated response."""
        return {
            "type": "object",
            "required": ["pagination", "results"],
            "properties": {
                "pagination": {
                    "type": "object",
                    "properties": {
                        "total_count": {"type": "integer"},
                        "limit": {"type": "integer"},
                        "offset": {"type": "integer"},
                        "page_count": {"type": "integer"},
                        "current_page": {"type": "integer"},
                        "next": {"type": "string", "nullable": True},
                        "previous": {"type": "string", "nullable": True},
                        "has_next": {"type": "boolean"},
                        "has_previous": {"type": "boolean"},
                    },
                },
                "results": schema,
            },
        }


class BookPageNumberPagination(PageNumberPagination):
    """
    PageNumberPagination with a configurable page size and a rich metadata envelope.

    Query parameters
    ----------------
    page          : 1-based page number (default: 1)
    page_size     : results per page — caller-controlled (default: 5, max: 50)

    Response shape
    --------------
    {
        "pagination": {
            "total_count"  : total number of matching objects,
            "page_size"    : effective page size,
            "page_count"   : total number of pages,
            "current_page" : current 1-based page number,
            "next"         : URL of the next page or null,
            "previous"     : URL of the previous page or null,
            "has_next"     : bool,
            "has_previous" : bool
        },
        "results": [ ... ]
    }
    """

    page_size = 5                          # default items per page
    max_page_size = 50                     # hard upper limit
    page_size_query_param = "page_size"    # allow ?page_size=N
    page_query_param = "page"              # allow ?page=N

    def get_paginated_response(self, data):
        paginator = self.page.paginator
        total_count = paginator.count
        page_size = paginator.per_page
        page_count = paginator.num_pages
        current_page = self.page.number

        return Response(
            {
                "pagination": {
                    "total_count": total_count,
                    "page_size": page_size,
                    "page_count": page_count,
                    "current_page": current_page,
                    "next": self.get_next_link(),
                    "previous": self.get_previous_link(),
                    "has_next": self.get_next_link() is not None,
                    "has_previous": self.get_previous_link() is not None,
                },
                "results": data,
            }
        )

    def get_paginated_response_schema(self, schema):
        """OpenAPI schema for the paginated response."""
        return {
            "type": "object",
            "required": ["pagination", "results"],
            "properties": {
                "pagination": {
                    "type": "object",
                    "properties": {
                        "total_count": {"type": "integer"},
                        "page_size": {"type": "integer"},
                        "page_count": {"type": "integer"},
                        "current_page": {"type": "integer"},
                        "next": {"type": "string", "nullable": True},
                        "previous": {"type": "string", "nullable": True},
                        "has_next": {"type": "boolean"},
                        "has_previous": {"type": "boolean"},
                    },
                },
                "results": schema,
            },
        }


class BookCursorPagination(CursorPagination):
    """
    Cursor-based pagination for time-ordered collections.

    How it works
    ------------
    Instead of page numbers or offsets, each response contains opaque
    'next' / 'previous' cursor URLs.  The cursor is a base64-encoded
    position marker — clients simply follow the links without needing
    to know the total count or construct their own URLs.

    Why use it?
    -----------
    - O(1) per page regardless of dataset size (no COUNT(*) query).
    - Stable: new inserts never cause items to appear twice or be skipped.
    - Ideal for real-time / infinite-scroll feeds ordered by time.

    Tradeoff: random access (jump to page 5) is not possible.

    Query parameters
    ----------------
    cursor    : opaque position token (provided by 'next'/'previous' URLs)
    page_size : items per page — caller-controlled (default: 5, max: 50)

    Ordering  : ascending by 'name', then by 'id' as a tiebreaker.

    Response shape
    --------------
    {
        "pagination": {
            "page_size"    : effective page size,
            "next"         : URL with next cursor token or null,
            "previous"     : URL with previous cursor token or null,
            "has_next"     : bool,
            "has_previous" : bool
        },
        "results": [ ... ]
    }

    Note: total_count and page numbers are deliberately absent —
    computing them would defeat the performance advantage of cursor
    pagination.
    """

    page_size = 5
    max_page_size = 50
    page_size_query_param = "page_size"
    cursor_query_param = "cursor"
    ordering = ("name", "id")   # stable, unique ordering required by cursor pagination

    def get_paginated_response(self, data):
        return Response(
            {
                "pagination": {
                    "page_size": self.get_page_size(self.request),
                    "next": self.get_next_link(),
                    "previous": self.get_previous_link(),
                    "has_next": self.get_next_link() is not None,
                    "has_previous": self.get_previous_link() is not None,
                },
                "results": data,
            }
        )

    def get_paginated_response_schema(self, schema):
        """OpenAPI schema for the cursor-paginated response."""
        return {
            "type": "object",
            "required": ["pagination", "results"],
            "properties": {
                "pagination": {
                    "type": "object",
                    "properties": {
                        "page_size": {"type": "integer"},
                        "next": {"type": "string", "nullable": True},
                        "previous": {"type": "string", "nullable": True},
                        "has_next": {"type": "boolean"},
                        "has_previous": {"type": "boolean"},
                    },
                },
                "results": schema,
            },
        }
