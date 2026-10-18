from rest_framework.pagination import PageNumberPagination


class Pages(PageNumberPagination):
    """Every list comes a page at a time, 5 to a page: ?page=2, and ?page_size= up to 200."""

    page_size_query_param = "page_size"
    max_page_size = 200
    page_size = 5
