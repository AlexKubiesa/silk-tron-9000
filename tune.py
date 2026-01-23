import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import yaml
import optuna
from optuna.pruners import MedianPruner
from optuna.samplers import TPESampler
import torch
import torch.nn as nn
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import EvalCallback, BaseCallback
from stable_baselines3.common.vec_env import VecNormalize, VecEnv
import gymnasium as gym

from train import make_vec_env, reset_env_id_counter
from silk_tron.networks import MultiHeadFeatureExtractor
from silk_tron.handicaps import HandicapConfig


def load_config(config_path: str) -> dict:
    """Load hyperparameters from YAML config file."""
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config


def _build_fixed_params(config: Dict[str, Any]) -> Dict[str, Any]:
    required_keys = [
        "learning_rate",
        "n_steps",
        "batch_size",
        "n_epochs",
        "gamma",
        "gae_lambda",
        "clip_range",
        "ent_coef",
        "vf_coef",
        "max_grad_norm",
        "features_dim",
        "pi_layers",
        "vf_layers",
    ]

    missing = [key for key in required_keys if key not in config]
    if missing:
        missing_str = ", ".join(missing)
        raise ValueError(
            f"Config missing required hyperparameters for tuning: {missing_str}"
        )

    return {
        "learning_rate": config["learning_rate"],
        "n_steps": config["n_steps"],
        "batch_size": config["batch_size"],
        "n_epochs": config["n_epochs"],
        "gamma": config["gamma"],
        "gae_lambda": config["gae_lambda"],
        "clip_range": config["clip_range"],
        "ent_coef": config["ent_coef"],
        "vf_coef": config["vf_coef"],
        "max_grad_norm": config["max_grad_norm"],
        "features_dim": config["features_dim"],
        "pi_layers": config["pi_layers"],
        "vf_layers": config["vf_layers"],
    }


def _suggest_from_space(
    trial: optuna.Trial, name: str, spec: Dict[str, Any]
) -> Any:
    if not isinstance(spec, dict):
        raise ValueError(f"Search space for {name} must be a dict, got {spec}")

    param_type = spec.get("type")
    if param_type is None:
        raise ValueError(f"Search space for {name} must include a 'type' field")

    if param_type == "float":
        low = spec.get("low")
        high = spec.get("high")
        if low is None or high is None:
            raise ValueError(f"Float space for {name} requires low/high")
        log = bool(spec.get("log", False))
        step = spec.get("step")
        if log and step is not None:
            raise ValueError(f"Float space for {name} cannot use log with step")
        return trial.suggest_float(name, low, high, log=log, step=step)

    if param_type == "int":
        low = spec.get("low")
        high = spec.get("high")
        if low is None or high is None:
            raise ValueError(f"Int space for {name} requires low/high")
        step = spec.get("step", 1)
        log = bool(spec.get("log", False))
        return trial.suggest_int(name, low, high, step=step, log=log)

    if param_type == "categorical":
        choices = spec.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError(f"Categorical space for {name} requires choices list")
        return trial.suggest_categorical(name, choices)

    raise ValueError(f"Unsupported search space type '{param_type}' for {name}")


def get_hyperparameters(
    trial: optuna.Trial,
    search_space: Dict[str, Any],
    fixed_params: Dict[str, Any],
    only_params: list[str] | None = None,
) -> Dict[str, Any]:
    if not search_space:
        raise ValueError("Config tuning.search_space must be defined and non-empty")

    if only_params is not None:
        unknown = [name for name in only_params if name not in search_space]
        if unknown:
            unknown_str = ", ".join(unknown)
            raise ValueError(
                f"Unknown parameter(s) in --only-params: {unknown_str}"
            )
        only_set = set(only_params)
    else:
        only_set = None

    params: Dict[str, Any] = {}
    for name, spec in search_space.items():
        if only_set is not None and name not in only_set:
            if name not in fixed_params:
                raise ValueError(
                    f"No fixed config value available for '{name}' when excluded"
                )
            params[name] = fixed_params[name]
            continue
        params[name] = _suggest_from_space(trial, name, spec)

    return params


class DummyCallback(BaseCallback):
    def _on_step(self) -> bool:
        return True


