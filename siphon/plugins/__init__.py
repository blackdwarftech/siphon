class ClientWrapperMixin:
    def __getstate__(self):
        state = self.__dict__.copy()
        state.pop("_client", None)
        return state

    def __getattr__(self, name: str):
        # Allow _client to be lazily rebuilt after unpickling
        if name == "_client":
            try:
                client = self._build_client()
                object.__setattr__(self, "_client", client)
                return client
            except Exception as e:
                raise AttributeError(f"Failed to rebuild _client: {e}") from e

        try:
            client = object.__getattribute__(self, "_client")
        except AttributeError:
            client = self._build_client()
            object.__setattr__(self, "_client", client)

        return getattr(client, name)

    def __setstate__(self, state):
        self.__dict__.update(state)
        try:
            self._client = self._build_client()
        except Exception:
            # Defer rebuild to __getattr__ if build fails during unpickle
            pass