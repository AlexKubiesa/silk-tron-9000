# SilkTron 9000

A reinforcement learning agent for Hollow Knight: Silksong.

The boss fights currently supported are Moss Mother, the second Lace fight and Widow (called Spinner in the game).

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
uv run python train.py --config configs/moss_mother.yaml
uv run python train.py --config configs/moss_mother.yaml --checkpoint ./experiments/run_abc/checkpoints/rl_model_1000_steps.zip
```

> **Tip**: Use `--no-fx` mode (enabled by default in training) for faster step processing.

### Evaluation

```bash
uv run python train.py --eval --config configs/moss_mother.yaml --checkpoint ./experiments/run_abc/checkpoints/rl_model_1000_steps.zip
```

### Tensorboard

```bash
uv run tensorboard --logdir ./logs
```

## Adding a boss

The plugin has tools for finding out what a new boss needs. They are only active when the game is started in manual mode, so they have no effect on training.

### Starting the game by hand

The plugin needs its shared memory file to exist, even though Python is not involved. Create it once, then start the game from its folder. Back up your save first (`~/.config/unity3d/Team Cherry/Hollow Knight Silksong/default`), because jumping between rooms can autosave into it.

```bash
truncate -s 4096 /dev/shm/silk_tron
cd "<game folder>"
./run_bepinex.sh --boss <Name> --manual < /dev/null > manual_output.log 2>&1 &
tail -f BepInEx/LogOutput.log
```

`--boss` has to be a name registered in [Boss.cs](plugin/Core/Boss.cs), so add a placeholder entry first (see below). The player has the abilities from the `--player-*` defaults, not those of a config.

### Keys

| Key | Does |
|---|---|
| F1 | Show or hide the overlay: positions, velocities, HP, phase, the boss's clip and FSM states, and the agent's inputs |
| F2 | Show or hide the 32 rays |
| F3 | Find the boss and log its scene, every `HealthManager`, its animation clips (as lines to paste into [BossAnimationState.cs](plugin/Core/BossAnimationState.cs)) and its FSMs |
| F4 | Log what has been recorded since the last reset, and write the state timeline to `silktron_state_timeline.txt` |
| F5 | Clear the recorded data. It is also cleared on every scene load |
| F6 | Jump to the scene named in `silktron_jump.txt` |
| F7 | Log the current scene's gates. This also happens on every scene load |
| F8 | Write every progress flag to `silktron_flags_dump.txt` |
| F9 | Apply the edits in `silktron_flags.txt` |
| F10 | Write every object in the scene, including inactive ones, to `silktron_scene_dump.txt` |
| F11 / F12 | Hard or soft reset the episode, as Python would |

In training with `--no-fx`, F9 instead switches the camera between its minimal and full resolution, so you can watch a run.

The text files are in the game's `BepInEx` folder and are read when the key is pressed. `silktron_jump.txt` holds one line, `SceneName GateName`. `silktron_flags.txt` holds one edit per line:

```
player someField false          # a PlayerData bool
scene SceneName Item Id false   # a scene's persistent bool or int
unscene SceneName Item Id       # forget a scene's entry, putting it back to its default
```

The game writes a scene's entries back from the objects in it when you leave it, which undoes edits made while you are there. Make `scene` and `unscene` edits from a different room, then enter the scene. Edits are made in memory and the game may not keep them across a restart, so apply them again after restarting.

Scene names can be listed without starting the game:

```bash
uv run python list_scenes.py <filter>
```

### Steps

1. **Register a placeholder.** Add a `BossId` and a `Boss` entry in [Boss.cs](plugin/Core/Boss.cs), a stub in [BossAnimationState.cs](plugin/Core/BossAnimationState.cs), a case in [EpisodeResetter.cs](plugin/Core/EpisodeResetter.cs) with an empty resetter class (see [WidowEpisodeResetter.cs](plugin/EpisodeManagement/WidowEpisodeResetter.cs)), and an entry in [bosses.py](silk_tron/bosses.py).
2. **Get to the arena.** Jump there with F6, using F7's list for gate names. If the save has the boss as already beaten, find the flags with F8 (search the dump for the boss's name, which may differ from its public one) and clear them with F9.
3. **Identify the boss.** Press F3 with the boss present. If it is not listed, press F10 and look for it in the dump. It may be inactive until the fight starts. The scan gives the HP and the clip list. Replace the stub with the clips. `NUM_BOSS_ANIMATION_STATES` in [constants.py](silk_tron/constants.py) is shared by all bosses and must be at least the clip count plus one. Raising it changes the network input size, so existing checkpoints stop loading.
4. **Measure the arena.** Stand in it, press F5, walk to each corner and jump, then press F4. Use the player's extents for `arena_min_x`, `arena_max_x` and `arena_min_y`, and allow for the ceiling above your highest jump.
5. **Fight it.** The F4 report then gives the boss's velocity extents, the animation clips and FSM states it used, which phase-marking states exist, and the `DamageHero` objects that were active, which are the projectiles and hazards. The timeline shows each FSM state with the boss's HP and position. Use it to pick `BossPhases` states: the first state of phases 2 and 3, which can be instant states that only the timeline shows. Projectiles with colliders should show up on the rays as hazards (check with F2). Ones without need tracking like Lace's circle slashes in [BossProjectileManager.cs](plugin/Managers/BossProjectileManager.cs).
6. **Write the resetter.** Override what the boss needs in its resetter class. [WidowEpisodeResetter.cs](plugin/EpisodeManagement/WidowEpisodeResetter.cs) shows the main cases: clearing the flags that make the fight beaten, starting a fight that waits for a trigger, putting the boss's FSMs back, and removing its projectiles. Test it with F11 and F12, then check the F4 report's list of boss FSM variables that changed to find phase state that a reset has to restore.
7. **Add a config and run a short test.** Copy a file in [configs](configs), set `boss` and the handicaps, and run for 10,000 steps first. Check that the episodes reset and that `lowest_boss_hp_mean` in TensorBoard stays above zero.

## Acknowledgements

This project was inspired by https://github.com/deeean/silksong-agent/.