class TrialEvalCallback(EvalCallback):
    """
    Callback used for evaluating and reporting a trial to Optuna.

    This callback extends EvalCallback to work with Optuna trials,
    allowing for trial pruning and reporting of evaluation results
    to the Optuna study.

    Attributes
    ----------
    trial : optuna.Trial
        The Optuna trial associated with this evaluation.
    eval_idx : int
        Current evaluation index for reporting to Optuna.
    is_pruned : bool
        Whether the trial has been pruned.
    """

    def __init__(
        self,
        eval_env: gym.Env | VecEnv,
        trial: optuna.Trial,
        n_eval_episodes: int = 5,
        eval_freq: int = 10000,
        deterministic: bool = True,
        verbose: int = 0,
        best_model_save_path: Optional[str] = None,
        log_path: Optional[str] = None,
        callback_after_eval: Optional[BaseCallback] = None,
    ) -> None:
        """
        Initialize the TrialEvalCallback.

        Parameters
        ----------
        eval_env : gym.Env
            The environment used for evaluation.
        trial : optuna.Trial
            The Optuna trial for this training run.
        n_eval_episodes : int, optional
            Number of episodes to evaluate (default is 5).
        eval_freq : int, optional
            Evaluate every `eval_freq` timesteps (default is 10000).
        deterministic : bool, optional
            Whether to use deterministic actions during evaluation (default is True).
        verbose : int, optional
            Verbosity level (default is 0).
        best_model_save_path : Optional[str], optional
            Path to save the best model (default is None).
        log_path : Optional[str], optional
            Path to save evaluation logs (default is None).
        callback_after_eval : Optional[BaseCallback], optional
            Additional callback to run after evaluation (default is None).
        """
        super().__init__(
            eval_env=eval_env,
            n_eval_episodes=n_eval_episodes,
            eval_freq=eval_freq,
            deterministic=deterministic,
            verbose=verbose,
            best_model_save_path=best_model_save_path,
            log_path=log_path,
            callback_after_eval=callback_after_eval,
        )
        self.trial = trial
        self.eval_idx = 0
        self.is_pruned = False
        self.all_mean_rewards = []

    def _on_step(self) -> bool:
        """
        Called at each training step to perform evaluation and report to Optuna.

        Returns
        -------
        bool
            True to continue training, False to stop.
        """
        continue_training = True

        # Perform evaluation at specified frequency
        if self.eval_freq > 0 and self.n_calls % self.eval_freq == 0:
            continue_training = super()._on_step()
            self.eval_idx += 1

            # Store the mean reward
            if self.last_mean_reward is not None:
                self.all_mean_rewards.append(self.last_mean_reward)

            # Report the best mean reward to Optuna
            self.trial.report(self.last_mean_reward, self.eval_idx)

            # Prune trial if needed
            if self.trial.should_prune():
                self.is_pruned = True
                return False

        return continue_training

    def get_average_reward(self) -> float:
        """Return average of all mean rewards across evaluations."""
        if not self.all_mean_rewards:
            return float("-inf")
        return sum(self.all_mean_rewards) / len(self.all_mean_rewards)


