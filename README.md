# SilkTron

A reinforcement learning agent for Hollow Knight: Silksong.

## Requirements

- **Linux** OS. Tested on Ubuntu 24.04.
- **Hollow Knight: Silksong** game installed (paid). Tested on the GOG Games version.
- **BepInEx 5** mod framework installed.
- **.NET SDK** installed, to build the plugin.
- **uv** package manager installed for Python.

## Setup

### 1. Game Setup

Install BepInEx in the game installation folder by following the instructions on the BepInEx website.

> **Note**: Multiple game instances are automatically created at runtime using junctions and hard links. No manual copying required.

### 2. Save File Setup

Copy [resources/user1.dat](resources/user1.dat) to:

```
~/.config/unity3d/Team Cherry/Hollow Knight Silksong/default
```

### 3. Environment Configuration

1. Copy `plugin/Directory.Build.props.example` → `plugin/Directory.Build.props`
2. Copy `.env.example` → `.env`
3. Set `SILKSONG_PATH` to the path of the `run_bepinex.sh` script

```
SILKSONG_PATH=/home/<username>/GOG Games/Hollow Knight Silksong/game/run_bepinex.sh
```

### 4. Build Plugin

```bash
dotnet build plugin
```

The built plugin will be automatically copied to the game's `BepInEx/plugins/` folder.

## Usage

### Training

```bash
uv run train.py
uv run train.py --checkpoint ./experiments/run_abc/checkpoints/rl_model_1000_steps.zip
```

> **Tip**: Use `--no-fx` mode (enabled by default in training) for faster step processing.

### Evaluation

```bash
uv run train.py --eval --checkpoint ./experiments/run_abc/checkpoints/rl_model_1000_steps.zip
```

### Tensorboard

```bash
uv run tensorboard --logdir ./logs
```
