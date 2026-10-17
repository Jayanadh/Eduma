from rest_framework.pagination import PageNumberPagination


class Pages(PageNumberPagination):
    """Long lists (registers, institutions, audit) come a page at a time: ?page=2, and ?page_size= up to 200."""

    page_size_query_param = "page_size"
    max_page_size = 200
    page_size = 50
