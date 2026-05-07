class Stage:
    """Pipeline stage. Subclasses set `name` and override `process`."""

    name: str

    def process(self, row: dict) -> None:
        raise NotImplementedError

    def stats(self) -> dict:
        return {}
