class Stage:
    """Pipeline stage. Subclasses set `name` and override `process`.

    Stages may also override `process_batch` if they can do meaningful work
    on a list of rows at once (e.g. dispatch in parallel). The default
    implementation just loops over `process`.
    """

    name: str

    def process(self, row: dict) -> None:
        raise NotImplementedError

    def process_batch(self, rows: list[dict]) -> None:
        for row in rows:
            self.process(row)

    def stats(self) -> dict:
        return {}
