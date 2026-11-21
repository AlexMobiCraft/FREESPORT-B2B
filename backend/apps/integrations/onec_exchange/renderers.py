from rest_framework import renderers


class PlainTextRenderer(renderers.BaseRenderer):
    media_type = "text/plain"
    format = "txt"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if isinstance(data, str):
            return data.encode("utf-8")
        # Handle dicts (errors) from DRF
        if isinstance(data, dict):
            if "detail" in data:
                return f"failure\n{data['detail']}".encode("utf-8")
        return str(data).encode("utf-8")
