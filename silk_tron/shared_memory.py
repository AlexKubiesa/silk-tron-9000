import atexit
from dataclasses import dataclass
from enum import IntEnum
from multiprocessing import shared_memory
import os
from pathlib import Path
import signal
import struct
import subprocess
import time
import logging

import numpy as np

from silk_tron.constants import (
    ARENA_MAX_X,
    ARENA_MAX_Y,
    ARENA_MIN_X,
    ARENA_MIN_Y,
    BOSS_MAX_HEALTH,
    BOSS_VEL_X_RANGE,
    BOSS_VEL_Y_RANGE,
    HERO_VEL_X_RANGE,
    HERO_VEL_Y_RANGE,
    NUM_BOSS_ANIMATION_STATES,
    NUM_PLAYER_ANIMATION_STATES,
    PLAYER_MAX_HEALTH,
    PLAYER_MAX_SILK,
)


_active_instances: list["SilkSongSharedMemory"] = []


def _cleanup_all():
    for instance in _active_instances[:]:
        try:
            instance.close()
        except Exception:
            pass


atexit.register(_cleanup_all)


def _signal_handler(signum, frame):
    _cleanup_all()
    raise KeyboardInterrupt


signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)


class GameTimeoutError(Exception):
    pass


class CommandType(IntEnum):
    NONE = 0
    STEP = 1
    RESET = 2


class StateType(IntEnum):
    NONE = 0
    READY = 1
    STEP = 2
    RESET = 3


@dataclass
class GameState:
    player_pos_x: float
    player_pos_y: float
    player_vel_x: float
    player_vel_y: float
    player_health: int
    player_max_health: int
    player_silk: int
    player_animation_state: int
    player_animation_progress: float
    player_grounded: bool
    player_can_dash: bool
    player_facing_right: bool
    player_invincible: bool
    player_can_attack: bool

    boss_pos_x: float
    boss_pos_y: float
    boss_vel_x: float
    boss_vel_y: float
    boss_health: int
    boss_max_health: int
    boss_phase: int
    boss_animation_state: int
    boss_animation_progress: float
    boss_facing_right: bool

    episode_time: float
    terminated: bool
    truncated: bool

    raycast_distances: np.ndarray
    raycast_hit_types: np.ndarray

    MAX_DISTANCE = np.sqrt(
        (ARENA_MAX_X - ARENA_MIN_X) ** 2 + (ARENA_MAX_Y - ARENA_MIN_Y) ** 2
    )

    def to_observation(self) -> np.ndarray:
        norm_player_x = (self.player_pos_x - ARENA_MIN_X) / (ARENA_MAX_X - ARENA_MIN_X)
        norm_player_y = (self.player_pos_y - ARENA_MIN_Y) / (ARENA_MAX_Y - ARENA_MIN_Y)
        norm_boss_x = (self.boss_pos_x - ARENA_MIN_X) / (ARENA_MAX_X - ARENA_MIN_X)
        norm_boss_y = (self.boss_pos_y - ARENA_MIN_Y) / (ARENA_MAX_Y - ARENA_MIN_Y)

        norm_player_vel_x = (self.player_vel_x - HERO_VEL_X_RANGE[0]) / (
            HERO_VEL_X_RANGE[1] - HERO_VEL_X_RANGE[0]
        )
        norm_player_vel_y = (self.player_vel_y - HERO_VEL_Y_RANGE[0]) / (
            HERO_VEL_Y_RANGE[1] - HERO_VEL_Y_RANGE[0]
        )
        norm_boss_vel_x = (self.boss_vel_x - BOSS_VEL_X_RANGE[0]) / (
            BOSS_VEL_X_RANGE[1] - BOSS_VEL_X_RANGE[0]
        )
        norm_boss_vel_y = (self.boss_vel_y - BOSS_VEL_Y_RANGE[0]) / (
            BOSS_VEL_Y_RANGE[1] - BOSS_VEL_Y_RANGE[0]
        )

        rel_x = (self.boss_pos_x - self.player_pos_x) / (ARENA_MAX_X - ARENA_MIN_X)
        rel_y = (self.boss_pos_y - self.player_pos_y) / (ARENA_MAX_Y - ARENA_MIN_Y)
        distance = (
            np.sqrt(
                (self.boss_pos_x - self.player_pos_x) ** 2
                + (self.boss_pos_y - self.player_pos_y) ** 2
            )
            / self.MAX_DISTANCE
        )

        state_obs = np.array(
            [
                np.clip(norm_player_x, 0.0, 1.0),
                np.clip(norm_player_y, 0.0, 1.0),
                np.clip(norm_player_vel_x, 0.0, 1.0),
                np.clip(norm_player_vel_y, 0.0, 1.0),
                float(self.player_health) / PLAYER_MAX_HEALTH,
                float(self.player_silk) / PLAYER_MAX_SILK,
                float(self.player_grounded),
                float(self.player_can_dash),
                float(self.player_facing_right),
                float(self.player_invincible),
                float(self.player_can_attack),
                np.clip(norm_boss_x, 0.0, 1.0),
                np.clip(norm_boss_y, 0.0, 1.0),
                np.clip(norm_boss_vel_x, 0.0, 1.0),
                np.clip(norm_boss_vel_y, 0.0, 1.0),
                float(self.boss_health) / BOSS_MAX_HEALTH,
                float(self.boss_phase) / 2.0,
                float(self.boss_facing_right),
                np.clip(
                    rel_x + 0.5, 0.0, 1.0
                ),  # Shouldn't rel_x and rel_y be divided by 2 first?
                np.clip(rel_y + 0.5, 0.0, 1.0),
                np.clip(distance, 0.0, 1.0),
                float(
                    np.clip(self.boss_animation_state, 0, NUM_BOSS_ANIMATION_STATES - 1)
                ),  # Shouldn't we one-hot encode or embed the animation state?
                np.clip(self.boss_animation_progress, 0.0, 1.0),
                float(
                    np.clip(
                        self.player_animation_state, 0, NUM_PLAYER_ANIMATION_STATES - 1
                    )
                ),
                np.clip(self.player_animation_progress, 0.0, 1.0),
            ],
            dtype=np.float32,
        )

        raycast_obs = np.concatenate([self.raycast_distances, self.raycast_hit_types])

        observe = np.concatenate([state_obs, raycast_obs.astype(np.float32)])

        return observe


