from typing import Dict, Tuple


class ReprMixin:
    __repr_attrs__: Tuple[str]

    def __repr__(self) -> str:
        kwargs: Dict[str, str] = dict()
        for identifier in self.__class__.__repr_attrs__:
            attr = getattr(self, identifier)
            if callable(attr):
                attr = attr()

            kwargs[identifier] = attr

        return f"{self.__class__.__name__}({', '.join([f'{k}={v}' for k, v in kwargs.items()])})"
