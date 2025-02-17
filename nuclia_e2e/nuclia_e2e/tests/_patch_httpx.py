import httpx

_original_init = httpx.AsyncClient.__init__


def custom_init(self, *args, timeout=httpx.Timeout(100), **kwargs):
    """Override httpx.Client.__init__ to set a custom default timeout."""
    if "timeout" not in kwargs:
        kwargs["timeout"] = timeout
    _original_init(self, *args, **kwargs)


# Apply the patch
httpx.AsyncClient.__init__ = custom_init