class SilkSongSharedMemory:
    MEMORY_NAME = "silk_tron"
    EVENT_NAME = "silk_tron_state_event"
    MEMORY_SIZE = 4096

    STATE_OFFSET = 0
    GAME_STATE_OFFSET = 4
    COMMAND_OFFSET = 1024

    GAME_STATE_FORMAT = (
        "ffff"
        + "iiii"
        + "f"
        + "BBBBB"
        + "xxx"
        + "ffff"
        + "iiii"
        + "f"
        + "B"
        + "xxx"
        + "f"
        + "BB"
        + "xx"
        + "f" * 32
        + "i" * 32
    )

    DEFAULT_TIMEOUT_MS = 30000

    @staticmethod
    def get_game_path() -> str:
        game_path = os.getenv("SILKSONG_PATH")
        if not game_path:
            raise ValueError("SILKSONG_PATH environment variable is not set")

        return game_path

    def __init__(
        self,
        time_scale: float = 1.0,
        no_fx: bool = False,
        timeout_ms: int | None = None,
    ):
        self.time_scale = time_scale
        self.no_fx = no_fx
        self.process = None
        self.timeout_ms = (
            timeout_ms if timeout_ms is not None else self.DEFAULT_TIMEOUT_MS
        )

        game_path = self.get_game_path()

        self.shm = shared_memory.SharedMemory(
            name=self.MEMORY_NAME,
            create=True,
            size=self.MEMORY_SIZE,
        )
        self.shm.buf[:] = bytes(self.MEMORY_SIZE)  # type: ignore
        logging.info(f"Created shared memory: {self.MEMORY_NAME}")

        args = [game_path, "--time-scale", str(time_scale)]
        if no_fx:
            args.append("--no-fx")

        game_dir = str(Path(game_path).parent)

        logging.info(f"Launching game from: {game_path}")
        logging.info(f"Time scale: {time_scale}, NoFx: {no_fx}")
        self.process = subprocess.Popen(args, cwd=game_dir)

        logging.info(f"Waiting for game to connect...")
        self.wait_for_state(StateType.READY, timeout_ms=60000)
        logging.info(f"Game connected!")

        _active_instances.append(self)

    def read_state(self) -> StateType:
        return struct.unpack_from("i", self.shm.buf, offset=self.STATE_OFFSET)[0]  # type: ignore

    def read_game_state(self) -> GameState:
        data = struct.unpack_from(
            self.GAME_STATE_FORMAT, self.shm.buf, offset=self.GAME_STATE_OFFSET  # type: ignore
        )

        raycast_distances = np.array(data[27:59], dtype=np.float32)
        raycast_hit_types = np.array(data[59:91], dtype=np.float32)

        return GameState(
            player_pos_x=data[0],
            player_pos_y=data[1],
            player_vel_x=data[2],
            player_vel_y=data[3],
            player_health=data[4],
            player_max_health=data[5],
            player_silk=data[6],
            player_animation_state=data[7],
            player_animation_progress=data[8],
            player_grounded=bool(data[9]),
            player_can_dash=bool(data[10]),
            player_facing_right=bool(data[11]),
            player_invincible=bool(data[12]),
            player_can_attack=bool(data[13]),
            boss_pos_x=data[14],
            boss_pos_y=data[15],
            boss_vel_x=data[16],
            boss_vel_y=data[17],
            boss_health=data[18],
            boss_max_health=data[19],
            boss_phase=data[20],
            boss_animation_state=data[21],
            boss_animation_progress=data[22],
            boss_facing_right=bool(data[23]),
            episode_time=data[24],
            terminated=bool(data[25]),
            truncated=bool(data[26]),
            raycast_distances=raycast_distances,
            raycast_hit_types=raycast_hit_types,
        )

    def send_command(
        self,
        command_type: CommandType,
        left: bool = False,
        right: bool = False,
        up: bool = False,
        down: bool = False,
        jump: bool = False,
        attack: bool = False,
        dash: bool = False,
        clawline: bool = False,
        skill: bool = False,
        heal: bool = False,
    ):
        offset = self.COMMAND_OFFSET

        logging.debug(f"Sending command.")

        struct.pack_into("i", self.shm.buf, offset + 0, int(command_type))  # type: ignore
        struct.pack_into("B", self.shm.buf, offset + 4, 1 if left else 0)  # type: ignore
        struct.pack_into("B", self.shm.buf, offset + 5, 1 if right else 0)  # type: ignore
        struct.pack_into("B", self.shm.buf, offset + 6, 1 if up else 0)  # type: ignore
        struct.pack_into("B", self.shm.buf, offset + 7, 1 if down else 0)  # type: ignore
        struct.pack_into("B", self.shm.buf, offset + 8, 1 if jump else 0)  # type: ignore
        struct.pack_into("B", self.shm.buf, offset + 9, 1 if attack else 0)  # type: ignore
        struct.pack_into("B", self.shm.buf, offset + 10, 1 if dash else 0)  # type: ignore
        struct.pack_into("B", self.shm.buf, offset + 11, 1 if clawline else 0)  # type: ignore
        struct.pack_into("B", self.shm.buf, offset + 12, 1 if skill else 0)  # type: ignore
        struct.pack_into("B", self.shm.buf, offset + 13, 1 if heal else 0)  # type: ignore
        struct.pack_into("i", self.shm.buf, offset + 14, 1)  # type: ignore

    def wait_for_state(self, state_type: StateType, timeout_ms: int | None = None):
        if timeout_ms is None:
            timeout_ms = self.timeout_ms

        deadline_s = time.monotonic() + timeout_ms / 1000.0
        poll_interval_s = 0.01

        while True:
            current_state = self.read_state()
            if current_state == state_type:
                struct.pack_into(
                    "i", self.shm.buf, self.STATE_OFFSET, int(StateType.READY)  # type: ignore
                )
                break

            if time.monotonic() >= deadline_s:
                raise GameTimeoutError(
                    f"Game did not respond within {timeout_ms}ms. "
                    f"Expected state: {state_type.name}, current state: {StateType(current_state).name}"
                )

            time.sleep(poll_interval_s)

    def reset(self) -> GameState:
        self.send_command(CommandType.RESET)
        self.wait_for_state(StateType.RESET)
        return self.read_game_state()

    def step(self, action: np.ndarray) -> GameState:
        if len(action) != 10:
            raise ValueError(f"Action must have 10 elements, got {len(action)}")

        self.send_command(
            CommandType.STEP,
            left=bool(action[0]),
            right=bool(action[1]),
            up=bool(action[2]),
            down=bool(action[3]),
            jump=bool(action[4]),
            attack=bool(action[5]),
            dash=bool(action[6]),
            clawline=bool(action[7]),
            skill=bool(action[8]),
            heal=bool(action[9]),
        )
        self.wait_for_state(StateType.STEP)
        return self.read_game_state()

    def restart(self):
        print("Restarting game...")

        if self.process is not None:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None

        self.shm.buf[:] = bytes(self.MEMORY_SIZE)  # type: ignore

        game_path = self.get_game_path()
        args = [game_path, "--time-scale", str(self.time_scale)]
        if self.no_fx:
            args.append("--no-fx")

        print(f"Launching game from: {game_path}")

        game_dir = Path(game_path).parent
        self.process = subprocess.Popen(args, cwd=game_dir)

        print("Waiting for game to connect...")
        self.wait_for_state(StateType.READY, timeout_ms=60000)
        print("Game reconnected!")

    def close(self):
        if self in _active_instances:
            _active_instances.remove(self)

        if self.process is not None:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None

        if hasattr(self, "shm") and self.shm is not None:
            try:
                self.shm.close()
                self.shm.unlink()
            except Exception:
                pass
            self.shm = None
