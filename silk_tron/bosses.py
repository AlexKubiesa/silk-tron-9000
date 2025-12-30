from dataclasses import dataclass


@dataclass
class Boss:
    name: str
    max_hp: int


BOSSES = {
    "Lace": Boss(name="Lace", max_hp=800),
    "MossMother": Boss(name="MossMother", max_hp=120),
}
