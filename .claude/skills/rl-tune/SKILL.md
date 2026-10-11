---
name: rl-tune
description: Tune training for one boss to minimize episode/lowest_boss_hp_mean, through config changes or code changes such as reward shaping, observations or the network. Screens each change on a short run, confirms the best ones on full-length runs, and checks training stability as well as the objective. Takes a boss name. Use when asked to tune, improve or experiment with a boss's training (hyperparameters, rewards, schedules, observations, network), or to compare training runs.
argument-hint: <boss>
---

# Tune training for a boss

Boss: **$ARGUMENTS**

**Goal:** minimize `episode/lowest_boss_hp_mean`. This is the rolling mean, over the last 100 episodes, of the lowest boss HP reached in each episode. It is in absolute HP, so compare it only between runs of the same boss. Treat everything else as a diagnostic or a constraint, including `rollout/ep_rew_mean`, which changes scale whenever a reward coefficient changes.

## 1. Resolve the config

- Find the config in `configs/` whose file stem matches the boss name (ignoring case, spaces and underscores) or whose `boss:` field matches it. If no name was given, if nothing matches, or if more than one file matches (for example `moss_mother` and `moss_mother_easy`), ask the user which one to use.
- Call that stem `<config>`. **Every run name starts with `<config>/`**, so all runs for a boss are grouped in `experiments/<config>/` and in TensorBoard.

## 2. Catch up on what has been tried

- Read `configs/<config>.yaml` and `git log -p --follow configs/<config>.yaml`. The commit messages record past changes and why they were made.
- Read `experiments/<config>/TUNING.md` if it exists. It is the tuning journal from earlier sessions (see step 7).
- List the runs in `experiments/<config>/`. Each run has a `config.json`, so you can see what it changed.
- Compare the relevant existing runs with the helper script, putting the baseline first:

  ```bash
  uv run python .claude/skills/rl-tune/compare_runs.py experiments/<config>/<baseline_run> experiments/<config>/<other_run> ...
  ```

  It compares the runs at the last step they all reached (or at `--at N`). It prints the config differences from the first run, the objective at 25/50/75/100% of that step with each run's delta, and stability metrics over the last quarter.

## 3. Plan the screen

Choose 1–4 changes, each with a stated hypothesis based on the curves and on what has already been tried. A change can be to the config or to the code (see "Code changes" below). Prefer a code change when the curves point to a problem no hyperparameter can fix: for example, a reward term the agent exploits, information the policy can't observe, or a network bottleneck. **Change one thing per variant.** Parameters that are coupled count as one change: for example, scale `learning_rate` and `learning_rate_final` together. Before choosing a change, think through its side effects (see the table below). Tell the user the plan, including the variants, the reason for each, and the rough wall-clock time, and then start.

### Screening rules

- **Screen at 1M steps** (`--total-timesteps 1000000`) before any full-length run. On this machine 1M steps take about 25 minutes with 4 envs at `time_scale` 8.
- **Make the screen match the long run's schedules.** `lr_decay_steps` and `ent_decay_steps` count absolute steps, so a 1M screen follows exactly the first third of a 3M run. If the config uses `learning_rate_final` or `ent_coef_final` without the matching `*_decay_steps`, the decay is spread over `total_timesteps` instead, so a 1M screen would decay three times as fast. In that case set `*_decay_steps` to the config's `total_timesteps` in every screening file, including the baseline. A run whose `*_decay_steps` is null has the same schedule as one where it equals that run's `total_timesteps`.
- **Every screen needs a baseline** with the current config, at the same length and seed. You can reuse an existing run as the baseline if its `config.json` matches the current config apart from `total_timesteps` (with the equivalence above) and it reached at least 1M steps. This includes the first 1M steps of a long run. Otherwise run `<config>/base_1m` first.
- **Leave `n_envs`, `time_scale`, `no_fx`, `handicaps` and `boss` alone.** The handicaps and boss define the task, and `n_envs` is capped by RAM (see below).

### Variant files and run names

- Copy `configs/<config>.yaml` to `experiments/<config>/variants/<variant>.yaml` and edit the copy. `experiments/` is gitignored, and the file stays next to its runs. Don't edit `configs/<config>.yaml` until a change has won its long run (step 6).
- `<variant>` is a short slug for the change, such as `gamma0995`, `ent002` or `lr6e-4`, and the step count is added as a suffix: `--run-name <config>/<variant>_1m` or `<config>/<variant>_3m`. `train.py` appends a timestamp, so the run directory is `experiments/<config>/<variant>_1m_<timestamp>/`.

