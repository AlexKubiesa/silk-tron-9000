"""Tests for the step-based learning rate and entropy coefficient schedules."""

from types import SimpleNamespace

import pytest

from silk_tron.networks import (
    EntropyCoefScheduleCallback,
    LearningRateScheduleCallback,
    linear_decay,
)


class FakeLogger:
    def __init__(self):
        self.recorded = {}

    def record(self, key, value):
        self.recorded[key] = value


def test_linear_decay_endpoints_and_midpoint():
    assert linear_decay(4e-4, 4e-5, 1000, 0) == pytest.approx(4e-4)
    assert linear_decay(4e-4, 4e-5, 1000, 500) == pytest.approx(2.2e-4)
    assert linear_decay(4e-4, 4e-5, 1000, 1000) == pytest.approx(4e-5)


def test_linear_decay_holds_final_value_after_decay_steps():
    assert linear_decay(4e-4, 4e-5, 1000, 5000) == pytest.approx(4e-5)


def test_linear_decay_can_increase():
    assert linear_decay(0.001, 0.01, 100, 50) == pytest.approx(0.0055)


def test_learning_rate_callback_sets_schedule_from_num_timesteps():
    callback = LearningRateScheduleCallback(4e-4, 4e-5, decay_steps=1000)
    callback.model = SimpleNamespace(num_timesteps=500, lr_schedule=None)
    callback._on_rollout_end()
    # SB3 calls the schedule with the training progress, which must not matter.
    assert callback.model.lr_schedule(1.0) == pytest.approx(2.2e-4)
    assert callback.model.lr_schedule(0.0) == pytest.approx(2.2e-4)


def test_learning_rate_callback_is_independent_of_total_timesteps():
    # The same timestep gives the same value, whatever progress SB3 reports.
    for progress_remaining in (0.9, 0.5, 0.1):
        callback = LearningRateScheduleCallback(4e-4, 4e-5, decay_steps=3_000_000)
        callback.model = SimpleNamespace(
            num_timesteps=1_000_000,
            lr_schedule=None,
            _current_progress_remaining=progress_remaining,
        )
        callback._on_rollout_end()
        assert callback.model.lr_schedule(progress_remaining) == pytest.approx(2.8e-4)


def entropy_callback(decay_steps, num_timesteps, progress_remaining):
    callback = EntropyCoefScheduleCallback(0.01, 0.001, decay_steps=decay_steps)
    callback.model = SimpleNamespace(
        num_timesteps=num_timesteps,
        ent_coef=0.01,
        _current_progress_remaining=progress_remaining,
        logger=FakeLogger(),
    )
    callback._on_rollout_start()
    return callback


def test_entropy_callback_with_decay_steps_uses_timesteps():
    callback = entropy_callback(decay_steps=1000, num_timesteps=500, progress_remaining=0.1)
    assert callback.model.ent_coef == pytest.approx(0.0055)
    assert callback.logger.recorded["train/ent_coef"] == pytest.approx(0.0055)


def test_entropy_callback_holds_final_value_past_decay_steps():
    callback = entropy_callback(decay_steps=1000, num_timesteps=4000, progress_remaining=0.0)
    assert callback.model.ent_coef == pytest.approx(0.001)


def test_entropy_callback_without_decay_steps_uses_progress():
    callback = entropy_callback(decay_steps=None, num_timesteps=500, progress_remaining=0.25)
    assert callback.model.ent_coef == pytest.approx(0.001 + 0.009 * 0.25)
