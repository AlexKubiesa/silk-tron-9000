from functools import partial
from pathlib import Path
from dotenv import load_dotenv
import os
from typing import Union
import numpy as np
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecNormalize
import torch
from torch import nn
from datetime import datetime
import json
import gymnasium as gym
from torchinfo import summary
import yaml


from silk_tron.env import MyMonitor, SilksongBossEnv, DummySilksongBossEnv
from silk_tron.networks import (
    MultiHeadFeatureExtractor,
    TensorboardCallback,
    CustomCheckpointCallback,
)

_next_env_id = 1


load_dotenv(Path(__file__).parent / ".env")


def reset_env_id_counter():
    global _next_env_id
    _next_env_id = 1


def load_config(config_path: str) -> dict:
    """Load hyperparameters from YAML config file."""
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config


def create_run_directory(base_dir: str, name: str) -> tuple[str, str, str]:
    """Create a run directory with timestamp.

    Args:
        base_dir: Base directory for experiments
        name: Name prefix for the run directory

    Returns:
        Tuple of (run_dir, checkpoints_dir, logs_dir)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = f"{name}_{timestamp}"

    run_dir = os.path.join(base_dir, dir_name)
    checkpoints_dir = os.path.join(run_dir, "checkpoints")
    logs_dir = os.path.join(run_dir, "logs")

    os.makedirs(checkpoints_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)

    return run_dir, checkpoints_dir, logs_dir


def save_config(config_path: str, **kwargs):
    """Save training configuration to JSON file."""
    with open(config_path, "w") as f:
        json.dump(kwargs, f, indent=2)


def find_vecnormalize_path(checkpoint_path: str) -> str | None:
    """Find the corresponding VecNormalize file for a checkpoint."""
    checkpoint_path_obj = Path(checkpoint_path)
    stem = checkpoint_path_obj.stem

    vecnorm_stem = stem.replace("rl_model_", "rl_model_vecnormalize_", 1)
    vecnorm_path = checkpoint_path_obj.parent / f"{vecnorm_stem}.pkl"

    if vecnorm_path.exists():
        return str(vecnorm_path)

    return None


def save_rng_state(checkpoint_path: str):
    """Save PyTorch and NumPy RNG states alongside a checkpoint.

    Args:
        checkpoint_path: Path to the model checkpoint (e.g., checkpoints/rl_model_10000_steps.zip)
    """
    checkpoint_path_obj = Path(checkpoint_path)
    stem = checkpoint_path_obj.stem

    rng_stem = stem.replace("rl_model_", "rl_model_rng_state_", 1)
    rng_path = checkpoint_path_obj.parent / f"{rng_stem}.zip"

    rng_state = {
        "numpy": np.random.get_state(),
        "torch": torch.get_rng_state(),
    }

    torch.save(rng_state, rng_path)
    return str(rng_path)


def load_rng_state(checkpoint_path: str) -> bool:
    """Load PyTorch and NumPy RNG states from a checkpoint.

    Args:
        checkpoint_path: Path to the model checkpoint

    Returns:
        True if RNG state was found and loaded, False otherwise
    """
    checkpoint_path_obj = Path(checkpoint_path)
    stem = checkpoint_path_obj.stem

    rng_stem = stem.replace("rl_model_", "rl_model_rng_state_", 1)
    rng_path = checkpoint_path_obj.parent / f"{rng_stem}.zip"

    if not rng_path.exists():
        return False

    rng_state = torch.load(rng_path, weights_only=False)

    np.random.set_state(rng_state["numpy"])
    torch.set_rng_state(rng_state["torch"])

    return True


def make_env(
    boss: str,
    env_id: int,
    time_scale: float = 1.0,
    no_fx: bool = False,
    dummy_env: bool = False,
    boss_damage_coef: float = 1.0,
    boss_defeat_coef: float = 0.0,
    player_damage_coef: float = 0.1,
    too_far_coef: float = 0.001,
    too_far_threshold: float = 15.0,
    too_close_coef: float = 0.001,
    too_close_threshold: float = 1.0,
    time_penalty_coef: float = 0.0001,
    silk_coef: float = 0.0,
    mask_dash: bool = False,
    mask_clawline: bool = False,
) -> gym.Env:
    import torch

    torch.set_num_threads(1)

    if dummy_env:
        env = DummySilksongBossEnv()
    else:
        env = SilksongBossEnv(
            boss,
            env_id,
            time_scale=time_scale,
            no_fx=no_fx,
            boss_damage_coef=boss_damage_coef,
            boss_defeat_coef=boss_defeat_coef,
            player_damage_coef=player_damage_coef,
            too_far_coef=too_far_coef,
            too_far_threshold=too_far_threshold,
            too_close_coef=too_close_coef,
            too_close_threshold=too_close_threshold,
            time_penalty_coef=time_penalty_coef,
            silk_coef=silk_coef,
            mask_dash=mask_dash,
            mask_clawline=mask_clawline,
        )

    env = MyMonitor(env)
    return env


def make_vec_env(
    boss: str,
    n_envs: int = 1,
    time_scale: float = 1.0,
    no_fx: bool = False,
    dummy_env: bool = False,
    boss_damage_coef: float = 1.0,
    boss_defeat_coef: float = 0.0,
    player_damage_coef: float = 0.1,
    too_far_coef: float = 0.001,
    too_far_threshold: float = 15.0,
    too_close_coef: float = 0.001,
    too_close_threshold: float = 1.0,
    time_penalty_coef: float = 0.0001,
    silk_coef: float = 0.0,
    mask_dash: bool = False,
    mask_clawline: bool = False,
):
    global _next_env_id

    if n_envs < 1:
        raise ValueError(f"n_envs must be >= 1, got {n_envs}")

    start_id = _next_env_id
    _next_env_id += n_envs
    env_fns = [
        partial(
            make_env,
            boss=boss,
            env_id=start_id + i,
            time_scale=time_scale,
            no_fx=no_fx,
            dummy_env=dummy_env,
            boss_damage_coef=boss_damage_coef,
            boss_defeat_coef=boss_defeat_coef,
            player_damage_coef=player_damage_coef,
            too_far_coef=too_far_coef,
            too_far_threshold=too_far_threshold,
            too_close_coef=too_close_coef,
            too_close_threshold=too_close_threshold,
            time_penalty_coef=time_penalty_coef,
            silk_coef=silk_coef,
            mask_dash=mask_dash,
            mask_clawline=mask_clawline,
        )
        for i in range(n_envs)
    ]

    if n_envs > 1:
        return SubprocVecEnv(env_fns)
    else:
        return DummyVecEnv(env_fns)


def train(
    boss: str = "Lace",
    total_timesteps: int = 10_000_000,
    learning_rate: float = 3e-4,
    n_steps: int = 2048,
    batch_size: int = 256,
    n_epochs: int = 5,
    gamma: float = 0.99,
    gae_lambda: float = 0.95,
    clip_range: float = 0.1,
    ent_coef: float = 0.05,
    vf_coef: float = 0.5,
    max_grad_norm: float = 0.3,
    experiments_dir: str = "./experiments",
    run_name: str | None = None,
    checkpoint_path: str | None = None,
    time_scale: float = 4.0,
    device: Union[torch.device, str] = "cpu",
    no_fx: bool = False,
    seed: int | None = None,
    dummy_env: bool = False,
    n_envs: int = 1,
    boss_damage_coef: float = 1.0,
    boss_defeat_coef: float = 0.0,
    player_damage_coef: float = 0.1,
    too_far_coef: float = 0.001,
    too_far_threshold: float = 15.0,
    too_close_coef: float = 0.001,
    too_close_threshold: float = 1.0,
    time_penalty_coef: float = 0.0001,
    silk_coef: float = 0.0,
    mask_dash: bool = False,
    mask_clawline: bool = False,
):
    resuming = checkpoint_path and os.path.exists(checkpoint_path)

    # Set random seeds for reproducibility
    if resuming:
        assert checkpoint_path is not None
        assert load_rng_state(checkpoint_path)
        print(f"RNG state restored from checkpoint")
    elif seed is not None:
        print(f"Setting random seed: {seed}")
        np.random.seed(seed)
        torch.manual_seed(seed)
    else:
        print("No random seed specified, using default randomness")

    if resuming:
        # Resume in the same run directory as the checkpoint
        assert checkpoint_path is not None
        checkpoint_path_obj = Path(checkpoint_path)
        run_dir = str(checkpoint_path_obj.parent.parent)
        checkpoints_dir = str(checkpoint_path_obj.parent)
        log_dir = os.path.join(run_dir, "logs")
    else:
        # Create new run directory
        assert run_name is not None
        run_dir, checkpoints_dir, log_dir = create_run_directory(
            experiments_dir, run_name
        )

    if resuming:
        print("\n" + "=" * 60)
        print("RESUMING TRAINING FROM CHECKPOINT")
        print("=" * 60)
        print(f"Checkpoint: {checkpoint_path}")
    else:
        print("\n" + "=" * 60)
        print("STARTING NEW TRAINING")
        print("=" * 60)

    print(f"Run directory: {run_dir}")
    print(f"Total timesteps: {total_timesteps:,}")
    print(f"Learning rate: {learning_rate}")
    print(f"Time scale: {time_scale}")
    print(f"NoFx: {no_fx}")
    print(f"Seed: {seed}")
    print("=" * 60)

    # Save configuration
    if not resuming:
        config_path = os.path.join(run_dir, "config.json")
        save_config(
            config_path,
            total_timesteps=total_timesteps,
            learning_rate=learning_rate,
            n_steps=n_steps,
            batch_size=batch_size,
            n_epochs=n_epochs,
            gamma=gamma,
            gae_lambda=gae_lambda,
            clip_range=clip_range,
            ent_coef=ent_coef,
            vf_coef=vf_coef,
            max_grad_norm=max_grad_norm,
            time_scale=time_scale,
            no_fx=no_fx,
            seed=seed,
            device=str(device),
            dummy_env=dummy_env,
            boss_damage_coef=boss_damage_coef,
            boss_defeat_coef=boss_defeat_coef,
            player_damage_coef=player_damage_coef,
            too_far_coef=too_far_coef,
            too_far_threshold=too_far_threshold,
            too_close_coef=too_close_coef,
            too_close_threshold=too_close_threshold,
            time_penalty_coef=time_penalty_coef,
            silk_coef=silk_coef,
            mask_dash=mask_dash,
            mask_clawline=mask_clawline,
            created_at=datetime.now().isoformat(),
        )
        print(f"Configuration saved to: {config_path}")

    print(f"\nLaunching game instance...")
    env = make_vec_env(
        boss=boss,
        n_envs=n_envs,
        time_scale=time_scale,
        no_fx=no_fx,
        dummy_env=dummy_env,
        boss_damage_coef=boss_damage_coef,
        boss_defeat_coef=boss_defeat_coef,
        player_damage_coef=player_damage_coef,
        too_far_coef=too_far_coef,
        too_far_threshold=too_far_threshold,
        too_close_coef=too_close_coef,
        too_close_threshold=too_close_threshold,
        time_penalty_coef=time_penalty_coef,
        silk_coef=silk_coef,
        mask_dash=mask_dash,
        mask_clawline=mask_clawline,
    )

    # Load VecNormalize if resuming
    if resuming:
        assert checkpoint_path is not None
        vecnormalize_path = find_vecnormalize_path(checkpoint_path)
        assert vecnormalize_path and os.path.exists(vecnormalize_path)
        print(f"Loading VecNormalize from: {vecnormalize_path}")
        env = VecNormalize.load(vecnormalize_path, env)
    else:
        print("Initializing new VecNormalize...")
        env = VecNormalize(env, norm_obs=False, norm_reward=True)

    policy_kwargs = dict(
        features_extractor_class=MultiHeadFeatureExtractor,
        features_extractor_kwargs=dict(features_dim=256),
        net_arch=dict(pi=[128], vf=[128]),
        activation_fn=nn.ReLU,
    )

    if resuming:
        print(f"\nLoading model from checkpoint: {checkpoint_path}")
        model = MaskablePPO.load(
            checkpoint_path,  # type: ignore
            env=env,
            learning_rate=learning_rate,
            n_steps=n_steps,
            batch_size=batch_size,
            n_epochs=n_epochs,
            gamma=gamma,
            gae_lambda=gae_lambda,
            clip_range=clip_range,
            ent_coef=ent_coef,
            vf_coef=vf_coef,
            max_grad_norm=max_grad_norm,
            verbose=1,
            tensorboard_log=log_dir,
            device=device,
        )
    else:
        print("\nInitializing new MaskablePPO model...")
        model = MaskablePPO(
            policy="MlpPolicy",
            env=env,
            learning_rate=learning_rate,
            n_steps=n_steps,
            batch_size=batch_size,
            n_epochs=n_epochs,
            gamma=gamma,
            gae_lambda=gae_lambda,
            clip_range=clip_range,
            ent_coef=ent_coef,
            vf_coef=vf_coef,
            max_grad_norm=max_grad_norm,
            verbose=1,
            tensorboard_log=log_dir,
            device=device,
            policy_kwargs=policy_kwargs,
        )

    print(f"Using device: {model.device}")
    print(f"\nModel architecture:")
    print(model.policy)

    print("\nModel details:")
    print("=" * 65)
    print("\nShared feature extractor:")
    summary(model.policy.features_extractor)
    print("\nValue network hidden layers:")
    summary(model.policy.mlp_extractor.value_net)
    print("\nPolicy network hidden layers:")
    summary(model.policy.mlp_extractor.policy_net)
    print("\nValue network head:")
    summary(model.policy.value_net)
    print("\nAction network head:")
    summary(model.policy.action_net)

    checkpoint_callback = CustomCheckpointCallback(
        save_freq=10000,
        save_path=checkpoints_dir,
        name_prefix="rl_model",
        save_vecnormalize=True,
    )
    tensorboard_callback = TensorboardCallback()

    print("\n" + "=" * 60)
    print("Starting training...")
    print(f"  tensorboard --logdir {log_dir}")
    print("=" * 60 + "\n")

    try:
        model.learn(
            total_timesteps=total_timesteps,
            callback=[checkpoint_callback, tensorboard_callback],
            progress_bar=True,
            reset_num_timesteps=not resuming,
        )

        final_model_path = os.path.join(checkpoints_dir, "rl_model_final.zip")
        model.save(final_model_path)
        env.save(os.path.join(checkpoints_dir, "rl_model_vecnormalize_final.pkl"))
        save_rng_state(final_model_path)
        print(f"RNG state saved")

        print("\n" + "=" * 60)
        print("Training completed!")
        print(f"Final model saved to: {final_model_path}")
        print(f"Run directory: {run_dir}")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\nTraining interrupted by user.")
        interrupt_model_path = os.path.join(checkpoints_dir, "interrupted")
        model.save(interrupt_model_path)
        env.save(os.path.join(checkpoints_dir, "interrupted_vecnormalize.pkl"))
        save_rng_state(interrupt_model_path + ".zip")
        print(f"Model and RNG state saved to: {interrupt_model_path}")
        print(f"Run directory: {run_dir}")

    finally:
        env.close()


def evaluate(
    model_path: str,
    boss: str,
    n_episodes: int = 10,
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
    mask_dash: bool = False,
    mask_clawline: bool = False,
):
    print(f"\nEvaluating model: {model_path}")
    print(f"Time scale: {time_scale}")
    print(f"NoFx: {no_fx}")

    env = DummyVecEnv(
        [
            partial(
                make_env,
                boss=boss,
                env_id=1,
                time_scale=time_scale,
                no_fx=no_fx,
                boss_damage_coef=boss_damage_coef,
                boss_defeat_coef=boss_defeat_coef,
                player_damage_coef=player_damage_coef,
                too_far_coef=too_far_coef,
                too_far_threshold=too_far_threshold,
                too_close_coef=too_close_coef,
                too_close_threshold=too_close_threshold,
                time_penalty_coef=time_penalty_coef,
                silk_coef=silk_coef,
                mask_dash=mask_dash,
                mask_clawline=mask_clawline,
            )
        ]
    )

    # Find corresponding VecNormalize file
    vecnormalize_path = find_vecnormalize_path(model_path)
    if vecnormalize_path and os.path.exists(vecnormalize_path):
        print(f"Loading VecNormalize from: {vecnormalize_path}")
        env = VecNormalize.load(vecnormalize_path, env)
        env.training = False
        env.norm_reward = False
    else:
        print("VecNormalize file not found, using default normalization")
        env = VecNormalize(env, norm_obs=False, norm_reward=False, training=False)

    print(f"Loading MaskablePPO model from: {model_path}")
    model = MaskablePPO.load(model_path, env=env)
    print("Model loaded successfully!")

    episode_rewards = []
    episode_lengths = []

    for episode in range(n_episodes):
        obs = env.reset()
        done = False
        episode_reward = 0
        episode_length = 0

        while not done:
            action, _ = model.predict(obs, deterministic=True)  # type: ignore
            obs, reward, done, info = env.step(action)
            episode_reward += reward[0]
            episode_length += 1

        episode_rewards.append(episode_reward)
        episode_lengths.append(episode_length)
        print(
            f"Episode {episode + 1}/{n_episodes}: Reward = {episode_reward:.2f}, Length = {episode_length}"
        )

    env.close()

    print("\n" + "=" * 60)
    print("Evaluation Results:")
    print(
        f"Mean reward: {np.mean(episode_rewards):.2f} +/- {np.std(episode_rewards):.2f}"
    )
    print(
        f"Mean length: {np.mean(episode_lengths):.2f} +/- {np.std(episode_lengths):.2f}"
    )
    print("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Train a MaskablePPO agent on Silksong boss fights"
    )
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to YAML config file containing hyperparameters (e.g., configs/lace.yaml)",
    )
    parser.add_argument("--eval", action="store_true", help="Evaluate a trained model")
    parser.add_argument(
        "--checkpoint",
        type=str,
        help="Path to checkpoint to resume training or evaluate",
    )
    parser.add_argument(
        "--n-envs", type=int, default=1, help="Number of parallel environments"
    )
    parser.add_argument(
        "--experiments-dir",
        type=str,
        default="./experiments",
        help="Base directory for experiment runs (default: ./experiments)",
    )
    parser.add_argument(
        "--run-name",
        type=str,
        help="Custom name for this run (default: auto-generated with timestamp)",
    )
    args = parser.parse_args()

    # Load config
    config = load_config(args.config)
    print(f"Loaded config from: {args.config}")
    print(f"Config: {json.dumps(config, indent=2)}")

    # Extract config name from path (e.g., "configs/lace.yaml" -> "lace")
    config_name = Path(args.config).stem

    # Use run_name if provided, otherwise fall back to config_name
    run_name = args.run_name if args.run_name else config_name

    if args.eval:
        if not args.checkpoint:
            parser.error("--eval requires --checkpoint")
        evaluate(
            args.checkpoint,
            config["boss"],
            n_episodes=10,
            time_scale=1.0,
            no_fx=False,
            boss_damage_coef=config.get("boss_damage_coef", 1.0),
            boss_defeat_coef=config.get("boss_defeat_coef", 0.0),
            player_damage_coef=config.get("player_damage_coef", 0.1),
            too_far_coef=config.get("too_far_coef", 0.001),
            too_far_threshold=config.get("too_far_threshold", 15.0),
            too_close_coef=config.get("too_close_coef", 0.001),
            too_close_threshold=config.get("too_close_threshold", 1.0),
            time_penalty_coef=config.get("time_penalty_coef", 0.0001),
            silk_coef=config.get("silk_coef", 0.0),
            mask_dash=config.get("mask_dash", False),
            mask_clawline=config.get("mask_clawline", False),
        )
    else:
        # Extract network architecture params
        features_dim = config.get("features_dim", 256)
        pi_layers = config.get("pi_layers", [128])
        vf_layers = config.get("vf_layers", [128])

        train(
            boss=config["boss"],
            total_timesteps=config.get("total_timesteps", 10_000_000),
            learning_rate=config.get("learning_rate", 5e-4),
            n_steps=config.get("n_steps", 2048),
            batch_size=config.get("batch_size", 512),
            n_epochs=config.get("n_epochs", 4),
            gamma=config.get("gamma", 0.99),
            gae_lambda=config.get("gae_lambda", 0.95),
            clip_range=config.get("clip_range", 0.1),
            ent_coef=config.get("ent_coef", 0.03),
            vf_coef=config.get("vf_coef", 0.5),
            max_grad_norm=config.get("max_grad_norm", 0.3),
            experiments_dir=args.experiments_dir,
            run_name=run_name,
            checkpoint_path=args.checkpoint,
            time_scale=config.get("time_scale", 4.0),
            device="cpu",
            no_fx=config.get("no_fx", True),
            seed=config.get("seed"),
            dummy_env=False,
            n_envs=args.n_envs,
            boss_damage_coef=config.get("boss_damage_coef", 1.0),
            boss_defeat_coef=config.get("boss_defeat_coef", 0.0),
            player_damage_coef=config.get("player_damage_coef", 0.1),
            too_far_coef=config.get("too_far_coef", 0.001),
            too_far_threshold=config.get("too_far_threshold", 15.0),
            too_close_coef=config.get("too_close_coef", 0.001),
            too_close_threshold=config.get("too_close_threshold", 1.0),
            time_penalty_coef=config.get("time_penalty_coef", 0.0001),
            silk_coef=config.get("silk_coef", 0.0),
            mask_dash=config.get("mask_dash", False),
            mask_clawline=config.get("mask_clawline", False),
        )
