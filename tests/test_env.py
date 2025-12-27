"""Tests for DummySilksongBossEnv to verify deterministic behavior."""

import numpy as np
import pytest

from silk_tron.env import DummySilksongBossEnv
from silk_tron.constants import OBSERVATION_DIM


class TestDummySilksongBossEnv:
    """Test suite for DummySilksongBossEnv determinism."""

    def test_reset_is_deterministic(self):
        """Test that reset() produces the same initial state."""
        env1 = DummySilksongBossEnv()
        env2 = DummySilksongBossEnv()

        obs1, info1 = env1.reset()
        obs2, info2 = env2.reset()

        np.testing.assert_array_equal(obs1, obs2)
        assert info1 == info2

    def test_deterministic_sequence(self):
        """Test that the same action sequence produces identical results."""
        # Create two environments
        env1 = DummySilksongBossEnv()
        env2 = DummySilksongBossEnv()

        env1.reset()
        env2.reset()

        # Create a sequence of random-looking but deterministic actions
        action_sequence = [
            np.array([1, 0, 0, 0, 0, 0, 0, 0]),  # move left
            np.array([2, 0, 0, 0, 0, 0, 0, 0]),  # move right
            np.array([0, 1, 0, 0, 0, 0, 0, 0]),  # move up
            np.array([0, 2, 0, 0, 0, 0, 0, 0]),  # move down
            np.array([2, 2, 1, 1, 0, 0, 0, 0]),  # move right-down, jump, attack
            np.array([1, 1, 0, 0, 1, 0, 0, 0]),  # move left-up, dash
            np.array([0, 0, 0, 0, 0, 1, 1, 1]),  # clawline, skill, heal
        ]

        # Run both environments with the same actions
        for action in action_sequence:
            obs1, reward1, term1, trunc1, info1 = env1.step(action)
            obs2, reward2, term2, trunc2, info2 = env2.step(action)

            np.testing.assert_array_equal(obs1, obs2)
            assert reward1 == reward2
            assert term1 == term2
            assert trunc1 == trunc2
            assert info1 == info2

    def test_player_movement(self):
        """Test that player movement actions work correctly."""
        env = DummySilksongBossEnv()
        env.reset()

        # Move right
        action = np.array([2, 0, 0, 0, 0, 0, 0, 0])
        env.step(action)
        assert env.player_x == 1
        assert env.player_y == 0

        # Move right again
        env.step(action)
        assert env.player_x == 2

        # Move down
        action = np.array([0, 2, 0, 0, 0, 0, 0, 0])
        env.step(action)
        assert env.player_x == 2
        assert env.player_y == 1

        # Move left
        action = np.array([1, 0, 0, 0, 0, 0, 0, 0])
        env.step(action)
        assert env.player_x == 1
        assert env.player_y == 1

        # Move up
        action = np.array([0, 1, 0, 0, 0, 0, 0, 0])
        env.step(action)
        assert env.player_x == 1
        assert env.player_y == 0

    def test_player_boundary_limits(self):
        """Test that player cannot move beyond boundaries."""
        env = DummySilksongBossEnv()
        env.reset()

        # Try to move left from origin (should stay at 0)
        action = np.array([1, 0, 0, 0, 0, 0, 0, 0])
        env.step(action)
        assert env.player_x == 0

        # Try to move up from origin (should stay at 0)
        action = np.array([0, 1, 0, 0, 0, 0, 0, 0])
        env.step(action)
        assert env.player_y == 0

        # Move to max x
        for _ in range(env.MAX_X + 5):  # Try to move beyond max
            action = np.array([2, 0, 0, 0, 0, 0, 0, 0])
            env.step(action)
        assert env.player_x == env.MAX_X

        # Reset and move to max y
        env.reset()
        for _ in range(env.MAX_Y + 5):  # Try to move beyond max
            action = np.array([0, 2, 0, 0, 0, 0, 0, 0])
            env.step(action)
        assert env.player_y == env.MAX_Y

    def test_reset_after_steps(self):
        """Test that reset() properly resets the environment after steps."""
        env = DummySilksongBossEnv()
        env.reset()

        # Take some random actions
        for _ in range(20):
            action = np.array([2, 2, 1, 1, 1, 1, 1, 1])
            env.step(action)

        # Reset and verify initial state is restored
        obs, info = env.reset()

        assert env.player_x == 0
        assert env.player_y == 0
        assert env.boss_x == 0
        assert env.boss_y == 0
        assert env.boss_state == 0
