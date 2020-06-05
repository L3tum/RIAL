from functools import lru_cache

from rial.concept.TransformerInterpreter import TransformerInterpreter


class CombinedTransformer(TransformerInterpreter):
    def __init__(self, *transformers):
        super().__init__()
        self.transformers = transformers

    @lru_cache(128)
    def __getattr__(self, key):
        for transformer in reversed(self.transformers):
            try:
                return getattr(transformer, key)
            except AttributeError:
                pass
        raise AttributeError(key)

    def __add__(self, other):
        return CombinedTransformer(*self.transformers, other)