def objective(
    trial: optuna.Trial,
    boss: str,
    n_envs: int,
    timesteps_per_trial: int,
    eval_freq: int,
    n_eval_episodes: int,
    time_scale: float,
    search_space: Dict[str, Any],
    fixed_params: Dict[str, Any],
    only_params: list[str] | None,
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
) -> float:
    """Optuna objective function."""

    if handicaps is None:
        handicaps = HandicapConfig()

    reset_env_id_counter()
    params = get_hyperparameters(trial, search_space, fixed_params, only_params)

    print(f"\n{'='*60}")
    print(f"Trial {trial.number}")
    print(f"{'='*60}")
    for key, value in params.items():
        print(f"  {key}: {value}")
    print(f"{'='*60}\n")

    env = make_vec_env(
        boss=boss,
        n_envs=n_envs,
        time_scale=time_scale,
        no_fx=True,
        boss_damage_coef=boss_damage_coef,
        boss_defeat_coef=boss_defeat_coef,
        player_damage_coef=player_damage_coef,
        too_far_coef=too_far_coef,
        too_far_threshold=too_far_threshold,
        too_close_coef=too_close_coef,
        too_close_threshold=too_close_threshold,
        time_penalty_coef=time_penalty_coef,
        silk_coef=silk_coef,
        handicaps=handicaps,
    )
    env = VecNormalize(env, norm_obs=False, norm_reward=True)

    eval_env = make_vec_env(
        boss=boss,
        n_envs=1,
        time_scale=time_scale,
        no_fx=True,
        boss_damage_coef=boss_damage_coef,
        boss_defeat_coef=boss_defeat_coef,
        player_damage_coef=player_damage_coef,
        too_far_coef=too_far_coef,
        too_far_threshold=too_far_threshold,
        too_close_coef=too_close_coef,
        too_close_threshold=too_close_threshold,
        time_penalty_coef=time_penalty_coef,
        silk_coef=silk_coef,
        handicaps=handicaps,
    )
    eval_env = VecNormalize(eval_env, norm_obs=False, norm_reward=False, training=False)

    policy_kwargs = dict(
        features_extractor_class=MultiHeadFeatureExtractor,
        features_extractor_kwargs=dict(features_dim=params["features_dim"]),
        net_arch=dict(
            pi=params["pi_layers"],
            vf=params["vf_layers"],
        ),
        activation_fn=nn.ReLU,
    )

    model = MaskablePPO(
        policy="MlpPolicy",
        env=env,
        learning_rate=params["learning_rate"],
        n_steps=params["n_steps"],
        batch_size=params["batch_size"],
        n_epochs=params["n_epochs"],
        gamma=params["gamma"],
        gae_lambda=params["gae_lambda"],
        clip_range=params["clip_range"],
        ent_coef=params["ent_coef"],
        vf_coef=params["vf_coef"],
        max_grad_norm=params["max_grad_norm"],
        verbose=0,
        device="cpu",
        policy_kwargs=policy_kwargs,
    )

    eval_callback = TrialEvalCallback(
        trial=trial,
        eval_env=eval_env,
        n_eval_episodes=n_eval_episodes,
        eval_freq=eval_freq,
        deterministic=True,
        verbose=0,
    )

    try:
        model.learn(
            total_timesteps=timesteps_per_trial,
            callback=eval_callback,
            progress_bar=True,
        )
    except Exception as e:
        print(f"Trial {trial.number} failed: {e}")
        env.close()
        eval_env.close()
        raise optuna.TrialPruned()

    env.close()
    eval_env.close()

    if eval_callback.is_pruned:
        raise optuna.TrialPruned()

    mean_reward = eval_callback.get_average_reward()
    print(f"\nTrial {trial.number} finished with average reward: {mean_reward:.4f}")

    return mean_reward


