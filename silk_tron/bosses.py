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
    # The arena was measured from the hero's position at its corners. Its floor is y=8.56, and 19.64 was the
    # highest jump tried. The ceiling is estimated from the ceiling gate at y=24.9.
    # The velocity ranges are the largest seen in one fight, -51.0 to 51.8 and -48.5 to 12.9, with a margin.
    "Widow": Boss(
        name="Widow",
        max_hp=360,
        arena_min_x=37.2,
        arena_max_x=67.8,
        arena_min_y=8.5,
        arena_max_y=24.5,
        vel_x_range=(-55.0, 55.0),
        vel_y_range=(-52.0, 16.0),
    ),
}
