from django.shortcuts import render
from django.views.static import serve
from django.conf import settings


def custom_error_view(request, exception=None):
    return render(request, "error_page.html", status=404)


def custom_permission_denied_view(request, exception=None):
    return render(
        request,
        "error_page.html",
        {"message": "You do not have permission to access this page."},
        status=403,
    )


def custom_bad_request_view(request, exception=None):
    return render(request, "error_page.html", {"message": "Bad request."}, status=400)


def custom_server_error_view(request):
    return render(
        request,
        "error_page.html",
        {"message": "An internal server error occurred."},
        status=500,
    )


def protected_serve(request, path, document_root=None, show_indexes=False):
    return serve(request, path, document_root, show_indexes)
