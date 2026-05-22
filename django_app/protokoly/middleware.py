from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    """
    Przekierowuje zalogowanych użytkowników z flagą must_change_password
    na stronę zmiany hasła przed dostępem do jakiejkolwiek innej strony.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                must_change = request.user.profile.must_change_password
            except Exception:
                must_change = False

            if must_change:
                change_url = reverse('change_password_forced')
                logout_url = reverse('logout')
                if request.path not in (change_url, logout_url):
                    return redirect(change_url)

        return self.get_response(request)
