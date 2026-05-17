class PermissionsPolicyMiddleware:
    """Set a permissive policy for features needed by embedded media players."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['Permissions-Policy'] = (
            'picture-in-picture=(self "https://www.youtube.com" "https://www.youtube-nocookie.com")'
        )
        return response
