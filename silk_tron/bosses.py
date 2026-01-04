from dataclasses import dataclass


@dataclass
class Boss:
    name: str
    max_hp: int
    arena_min_x: float
    arena_max_x: float
    arena_min_y: float
    arena_max_y: float
    vel_x_range: tuple[float, float]
    vel_y_range: tuple[float, float]


BOSSES = {
    "Lace": Boss(
        name="Lace",
        max_hp=800,
        arena_min_x=32.68,
        arena_max_x=78.26,
        arena_min_y=95.0,
        arena_max_y=125.0,
        vel_x_range=(-67.0, 67.0),
        vel_y_range=(-65.0, 60.0),
    ),
    "MossMother": Boss(
        name="MossMother",
        max_hp=120,
        arena_min_x=45.44,
        arena_max_x=68.56,
        arena_min_y=17.50,
        arena_max_y=29.25,
        vel_x_range=(-20.0, 20.0),
        vel_y_range=(-22.0, 25.0),
    ),
}
