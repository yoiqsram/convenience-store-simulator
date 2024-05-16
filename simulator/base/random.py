from numpy import random
from typing import List


class RandomGeneratorMixin:
    def __init_rng__(self, seed: int = None):
        self._rng = random.RandomState(seed)

    def random_seed(
            self,
            size: int,
            maxlen: int = 6
        ) -> List[int]:
        return int(self._rng.random(size) * int('1' + '0' * maxlen))
