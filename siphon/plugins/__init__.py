class ClientWrapperMixin:
    def __getstate__(self):
        state = self.__dict__.copy()
        state.pop("_client", None)
        return state

    def __getattr__(self, name: str):
        if name == "_client":
            raise AttributeError(name)

        try:
            client = object.__getattribute__(self, "_client")
        except AttributeError:
            client = self._build_client()
            object.__setattr__(self, "_client", client)

        return getattr(client, name)

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._client = self._build_client()