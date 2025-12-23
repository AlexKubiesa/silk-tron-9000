from functools import partial
from pathlib import Path
from dotenv import load_dotenv
import os
from typing import Union
import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
import torch
from torch import nn


from silk_tron.env import MyMonitor, SilksongBossEnv
from silk_tron.networks import MultiHeadFeatureExtractor, TensorboardCallback


load_dotenv(Path(__file__).parent / ".env")


def make_env(time_scale: float = 1.0, no_fx: bool = False):
    import torch

    torch.set_num_threads(1)

    env = SilksongBossEnv(time_scale=time_scale, no_fx=no_fx)
    env = MyMonitor(env)
    return env


def make_vec_env(time_scale: float = 1.0, no_fx: bool = False):
    env_fn = partial(make_env, time_scale=time_scale, no_fx=no_fx)
    return DummyVecEnv([env_fn])


def train(
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
    log_dir: str = "./logs",
    save_dir: str = "./models",
    checkpoint_path: str | None = None,
    time_scale: float = 4.0,
    device: Union[torch.device, str] = "cpu",
    no_fx: bool = False,
):
    resuming = checkpoint_path and os.path.exists(checkpoint_path)

    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(save_dir, exist_ok=True)

    if resuming:
        print("\n" + "=" * 60)
        print("RESUMING TRAINING FROM CHECKPOINT")
        print("=" * 60)
        print(f"Checkpoint: {checkpoint_path}")
    else:
        print("\n" + "=" * 60)
        print("STARTING NEW TRAINING")
        print("=" * 60)

    print(f"Total timesteps: {total_timesteps:,}")
    print(f"Learning rate: {learning_rate}")
    print(f"Time scale: {time_scale}")
    print(f"NoFx: {no_fx}")
    print(f"Log directory: {log_dir}")
    print(f"Save directory: {save_dir}")
    print("=" * 60)

    print(f"\nLaunching game instance...")
    env = make_vec_env(time_scale=time_scale, no_fx=no_fx)

    vecnormalize_path = (  # TODO: Support all checkpoint paths, not just this specific format
        (
            "models/rl_model_vecnormalize_"
            + checkpoint_path[len("models/rl_model_") :].replace(".zip", ".pkl")
        )
        if checkpoint_path
        else None
    )
    if resuming and vecnormalize_path and os.path.exists(vecnormalize_path):
        print(f"Loading VecNormalize from: {vecnormalize_path}")
        env = VecNormalize.load(vecnormalize_path, env)
    else:
        env = VecNormalize(env, norm_obs=False, norm_reward=True)

    policy_kwargs = dict(
        features_extractor_class=MultiHeadFeatureExtractor,
        features_extractor_kwargs=dict(features_dim=256),
        net_arch=dict(pi=[128], vf=[128]),
        activation_fn=nn.ReLU,
    )

    if resuming:
        print(f"\nLoading model from checkpoint: {checkpoint_path}")
        model = PPO.load(
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
        print("\nInitializing new PPO model...")
        model = PPO(
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

    checkpoint_callback = CheckpointCallback(
        save_freq=10000,
        save_path=save_dir,
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
        )

        final_model_path = os.path.join(save_dir, "rl_model_final")
        model.save(final_model_path)
        env.save(os.path.join(save_dir, "vecnormalize_final.pkl"))

        print("\n" + "=" * 60)
        print("Training completed!")
        print(f"Final model saved to: {final_model_path}")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\nTraining interrupted by user.")
        interrupt_model_path = os.path.join(save_dir, "rl_model_interrupted")
        model.save(interrupt_model_path)
        env.save(os.path.join(save_dir, "vecnormalize_interrupted.pkl"))
        print(f"Model saved to: {interrupt_model_path}")

    finally:
        env.close()


def evaluate(
    model_path: str, n_episodes: int = 10, time_scale: float = 1.0, no_fx: bool = False
):
    print(f"\nEvaluating model: {model_path}")
    print(f"Time scale: {time_scale}")
    print(f"NoFx: {no_fx}")

    env = DummyVecEnv([partial(make_env, time_scale=time_scale, no_fx=no_fx)])

    vecnormalize_path = "models/rl_model_vecnormalize_" + model_path[  # TODO: Support all checkpoint paths, not just this specific format
        len("models/rl_model_") :
    ].replace(
        ".zip", ".pkl"
    )
    if os.path.exists(vecnormalize_path):
        print(f"Loading VecNormalize from: {vecnormalize_path}")
        env = VecNormalize.load(vecnormalize_path, env)
        env.training = False
        env.norm_reward = False
    else:
        env = VecNormalize(env, norm_obs=False, norm_reward=False, training=False)

    print(f"Loading PPO model from: {model_path}")
    model = PPO.load(model_path, env=env)
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

    parser = argparse.ArgumentParser()
    parser.add_argument("--eval", action="store_true")
    parser.add_argument("--checkpoint", type=str)

    parser.add_argument(
        "--total-timesteps",
        type=int,
        default=10_000_000,
        help="Total number of timesteps for training",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=5e-4,
        help="Learning rate for the optimizer",
    )
    parser.add_argument(
        "--n-steps",
        type=int,
        default=2048,
        help="Number of steps to run for each environment per update",
    )
    parser.add_argument(
        "--n-epochs",
        type=int,
        default=4,
        help="Number of epochs to run when optimizing the surrogate loss",
    )
    args = parser.parse_args()

    if args.eval:
        if not args.checkpoint:
            parser.error("--eval requires --checkpoint")
        evaluate(args.checkpoint, n_episodes=10, time_scale=1.0)
    else:
        train(
            total_timesteps=args.total_timesteps,
            learning_rate=args.learning_rate,
            n_steps=args.n_steps,
            batch_size=512,
            n_epochs=args.n_epochs,
            gamma=0.99,
            gae_lambda=0.95,
            clip_range=0.1,
            ent_coef=0.03,
            vf_coef=0.5,
            max_grad_norm=0.3,
            checkpoint_path=args.checkpoint,
            time_scale=4.0,
            device="cpu",
            no_fx=True,
        )
