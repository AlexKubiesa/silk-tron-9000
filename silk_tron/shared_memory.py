import atexit
from dataclasses import dataclass
from enum import IntEnum
from multiprocessing import shared_memory
import os
from pathlib import Path
import select
import shutil
import signal
import struct
import subprocess
import time
import logging

import numpy as np


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
    player_can_clawline: bool

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

    def __post_init__(self):
        # Ensure boss health is non-negative
        if self.boss_health < 0:
            self.boss_health = 0


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
        + "BBBB"
        + "BBxx"
        + "ffff"
        + "iiii"
        + "f"
        + "Bxxx"
        + "f"
        + "BBxx"
        + "f" * 32
        + "i" * 32
    )

    DEFAULT_TIMEOUT_MS = 30000
    LAUNCH_ATTEMPTS = 3

    @staticmethod
    def _create_symlink(link_path: Path, target_path: Path):
        """Create a symbolic link."""
        os.symlink(target_path, link_path)

    @staticmethod
    def _create_hardlink(link_path: Path, target_path: Path):
        """Create a hard link for files."""
        os.link(target_path, link_path)

    @staticmethod
    def get_game_path(env_id: int) -> str:
        # TODO: Separate setting up game files from getting the game path
        base_path = os.getenv("SILKSONG_PATH")
        if not base_path:
            raise ValueError("SILKSONG_PATH environment variable is not set")

        base_path = Path(base_path)
        base_dir = base_path.parent
        exe_name = base_path.name
        data_folder_name = base_path.stem + "_Data"
        base_bepinex = base_dir / "BepInEx"

        instance_dir = base_dir / "instances" / str(env_id)
        instance_exe = instance_dir / exe_name
        instance_bepinex = instance_dir / "BepInEx"

        if instance_exe.exists():
            return str(instance_exe)

        instance_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(base_path, instance_exe)

        folders_to_link = [
            data_folder_name,
            "MonoBleedingEdge",
        ]

        for folder in folders_to_link:
            src = base_dir / folder
            dst = instance_dir / folder
            if src.exists() and not dst.exists():
                SilkSongSharedMemory._create_symlink(dst, src)

        files_to_link = [
            "UnityPlayer.so",
        ]

        for filename in files_to_link:
            src = base_dir / filename
            dst = instance_dir / filename
            if src.exists() and not dst.exists():
                SilkSongSharedMemory._create_hardlink(dst, src)

        files_to_copy = [
            "libdoorstop.so",
            "doorstop_config.ini",
            ".doorstop_version",
        ]

        for filename in files_to_copy:
            src = base_dir / filename
            dst = instance_dir / filename
            if src.exists() and not dst.exists():
                shutil.copy2(src, dst)

        if base_bepinex.exists():
            instance_bepinex.mkdir(parents=True, exist_ok=True)

            preloader_src = base_bepinex / "BepInEx.Preloader.dll"
            if preloader_src.exists():
                shutil.copy2(preloader_src, instance_bepinex / "BepInEx.Preloader.dll")

            for folder in ["core", "plugins", "patchers"]:
                src = base_bepinex / folder
                dst = instance_bepinex / folder
                if src.exists() and not dst.exists():
                    SilkSongSharedMemory._create_symlink(dst, src)

            config_src = base_bepinex / "config"
            config_dst = instance_bepinex / "config"
            if config_src.exists() and not config_dst.exists():
                shutil.copytree(config_src, config_dst)

            (instance_bepinex / "cache").mkdir(exist_ok=True)

        print(f"[Env {env_id}] Created instance folder")
        return str(instance_exe)

    def __init__(
        self,
        boss: str,
        id: int,
        time_scale: float = 1.0,
        no_fx: bool = False,
        player_has_clawline: bool = True,
        player_has_cling_grip: bool = True,
        player_has_dash: bool = True,
        player_has_double_jump: bool = True,
        player_has_drifters_cloak: bool = True,
        player_has_needle_strike: bool = True,
        player_has_silkspear: bool = True,
        player_hunter_crest_version: int = 3,
        player_max_health: int = 9,
        player_max_silk: int = 18,
        player_needle_upgrades: int = 4,
        player_silk_hearts: int = 3,
        timeout_ms: int | None = None,
    ):
        self.boss = boss
        self.id = id
        self.time_scale = time_scale
        self.no_fx = no_fx
        self.player_has_clawline = player_has_clawline
        self.player_has_cling_grip = player_has_cling_grip
        self.player_has_dash = player_has_dash
        self.player_has_double_jump = player_has_double_jump
        self.player_has_drifters_cloak = player_has_drifters_cloak
        self.player_has_needle_strike = player_has_needle_strike
        self.player_has_silkspear = player_has_silkspear
        self.player_hunter_crest_version = player_hunter_crest_version
        self.player_max_health = player_max_health
        self.player_max_silk = player_max_silk
        self.player_needle_upgrades = player_needle_upgrades
        self.player_silk_hearts = player_silk_hearts
        self.process = None
        self.timeout_ms = (
            timeout_ms if timeout_ms is not None else self.DEFAULT_TIMEOUT_MS
        )

        if id < 1:
            raise ValueError(f"Invalid environment ID: {id}. Must be >= 1.")

        shm_name = f"{self.MEMORY_NAME}_{id}"

        try:
            self.shm = shared_memory.SharedMemory(
                name=shm_name,
                create=True,
                size=self.MEMORY_SIZE,
            )
        except FileExistsError:
            # Left behind by a run that was killed before it could clean up.
            print(f"Removing stale shared memory: {shm_name}")
            stale = shared_memory.SharedMemory(name=shm_name)
            stale.close()
            stale.unlink()
            self.shm = shared_memory.SharedMemory(
                name=shm_name,
                create=True,
                size=self.MEMORY_SIZE,
            )
        self.shm.buf[:] = bytes(self.MEMORY_SIZE)  # type: ignore
        logging.info(f"Created shared memory: {shm_name}")

        # Doorbells: named pipes that carry wake-up bytes, so each side can block until the
        # other has written to shared memory instead of polling. The game opens them by
        # deriving the same paths from its instance ID.
        self.command_doorbell_path = Path("/dev/shm") / f"{shm_name}_to_game"
        self.state_doorbell_path = Path("/dev/shm") / f"{shm_name}_to_py"
        self.command_doorbell_fd = self._create_doorbell(self.command_doorbell_path)
        self.state_doorbell_fd = self._create_doorbell(self.state_doorbell_path)

        # Register before launching, so an interrupt during startup still cleans up.
        _active_instances.append(self)
        self._start_game()

    @staticmethod
    def _create_doorbell(path: Path) -> int:
        path.unlink(missing_ok=True)
        os.mkfifo(path)
        # O_RDWR keeps the open from blocking until the game connects, and means reads
        # never see EOF if the game exits.
        return os.open(path, os.O_RDWR | os.O_NONBLOCK)

    def _ring_command_doorbell(self):
        try:
            os.write(self.command_doorbell_fd, b"\x01")
        except BlockingIOError:
            # Pipe is full, so the game already has wake-ups pending.
            pass

    def _drain_state_doorbell(self):
        try:
            while os.read(self.state_doorbell_fd, 4096):
                pass
        except BlockingIOError:
            pass

    def read_state(self) -> StateType:
        return struct.unpack_from("i", self.shm.buf, offset=self.STATE_OFFSET)[0]  # type: ignore

    def read_game_state(self) -> GameState:
        data = struct.unpack_from(
            self.GAME_STATE_FORMAT, self.shm.buf, offset=self.GAME_STATE_OFFSET  # type: ignore
        )

        raycast_distances = np.array(data[28:60], dtype=np.float32)
        raycast_hit_types = np.array(data[60:92], dtype=np.float32)

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
            player_can_clawline=bool(data[14]),
            boss_pos_x=data[15],
            boss_pos_y=data[16],
            boss_vel_x=data[17],
            boss_vel_y=data[18],
            boss_health=data[19],
            boss_max_health=data[20],
            boss_phase=data[21],
            boss_animation_state=data[22],
            boss_animation_progress=data[23],
            boss_facing_right=bool(data[24]),
            episode_time=data[25],
            terminated=bool(data[26]),
            truncated=bool(data[27]),
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
        self._ring_command_doorbell()

    def wait_for_state(self, state_type: StateType, timeout_ms: int | None = None):
        if timeout_ms is None:
            timeout_ms = self.timeout_ms

        deadline_s = time.perf_counter() + timeout_ms / 1000.0

        while True:
            # The doorbell only wakes us up; the state in shared memory is authoritative,
            # so stale or extra rings just cause another check.
            current_state = self.read_state()
            if current_state == state_type:
                struct.pack_into(
                    "i", self.shm.buf, self.STATE_OFFSET, int(StateType.READY)  # type: ignore
                )
                break

            remaining_s = deadline_s - time.perf_counter()
            if remaining_s <= 0:
                raise GameTimeoutError(
                    f"Game did not respond within {timeout_ms}ms. "
                    f"Expected state: {state_type.name}, current state: {StateType(current_state).name}"
                )

            select.select([self.state_doorbell_fd], [], [], remaining_s)
            self._drain_state_doorbell()

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

        self._stop_game()

        self.shm.buf[:] = bytes(self.MEMORY_SIZE)  # type: ignore
        self._start_game()

    def _stop_game(self):
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

    def _start_game(self):
        game_path = self.get_game_path(self.id)
        args = [
            game_path,
            "--boss",
            self.boss,
            "--id",
            str(self.id),
            "--time-scale",
            str(self.time_scale),
        ]
        if self.no_fx:
            args.append("--no-fx")
        args.extend(
            ["--player-has-clawline", "true" if self.player_has_clawline else "false"]
        )
        args.extend(
            [
                "--player-has-cling-grip",
                "true" if self.player_has_cling_grip else "false",
            ]
        )
        args.extend(["--player-has-dash", "true" if self.player_has_dash else "false"])
        args.extend(
            [
                "--player-has-double-jump",
                "true" if self.player_has_double_jump else "false",
            ]
        )
        args.extend(
            [
                "--player-has-drifters-cloak",
                "true" if self.player_has_drifters_cloak else "false",
            ]
        )
        args.extend(
            [
                "--player-has-needle-strike",
                "true" if self.player_has_needle_strike else "false",
            ]
        )
        args.extend(
            ["--player-has-silkspear", "true" if self.player_has_silkspear else "false"]
        )
        args.extend(
            ["--player-hunter-crest-version", str(self.player_hunter_crest_version)]
        )
        args.extend(["--player-max-health", str(self.player_max_health)])
        args.extend(["--player-max-silk", str(self.player_max_silk)])
        args.extend(["--player-needle-upgrades", str(self.player_needle_upgrades)])
        args.extend(["--player-silk-hearts", str(self.player_silk_hearts)])

        print(f"Launching game from: {game_path}")

        env = os.environ.copy()
        game_dir = Path(game_path).parent
        env["LD_PRELOAD"] = "./libdoorstop.so"
        env["LD_LIBRARY_PATH"] = f".:{env.get('LD_LIBRARY_PATH', '')}"
        env["DOORSTOP_ENABLED"] = "1"
        env["DOORSTOP_TARGET_ASSEMBLY"] = str(
            game_dir / "BepInEx" / "core" / "BepInEx.Preloader.dll"
        )
        env["__GL_SYNC_TO_VBLANK"] = "0"
        env["vblank_mode"] = "0"

        for attempt in range(1, self.LAUNCH_ATTEMPTS + 1):
            # Keep the game away from the trainer's terminal. With BepInEx's console
            # enabled, games attached to a terminal either fail to load BepInEx or hang
            # at startup, especially when several start at once.
            with open(game_dir / "game_output.log", "w") as output:
                self.process = subprocess.Popen(
                    args,
                    env=env,
                    cwd=game_dir,
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                )

            print("Waiting for game to connect...")
            try:
                self.wait_for_state(StateType.READY, timeout_ms=60000)
                break
            except GameTimeoutError:
                if attempt == self.LAUNCH_ATTEMPTS:
                    raise
                print(
                    f"Instance {self.id} did not start "
                    f"(attempt {attempt}/{self.LAUNCH_ATTEMPTS}), relaunching..."
                )
                self._stop_game()
        print("Game reconnected!")

    def close(self):
        if self in _active_instances:
            _active_instances.remove(self)

        self._stop_game()

        if hasattr(self, "shm") and self.shm is not None:
            try:
                self.shm.close()
                self.shm.unlink()
            except Exception:
                pass
            self.shm = None

        for fd_attr, path_attr in (
            ("command_doorbell_fd", "command_doorbell_path"),
            ("state_doorbell_fd", "state_doorbell_path"),
        ):
            if getattr(self, fd_attr, None) is not None:
                try:
                    os.close(getattr(self, fd_attr))
                    getattr(self, path_attr).unlink(missing_ok=True)
                except Exception:
                    pass
                setattr(self, fd_attr, None)
