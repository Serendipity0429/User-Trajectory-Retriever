from django.shortcuts import render

def custom_error_view(request, exception=None):
    return render(request, 'error_page.html', status=404)