### Code changes

You may change the Python code (`silk_tron/`, `train.py`) and the plugin (`plugin/`). Examples include reward shaping, new observation features, the feature extractor, action masking, normalization, and new schedules.

- **Put each change behind a config option that defaults to the current behaviour.** Thread the option through the same way existing options such as `silk_coef` or `lr_decay_steps` are: read it from the config in `train.py`, pass it to `train()` and the env factories, and add it to `save_config` and to `evaluate()` where it affects the env. That way the baseline still runs the old code, other bosses are unaffected, every run's `config.json` records whether the change was on, and `compare_runs.py` shows it as a config difference. Turn the option on only in the variant file.
- **If a change can't be gated**, for example because it changes the observation size (which also stops old checkpoints from loading) or alters plugin behaviour that Python can't switch, make it on a branch named `tune/<config>-<variant>`. Note the commit in the journal, and make sure the baseline ran on code without the change. Switch back to the original branch once the screen is done.
- **Don't touch the objective or the task.** Don't change how `lowest_boss_hp` is measured or logged, boss or player HP or damage, handicaps, or the episode start and end conditions in ways that make a lower HP easier to reach. A change has to make the agent better at the same fight.
- **Check the change before using compute on it.** Run `uv run pytest`, and add a test when the change has logic worth pinning down (see `tests/test_schedules.py`). After plugin changes, run `dotnet build plugin`. Then do a short smoke run, for example `--total-timesteps 20000 --run-name <config>/smoke`, and check that episodes reset and the new behaviour shows up in the logs. Delete the smoke run's directory afterwards.
- **Never edit code or rebuild the plugin while a run is going.** A build copies the DLL into the game's plugins folder, and worker processes or restarted game instances could pick up half-finished changes.
- Save the change next to its runs with `git diff > experiments/<config>/variants/<variant>.patch` (or the branch commit), so the journal can point to exactly what was tested.
- Match the surrounding code style. Keep each change as small as the hypothesis needs.

### Launching

```bash
uv run python train.py --config experiments/<config>/variants/<variant>.yaml --run-name <config>/<variant>_1m --total-timesteps 1000000
```

- **Run only one training at a time.** Each game instance uses about 2 GB of RAM, and running more instances than that has frozen the machine before. Before you launch, check that no other run is going (`pgrep -af "train.py|tune.py"`). Queue the variants one after another.
- Start each run in the background (`run_in_background`) and wait for the completion notification. Don't poll with sleep. When a run finishes, run `compare_runs.py` on it before launching the next one, because a result can change what is worth screening next.
- If a run crashes (for example, a game instance fails to start), read the end of its output, fix the cause or tell the user, and rerun it. Don't compare a partial run as if it were complete.

## 4. Judge the screen

Run `compare_runs.py` with the baseline first and all the screened variants after it.

- **Objective.** Lower `lowest_boss_hp_mean` at 1M is better. Look at the trend too: a variant that is still falling steeply at 1M can be worth more than one that has flattened out at a slightly lower value.
- **Noise.** Each run uses one seed, and the game's timing makes even same-seed runs differ. The `regress` column (how far the objective rose above its best value so far) gives a rough idea of the noise, typically a few HP. Treat a delta smaller than the runs' `regress` values as inconclusive. If an inconclusive change still looks worth promoting, rerun both it and the baseline with another `seed` before trusting it.
- **Stability.** Compare each variant with the baseline, not with fixed thresholds:
  - `approx_kl`: values near 1.5 × `target_kl` mean early stopping is cutting the epoch loop short, so the update is being throttled. Large or spiky KL means the policy is lurching.
  - `clip_fraction`: a big increase means the updates are pushing against the clip range.
  - `explained_variance` falling, or `value_loss` rising sharply: the critic is not keeping up.
  - `entropy` (`train/entropy_loss`, which is the negated entropy): rising quickly toward 0 means the policy is collapsing toward deterministic play early. That often looks good at 1M and then stalls at 3M.
  - `regress`: a large value means the objective improved and then got worse again. This is a red flag even if the final value is good.
