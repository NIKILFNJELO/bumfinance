from django.shortcuts import redirect

PUBLIC_PATHS = ('/accounts/', '/signup/', '/admin/')

class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated and not request.path.startswith(PUBLIC_PATHS):
            return redirect('login')
        return self.get_response(request)