from collections import defaultdict
from typing import Optional
import gymnasium as gym
from gymnasium import spaces
import numpy as np
from numpy.typing import NDArray
from stable_baselines3.common.monitor import Monitor
from silk_tron.bosses import BOSSES
from silk_tron.handicaps import HandicapConfig
from silk_tron.constants import (
    BOSS_MAX_PHASE,
    HERO_VEL_X_RANGE,
    HERO_VEL_Y_RANGE,
    MAX_EPISODE_STEPS,
    NUM_BOSS_ANIMATION_STATES,
    NUM_PLAYER_ANIMATION_STATES,
    OBSERVATION_DIM,
    PLAYER_MAX_HEALTH,
    PLAYER_MAX_SILK,
)
from silk_tron.shared_memory import GameState, GameTimeoutError, SilkSongSharedMemory


def min_max_normalize(value: float, min_value: float, max_value: float) -> float:
    value = (value - min_value) / (max_value - min_value)
    value = np.clip(value, 0.0, 1.0)
    return value


class SilksongBossEnv(gym.Env[NDArray[np.float32], NDArray[np.integer]]):
    def __init__(
        self,
        boss: str,
        id: int = 1,
        time_scale: float = 1.0,
        no_fx: bool = False,
        boss_damage_coef: float = 1.0,
        boss_defeat_coef: float = 0.0,
        player_damage_coef: float = 0.1,
        too_far_coef: float = 0.001,
        too_far_threshold: float = 15.0,
        too_close_coef: float = 0.001,
        too_close_threshold: float = 1.0,
        time_penalty_coef: float = 0.0001,
        silk_coef: float = 0.0,
        handicaps: HandicapConfig | None = None,
    ):
        super().__init__()

        if handicaps is None:
            handicaps = HandicapConfig()

        self.boss = BOSSES[boss]
        self.arena_width = self.boss.arena_max_x - self.boss.arena_min_x
        self.arena_height = self.boss.arena_max_y - self.boss.arena_min_y
        self.max_distance = np.sqrt(self.arena_width**2 + self.arena_height**2)

        # Reward coefficients and thresholds
        self.boss_damage_coef = boss_damage_coef
        self.boss_defeat_coef = boss_defeat_coef
        self.player_damage_coef = player_damage_coef
        self.too_far_coef = too_far_coef
        self.too_far_threshold = too_far_threshold
        self.too_close_coef = too_close_coef
        self.too_close_threshold = too_close_threshold
        self.time_penalty_coef = time_penalty_coef
        self.silk_coef = silk_coef
        self.handicaps = handicaps

        self.action_space = spaces.MultiDiscrete([3, 3, 2, 2, 2, 2, 2, 2])
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(OBSERVATION_DIM,), dtype=np.float32
        )

        self.action_names = [
            "left",
            "right",
            "up",
            "down",
            "jump",
            "attack",
            "dash",
            "clawline",
            "skill",
            "heal",
        ]

        self.shm = SilkSongSharedMemory(
            boss,
            id,
            time_scale=time_scale,
            no_fx=no_fx,
            player_has_clawline=handicaps.has_clawline,
            player_has_dash=handicaps.has_dash,
            player_has_silkspear=handicaps.has_silkspear,
        )

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)

        try:
            game_state = self.shm.reset()  # type: ignore
        except GameTimeoutError as e:
            print(f"Reset timeout: {e}")
            self.shm.restart()  # type: ignore
            game_state = self.shm.reset()  # type: ignore

        self.game_state = game_state
        self.prev_boss_health = game_state.boss_health
        self.prev_player_health = game_state.player_health
        self.prev_player_silk = game_state.player_silk
        self.total_steps = 0

        self.attack_count = 0
        self.heal_count = 0
        self.hurt_count = 0
        self.episode_reward = 0.0
        self.lowest_boss_hp = game_state.boss_health
        self.prev_attack = 0

        # Action tracking
        self.action_counts = {name: 0 for name in self.action_names}

        observation = self._make_observation(game_state)
        reward, reward_components = self._default_reward()
        info = self._get_info(game_state, reward_components)

        return observation, info

    def step(self, action):
        # Track actions
        self._track_actions(action)

        binary_action = self._convert_to_binary(action)

        try:
            game_state = self.shm.step(binary_action)  # type: ignore
        except GameTimeoutError as e:
            print(f"[Env] {e}")
            return self._handle_timeout()

        self.game_state = game_state
        self.total_steps += 1

        boss_dmg = self.prev_boss_health - game_state.boss_health
        if boss_dmg > 0:
            self.attack_count += 1

        player_dmg = self.prev_player_health - game_state.player_health
        if player_dmg > 0:
            self.hurt_count += 1

        reward, reward_components = self._calculate_reward(game_state)

        self.episode_reward += reward
        self.lowest_boss_hp = min(self.lowest_boss_hp, game_state.boss_health)

        observation = self._make_observation(game_state)

        terminated = self._is_terminated(game_state)
        truncated = self._is_truncated(game_state)

        self.prev_boss_health = game_state.boss_health
        self.prev_player_health = game_state.player_health
        self.prev_player_silk = game_state.player_silk

        info = self._get_info(game_state, reward_components, terminated or truncated)

        return observation, reward, terminated, truncated, info

    def _handle_timeout(self):
        self.shm.restart()  # type: ignore

        game_state = self.shm.reset()  # type: ignore

        self.game_state = game_state
        self.prev_boss_health = game_state.boss_health
        self.prev_player_health = game_state.player_health
        self.prev_player_silk = game_state.player_silk

        observation = self._make_observation(game_state)
        reward, reward_components = self._calculate_reward(game_state)
        info = self._get_info(game_state, reward_components, episode_end=True)
        info["timeout_restart"] = True

        return observation, 0.0, False, True, info

    def _calculate_reward(
        self, game_state: GameState
    ) -> tuple[float, dict[str, float]]:
        components = {}

        boss_dmg = self.prev_boss_health - game_state.boss_health
        components["boss_damage"] = (
            boss_dmg / self.boss.max_hp
        ) * self.boss_damage_coef

        components["boss_defeat"] = (
            self.boss_defeat_coef
            if (self.prev_boss_health > 0 and game_state.boss_health <= 0)
            else 0.0
        )

        player_dmg = self.prev_player_health - game_state.player_health
        components["player_damage"] = (
            -(player_dmg / PLAYER_MAX_HEALTH) * self.player_damage_coef
        )

        silk_delta = game_state.player_silk - self.prev_player_silk
        components["silk"] = (silk_delta / PLAYER_MAX_SILK) * self.silk_coef

        distance = np.sqrt(
            (game_state.player_pos_x - game_state.boss_pos_x) ** 2
            + (game_state.player_pos_y - game_state.boss_pos_y) ** 2
        )

        too_far = distance > self.too_far_threshold
        too_close = distance < self.too_close_threshold

        components["too_far"] = -self.too_far_coef if too_far else 0.0
        components["too_close"] = -self.too_close_coef if too_close else 0.0

        components["time_penalty"] = -self.time_penalty_coef

        reward = sum(c for c in components.values())

        return reward, components

    def _default_reward(self):
        reward = 0.0
        components = None
        return reward, components

    def _make_observation(self, game_state: GameState) -> np.ndarray:
        player_x = min_max_normalize(
            game_state.player_pos_x, self.boss.arena_min_x, self.boss.arena_max_x
        )
        player_y = min_max_normalize(
            game_state.player_pos_y, self.boss.arena_min_y, self.boss.arena_max_y
        )

        player_vel_x = min_max_normalize(
            game_state.player_vel_x, HERO_VEL_X_RANGE[0], HERO_VEL_X_RANGE[1]
        )
        player_vel_y = min_max_normalize(
            game_state.player_vel_y, HERO_VEL_Y_RANGE[0], HERO_VEL_Y_RANGE[1]
        )

        player_health = game_state.player_health / PLAYER_MAX_HEALTH
        player_silk = game_state.player_silk / PLAYER_MAX_SILK
        player_grounded = float(game_state.player_grounded)
        player_can_dash = float(game_state.player_can_dash)
        player_facing_right = float(game_state.player_facing_right)
        player_invincible = float(game_state.player_invincible)
        player_can_attack = float(game_state.player_can_attack)
        boss_x = min_max_normalize(
            game_state.boss_pos_x, self.boss.arena_min_x, self.boss.arena_max_x
        )
        boss_y = min_max_normalize(
            game_state.boss_pos_y, self.boss.arena_min_y, self.boss.arena_max_y
        )

        boss_vel_x = min_max_normalize(
            game_state.boss_vel_x, self.boss.vel_x_range[0], self.boss.vel_x_range[1]
        )
        boss_vel_y = min_max_normalize(
            game_state.boss_vel_y, self.boss.vel_y_range[0], self.boss.vel_y_range[1]
        )

        boss_health = game_state.boss_health / self.boss.max_hp

        boss_phase = game_state.boss_phase / BOSS_MAX_PHASE
        boss_facing_right = float(game_state.boss_facing_right)

        rel_x = min_max_normalize(
            (game_state.boss_pos_x - game_state.player_pos_x),
            -self.arena_width,
            self.arena_width,
        )

        rel_y = min_max_normalize(
            (game_state.boss_pos_y - game_state.player_pos_y),
            -self.arena_height,
            self.arena_height,
        )

        distance = (
            np.sqrt(
                (game_state.boss_pos_x - game_state.player_pos_x) ** 2
                + (game_state.boss_pos_y - game_state.player_pos_y) ** 2
            )
            / self.max_distance
        )
        distance = np.clip(distance, 0.0, 1.0)

        boss_anim_state = float(
            np.clip(game_state.boss_animation_state, 0, NUM_BOSS_ANIMATION_STATES - 1)
        )
        boss_anim_progress = np.clip(game_state.boss_animation_progress, 0.0, 1.0)

        player_anim_state = float(
            np.clip(
                game_state.player_animation_state, 0, NUM_PLAYER_ANIMATION_STATES - 1
            )
        )
        player_anim_progress = np.clip(game_state.player_animation_progress, 0.0, 1.0)

        state_obs = np.array(
            [
                player_x,
                player_y,
                player_vel_x,
                player_vel_y,
                player_health,
                player_silk,
                player_grounded,
                player_can_dash,
                player_facing_right,
                player_invincible,
                player_can_attack,
                boss_x,
                boss_y,
                boss_vel_x,
                boss_vel_y,
                boss_health,
                boss_phase,
                boss_facing_right,
                rel_x,
                rel_y,
                distance,
                boss_anim_state,
                boss_anim_progress,
                player_anim_state,
                player_anim_progress,
            ],
            dtype=np.float32,
        )

        raycast_obs = np.concatenate(
            [game_state.raycast_distances, game_state.raycast_hit_types]
        )

        observe = np.concatenate([state_obs, raycast_obs.astype(np.float32)])
        return observe

    def _is_terminated(self, game_state: GameState) -> bool:
        return game_state.boss_health <= 0 or game_state.player_health <= 0

    def _is_truncated(self, game_state: GameState) -> bool:
        if self.total_steps >= MAX_EPISODE_STEPS:
            return True
        return game_state.truncated

    def _is_success(self, game_state: GameState) -> bool:
        return game_state.boss_health <= 0 and game_state.player_health > 0

    def _get_info(
        self,
        game_state: GameState,
        reward_components: dict[str, float] | None,
        episode_end: bool = False,
    ) -> dict:
        info = {
            "player_health": game_state.player_health,
            "boss_health": game_state.boss_health,
            "player_silk": game_state.player_silk,
            "episode_time": game_state.episode_time,
            "total_steps": self.total_steps,
            "player_pos": (game_state.player_pos_x, game_state.player_pos_y),
            "boss_pos": (game_state.boss_pos_x, game_state.boss_pos_y),
            "reward": reward_components,
        }

        if episode_end:
            info["episode_reward"] = self.episode_reward
            info["lowest_boss_hp"] = self.lowest_boss_hp
            info["attack_count"] = self.attack_count
            info["heal_count"] = self.heal_count
            info["hurt_count"] = self.hurt_count
            info["action_counts"] = self.action_counts.copy()
            info["success"] = self._is_success(game_state)

        return info

    def _convert_to_binary(self, action: np.ndarray) -> np.ndarray:
        binary = np.zeros(10, dtype=np.int8)

        if action[0] == 1:  # left
            binary[0] = 1
        elif action[0] == 2:  # right
            binary[1] = 1

        if action[1] == 1:  # up
            binary[2] = 1
        elif action[1] == 2:  # down
            binary[3] = 1

        binary[4] = action[2]  # jump

        binary[5] = action[3]  # attack

        if self.prev_attack == 1:
            binary[5] = 0
        else:
            binary[5] = action[3]
        self.prev_attack = binary[5]

        binary[6] = action[4]  # dash
        binary[7] = action[5]  # clawline
        binary[8] = action[6]  # skill
        binary[9] = action[7]  # heal

        return binary

    def _track_actions(self, action: np.ndarray) -> None:
        """Track action statistics for logging."""
        # Track horizontal movement (left/right)
        if action[0] == 1:  # left
            self.action_counts["left"] += 1
        elif action[0] == 2:  # right
            self.action_counts["right"] += 1

        # Track vertical movement (up/down)
        if action[1] == 1:  # up
            self.action_counts["up"] += 1
        elif action[1] == 2:  # down
            self.action_counts["down"] += 1

        # Track other actions (jump, attack, dash, clawline, skill, heal)
        if action[2] != 0:
            self.action_counts["jump"] += 1
        if action[3] != 0:
            self.action_counts["attack"] += 1
        if action[4] != 0:
            self.action_counts["dash"] += 1
        if action[5] != 0:
            self.action_counts["clawline"] += 1
        if action[6] != 0:
            self.action_counts["skill"] += 1
        if action[7] != 0:
            self.action_counts["heal"] += 1

    def action_masks(self) -> np.ndarray:
        """Return action masks for MaskablePPO.

        Returns a 1D boolean array indicating valid actions for MultiDiscrete space.
        For MultiDiscrete([3, 3, 2, 2, 2, 2, 2, 2]), returns array of length 18 (sum of dims).
        The mask is flattened: [horiz_0, horiz_1, horiz_2, vert_0, vert_1, vert_2, jump_0, jump_1, ...]
        """
        # Create flattened mask for MultiDiscrete space
        mask = np.ones(sum(self.action_space.nvec), dtype=bool)  # type: ignore

        # Movement (horizontal index 0-2 and vertical index 3-5) always allowed

        # Jump: indices 6-7 (no jump=6, jump=7) always allowed, because the player can hold it to jump higher

        # Attack: indices 8-9 (no attack=8, attack=9) always allowed for now

        # Dash: indices 10-11 (no dash=10, dash=11)
        if not self.handicaps.has_dash:
            mask[11] = False  # Dash disabled by handicap

        # Clawline: indices 12-13 (no clawline=12, clawline=13)
        if not self.handicaps.has_clawline:
            mask[13] = False  # Clawline disabled by handicap

        # Skill: indices 14-15 (no skill=14, skill=15)
        if not self.handicaps.has_silkspear:
            mask[15] = False  # Silkspear disabled by handicap

        # Heal: indices 16-17 (always allowed for now)

        return mask

    def close(self):
        if hasattr(self, "shm") and self.shm is not None:
            self.shm.close()
            self.shm = None