def tune(
    boss: str,
    n_trials: int = 30,
    n_envs: int = 1,
    timesteps_per_trial: int = 300_000,
    eval_freq: int = 50_000,
    n_eval_episodes: int = 10,
    time_scale: float = 4.0,
    search_space: Dict[str, Any] | None = None,
    fixed_params: Dict[str, Any] | None = None,
    only_params: list[str] | None = None,
    study_name: str = "silksong",
    storage: str | None = None,
    output_dir: str = "./hyperparameters",
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
    if handicaps is None:
        handicaps = HandicapConfig()

    if search_space is None:
        raise ValueError("Config tuning.search_space is required for tuning")
    if fixed_params is None:
        raise ValueError("Fixed training params are required for tuning")

    os.makedirs(output_dir, exist_ok=True)

    sampler = TPESampler(n_startup_trials=5, seed=42)
    pruner = MedianPruner(n_startup_trials=5, n_warmup_steps=2)

    study = optuna.create_study(
        study_name=study_name,
        storage=storage,
        sampler=sampler,
        pruner=pruner,
        direction="maximize",
        load_if_exists=True,
    )

    print(f"\n{'='*60}")
    print("HYPERPARAMETER TUNING")
    print(f"{'='*60}")
    print(f"Study name: {study_name}")
    print(f"Number of trials: {n_trials}")
    print(f"Timesteps per trial: {timesteps_per_trial:,}")
    print(f"Parallel environments: {n_envs}")
    print(f"Time scale: {time_scale}")
    print(f"{'='*60}\n")

    try:
        study.optimize(
            lambda trial: objective(
                trial,
                boss=boss,
                n_envs=n_envs,
                timesteps_per_trial=timesteps_per_trial,
                eval_freq=eval_freq,
                n_eval_episodes=n_eval_episodes,
                time_scale=time_scale,
                search_space=search_space,
                fixed_params=fixed_params,
                only_params=only_params,
                boss_damage_coef=boss_damage_coef,
                boss_defeat_coef=boss_defeat_coef,
                player_damage_coef=player_damage_coef,
                too_far_coef=too_far_coef,
                too_far_threshold=too_far_threshold,
                too_close_coef=too_close_coef,
                too_close_threshold=too_close_threshold,
                time_penalty_coef=time_penalty_coef,
                silk_coef=silk_coef,
                handicaps=handicaps,
            ),
            n_trials=n_trials,
            show_progress_bar=True,
        )
    except KeyboardInterrupt:
        print("\n\nTuning interrupted by user.")

    print(f"\n{'='*60}")
    print("TUNING RESULTS")
    print(f"{'='*60}")
    print(f"Number of finished trials: {len(study.trials)}")

    if len(study.trials) > 0:
        print(f"\nBest trial:")
        best_trial = study.best_trial
        print(f"  Value (mean reward): {best_trial.value:.4f}")
        print(f"  Params:")
        for key, value in best_trial.params.items():
            print(f"    {key}: {value}")

        best_params_path = os.path.join(output_dir, "best_params.json")
        with open(best_params_path, "w") as f:
            json.dump(best_trial.params, f, indent=2)
        print(f"\nBest params saved to: {best_params_path}")

        trials_path = os.path.join(output_dir, "all_trials.json")
        trials_data = []
        for trial in study.trials:
            if trial.state == optuna.trial.TrialState.COMPLETE:
                trials_data.append(
                    {
                        "number": trial.number,
                        "value": trial.value,
                        "params": trial.params,
                    }
                )
        with open(trials_path, "w") as f:
            json.dump(trials_data, f, indent=2)
        print(f"All trials saved to: {trials_path}")

    print(f"{'='*60}\n")

    return study


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Hyperparameter tuning for PPO")
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to YAML config file containing hyperparameters (e.g., configs/lace.yaml)",
    )
    parser.add_argument("--n-trials", type=int, default=20, help="Number of trials")
    parser.add_argument(
        "--n-envs", type=int, default=1, help="Number of parallel environments"
    )
    parser.add_argument(
        "--timesteps", type=int, default=100_000, help="Timesteps per trial"
    )
    parser.add_argument(
        "--eval-freq", type=int, default=20_000, help="Evaluation frequency"
    )
    parser.add_argument(
        "--n-eval-episodes", type=int, default=10, help="Episodes per evaluation"
    )
    parser.add_argument(
        "--only-params",
        type=str,
        default=None,
        help="Comma-separated list of hyperparameters to tune (others use config values)",
    )
    parser.add_argument("--study-name", type=str, default="silk_tron")
    parser.add_argument(
        "--storage",
        type=str,
        default=None,
        help="Optuna storage URL (e.g., sqlite:///study.db.db)",
    )
    parser.add_argument("--output_dir", type=str, default="./hyperparameters")

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)
    print(f"Loaded config from: {args.config}")
    print(f"Config: {json.dumps(config, indent=2)}")

    tuning = config.get("tuning")
    if tuning is None or "search_space" not in tuning:
        raise ValueError(
            "Config must include tuning.search_space to run hyperparameter tuning"
        )
    search_space = tuning["search_space"]
    if not isinstance(search_space, dict) or not search_space:
        raise ValueError("tuning.search_space must be a non-empty mapping")

    fixed_params = _build_fixed_params(config)

    only_params = None
    if args.only_params:
        only_params = [name.strip() for name in args.only_params.split(",") if name]
        if not only_params:
            raise ValueError("--only-params must include at least one name")

    # Load handicaps from config
    handicaps_dict = config.get("handicaps", {})
    handicaps = HandicapConfig(**handicaps_dict)

    tune(
        boss=config["boss"],
        n_trials=args.n_trials,
        n_envs=args.n_envs,
        timesteps_per_trial=args.timesteps,
        eval_freq=args.eval_freq,
        n_eval_episodes=args.n_eval_episodes,
        time_scale=config.get("time_scale", 4.0),
        search_space=search_space,
        fixed_params=fixed_params,
        only_params=only_params,
        study_name=args.study_name,
        storage=args.storage,
        output_dir=args.output_dir,
        boss_damage_coef=config.get("boss_damage_coef", 1.0),
        boss_defeat_coef=config.get("boss_defeat_coef", 0.0),
        player_damage_coef=config.get("player_damage_coef", 0.1),
        too_far_coef=config.get("too_far_coef", 0.001),
        too_far_threshold=config.get("too_far_threshold", 15.0),
        too_close_coef=config.get("too_close_coef", 0.001),
        too_close_threshold=config.get("too_close_threshold", 1.0),
        time_penalty_coef=config.get("time_penalty_coef", 0.0001),
        silk_coef=config.get("silk_coef", 0.0),
        handicaps=handicaps,
    )