- **Behaviour.** For reward changes especially, check that the policy is not exploiting the reward instead of fighting. Look at `rollout/success_rate`, `episode/hurt_count_mean`, `episode/attack_count_mean`, `rollout/ep_len_mean`, `actions/proportion_*` (such as heavy use of one action) and the `rewards/mean_*` components. These are TensorBoard tags. Read them with `tbparse` (`SummaryReader(logs_dir, pivot=True).scalars`) or the TensorBoard UI.
- **Throughput.** Check `time/fps`. A change that is better per step but much slower per hour has to be judged on both counts.
- **Short-screen bias.** A 1M screen favours whatever speeds up early learning: higher learning rates, less entropy, more updates per sample. Weigh how a change is likely to behave late in training, not just its 1M number.

A variant **passes** if it is clearly better on the objective and has no stability or behaviour regression you can't explain.

## 5. Confirm on a long run

- Run each passing variant for the config's full `total_timesteps` (leave out `--total-timesteps`), named `<config>/<variant>_3m` (or whatever the length is).
- Compare it with a long baseline of the current config: an existing full-length run that matches, or a new `<config>/base_3m`. Apply the same judgement as in step 4, at the full length.
- If you want to combine several screened winners, screen the combination at 1M first, because changes can interact.

## 6. Adopt the winner

If the long run wins, apply the change to `configs/<config>.yaml`. Follow the file's comment style, and add a short comment where the reason for a value isn't obvious. Then show the user the comparison. Offer to commit, but only commit if they agree, using a one-sentence message in the style of the existing ones (for example, "Triple the Widow boss damage coefficient."). If the change was a loss or the result was inconclusive, leave the config unchanged.

For a code change that wins, keep the code and enable its option in `configs/<config>.yaml`. Leave the default as the old behaviour unless the user wants it applied to other bosses, which would need their own screens. For a code change that loses or is inconclusive, revert it (or delete its branch) so options that were never adopted don't pile up. Its `.patch` file and journal entry are kept so it can be retried later.

## 7. Record and report

Append to `experiments/<config>/TUNING.md` (create it if needed). For each run, record the date, run directory, change (with the `.patch` file or branch commit for code changes), hypothesis, objective at the screen and full lengths with deltas against the baseline, any stability notes, and the verdict (pass, fail, inconclusive or adopted). Future sessions start from this file.

End by giving the user a short table of the runs and verdicts, what changed in the config (if anything), and the next things you would try.

## Knobs and their side effects

| Knob | Effect | Watch for |
|---|---|---|
| `learning_rate`, `learning_rate_final`, `lr_decay_steps` | Faster progress per step | KL near the `target_kl` cap, `regress`, late collapse. Keep the initial/final ratio unless the decay itself is what you are testing |
| `ent_coef`, `ent_coef_final`, `ent_decay_steps` | Exploration versus committing to a strategy | Entropy collapsing early, action proportions narrowing. Lower values are flattered by short screens |
| `n_steps`, `batch_size`, `n_epochs` | Samples per update and gradient steps per sample | More epochs or smaller batches raise KL and hit `target_kl`. Bigger rollouts give fewer updates per step, so they look slow at 1M. `n_steps` is per env (rollout = `n_steps` × `n_envs`) |
| `target_kl`, `clip_range` | How large each update can be | Too tight throttles learning (KL pinned at the cap); too loose lets the policy lurch |
| `gamma`, `gae_lambda` | Credit-assignment horizon | Value loss and explained variance. Interacts with `time_penalty_coef` and with how long fights last |
| `vf_coef`, `max_grad_norm` | Critic weight, gradient clipping | `value_loss`, `explained_variance` |
| Reward coefficients (`boss_damage_coef`, `player_damage_coef`, `too_far_*`, `too_close_*`, `time_penalty_coef`, `silk_coef`, `boss_defeat_coef`) | Change what the agent is optimizing | Reward exploitation (check behaviour metrics). `ep_rew_mean` and VecNormalize scaling are no longer comparable |
| `features_dim`, `pi_layers`, `vf_layers` | Network capacity | `time/fps`, overfitting to early play. Changing these means no old checkpoint can be loaded |
| Code: new reward terms (`silk_tron/env.py`) | Shape behaviour the coefficients can't reach | As for reward coefficients. Add the term to the `reward_components` info so it gets its own `rewards/mean_*` tag |
| Code: observations (`silk_tron/env.py`, `constants.py`, the plugin) | Give the policy information it is missing | The observation size changes, so old checkpoints won't load. Check the scaling of new features (`VecNormalize` uses `norm_obs=False`) |
| Code: network (`silk_tron/networks.py`) | Better use of the features the policy already has | `time/fps`, `explained_variance`. Old checkpoints won't load |