class MyMonitor(Monitor):
    def __init__(
        self,
        env: gym.Env,
        filename: Optional[str] = None,
        allow_early_resets: bool = True,
        reset_keywords: tuple[str, ...] = (),
        info_keywords: tuple[str, ...] = (),
        override_existing: bool = True,
    ):
        super().__init__(
            env=env,
            filename=filename,
            allow_early_resets=allow_early_resets,
            reset_keywords=reset_keywords,
            info_keywords=info_keywords,
            override_existing=override_existing,
        )
        self.reward_components = defaultdict(list)

    def reset(self, **kwargs):
        self.reward_components = defaultdict(list)
        return super().reset(**kwargs)

    def step(self, action):
        observation, reward, terminated, truncated, info = super().step(action)
        if (reward_components := info.get("reward")) is not None:
            for name, val in reward_components.items():
                self.reward_components[name].append(val)
        if (terminated or truncated) and ((ep_info := info.get("episode")) is not None):
            ep_info["reward_components"] = {
                name: sum(vals) for name, vals in self.reward_components.items()
            }
        return observation, reward, terminated, truncated, info


class DummySilksongBossEnv(gym.Env):
    """A deterministic dummy environment for testing reproducibility."""

    MAX_X = 4
    MAX_Y = 4

    def __init__(self):
        super().__init__()

        self.action_space = spaces.MultiDiscrete([3, 3, 2, 2, 2, 2, 2, 2])
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(OBSERVATION_DIM,), dtype=np.float32
        )

    def reset(self, seed=None, options=None):
        self.player_x = 0
        self.player_y = 0
        self.boss_state = 0
        self.boss_x = 0
        self.boss_y = 0
        observation = self._get_observation()
        info = {}
        return observation, info

    def step(self, action: NDArray[np.integer]):
        if action[0] == 1:  # left
            self.player_x = max(0, self.player_x - 1)
        elif action[0] == 2:  # right
            self.player_x = min(self.MAX_X, self.player_x + 1)

        if action[1] == 1:  # up
            self.player_y = max(0, self.player_y - 1)
        elif action[1] == 2:  # down
            self.player_y = min(self.MAX_Y, self.player_y + 1)

        self.boss_state = (self.boss_state + 1) % 15

        boss_move_x = self.boss_state % 3  # stay, left, right 33% of the time
        if boss_move_x == 1:  # left
            self.boss_x = max(0, self.boss_x - 1)
        elif boss_move_x == 2:  # right
            self.boss_x = min(self.MAX_X, self.boss_x + 1)

        boss_move_y = 2 - (self.boss_state % 5) // 2  # stay 20%, left/right 40%
        if boss_move_y == 1:  # up
            self.boss_y = max(0, self.boss_y - 1)
        elif boss_move_y == 2:  # down
            self.boss_y = min(self.MAX_Y, self.boss_y + 1)

        observation = self._get_observation()

        player_boss_collision = (
            self.player_x == self.boss_x and self.player_y == self.boss_y
        )
        reward = -1 if player_boss_collision else 0.1

        terminated = False
        truncated = False
        info = {}

        return observation, reward, terminated, truncated, info

    def _get_observation(self):
        player_x = self.player_x / self.MAX_X
        player_y = self.player_y / self.MAX_Y
        boss_x = (self.boss_x - self.player_x) / self.MAX_X
        boss_y = (self.boss_y - self.player_y) / self.MAX_Y
        return np.array(
            [player_x, player_y] + [0.0] * 9 + [boss_x, boss_y] + [0.0] * 76
        )

    def action_masks(self) -> np.ndarray:
        """Return action masks for MaskablePPO. All actions allowed in dummy env.

        Returns a 1D boolean array of length 18 (sum of MultiDiscrete([3,3,2,2,2,2,2,2])).
        """
        return np.ones(18, dtype=bool)
