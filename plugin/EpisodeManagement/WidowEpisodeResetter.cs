using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace SilkTronPlugin.EpisodeManagement;

/// <summary>
/// In the game, Widow is "Spinner". Her fight starts when the hero walks into the arena's challenge region,
/// after which her main FSM goes Dormant, Intro In, Scream Start, Intro Scream, Start Fight, Idle.
/// </summary>
public class WidowEpisodeResetter : EpisodeResetterBase
{
    private const float FightStartTimeoutSeconds = 30f;

    private const string ShrineSequenceId = "Bellshrine Sequence Bellhart";

    private static readonly string[] ResetFsmNames = { "Control", "Stun Control", "Fake Death" };

    private class VariableSnapshot
    {
        public readonly Dictionary<string, bool> Bools = new Dictionary<string, bool>();
        public readonly Dictionary<string, int> Ints = new Dictionary<string, int>();
        public readonly Dictionary<string, float> Floats = new Dictionary<string, float>();
        public readonly Dictionary<string, string> Strings = new Dictionary<string, string>();
    }

    // Her phase is kept in FSM variables (In P2, Final Phase, Started Rage, Did Fake Death, Binds, ...), so a soft
    // reset puts all of them back to how they were when the fight started.
    private readonly Dictionary<string, VariableSnapshot> _variablesAtFightStart = new Dictionary<string, VariableSnapshot>();

    private Vector3 _scaleAtFightStart = new Vector3(-1f, 1f, 1f);

    protected override Vector3 BossResetScale => _scaleAtFightStart;

    protected override void ResetPlayerData()
    {
        base.ResetPlayerData();

        // The game remembers the fight as won, which switches off its trigger and opens the bench.
        var playerData = HeroController.instance.playerData;
        playerData.spinnerDefeated = false;
        playerData.SpinnerDefeatedTimePassed = false;
        playerData.encounteredSpinner = true;
        playerData.bellShrineBellhart = false;
        ScenePersistence.RemoveEntry(CommandLineArgs.Boss.Scene, ShrineSequenceId);
    }

    // Leaving the scene writes the shrine's progress back, which would put the bench there again.
    protected override void OnLevelStateSaved()
    {
        ScenePersistence.RemoveEntry(CommandLineArgs.Boss.Scene, ShrineSequenceId);
    }

    protected override IEnumerator WaitForFightStart()
    {
        var fsm = BossStateManager.CurrentBossFsm;
        if (fsm == null)
        {
            Plugin.Logger.LogWarning("[Widow] No boss FSM to wait for");
            yield break;
        }

        // Moving the hero into the arena starts the fight, and the intro plays out.
        var deadline = Time.time + FightStartTimeoutSeconds;
        while (fsm.ActiveStateName != "Idle" && Time.time < deadline)
        {
            yield return null;
        }

        if (fsm.ActiveStateName != "Idle")
        {
            Plugin.Logger.LogWarning(
                $"[Widow] The fight did not start within {FightStartTimeoutSeconds}s. Her FSM is in state {fsm.ActiveStateName}. " +
                $"Is the hero inside the challenge region, at {CommandLineArgs.Boss.HeroSpawnPosition}?");
            yield break;
        }

        _scaleAtFightStart = BossStateManager.CurrentBoss.transform.localScale;

        _variablesAtFightStart.Clear();
        foreach (var bossFsm in BossStateManager.CurrentBoss.GetComponents<PlayMakerFSM>())
        {
            if (System.Array.IndexOf(ResetFsmNames, bossFsm.FsmName) >= 0)
            {
                _variablesAtFightStart[bossFsm.FsmName] = TakeSnapshot(bossFsm);
            }
        }

        Plugin.Logger.LogInfo(
            $"[Widow] Fight started. Boss at {BossStateManager.CurrentBoss.transform.position}, scale {_scaleAtFightStart}");
    }

    protected override void ResetAllBossFsms(HealthManager boss)
    {
        base.ResetAllBossFsms(boss);

        foreach (var fsm in boss.GetComponents<PlayMakerFSM>())
        {
            if (System.Array.IndexOf(ResetFsmNames, fsm.FsmName) < 0)
                continue;

            if (_variablesAtFightStart.TryGetValue(fsm.FsmName, out var snapshot))
            {
                Restore(fsm, snapshot);
            }

            fsm.SetState("Idle");
        }
    }

    protected override void ClearBossProjectiles()
    {
        var boss = BossStateManager.CurrentBoss;

        foreach (var obj in Object.FindObjectsByType<GameObject>(FindObjectsSortMode.None))
        {
            if (obj == null || !obj.activeInHierarchy)
                continue;

            var isBell = obj.name.Contains("Spinner AtkBell");
            var isBlade = obj.name == "blade" && (boss == null || !obj.transform.IsChildOf(boss.transform));
            if (isBell || isBlade)
            {
                obj.SetActive(false);
            }
        }
    }

    private static VariableSnapshot TakeSnapshot(PlayMakerFSM fsm)
    {
        var snapshot = new VariableSnapshot();
        var variables = fsm.FsmVariables;

        foreach (var variable in variables.BoolVariables)
            snapshot.Bools[variable.Name] = variable.Value;
        foreach (var variable in variables.IntVariables)
            snapshot.Ints[variable.Name] = variable.Value;
        foreach (var variable in variables.FloatVariables)
            snapshot.Floats[variable.Name] = variable.Value;
        foreach (var variable in variables.StringVariables)
            snapshot.Strings[variable.Name] = variable.Value;

        return snapshot;
    }

    private static void Restore(PlayMakerFSM fsm, VariableSnapshot snapshot)
    {
        var variables = fsm.FsmVariables;

        foreach (var variable in variables.BoolVariables)
            if (snapshot.Bools.TryGetValue(variable.Name, out var value))
                variable.Value = value;
        foreach (var variable in variables.IntVariables)
            if (snapshot.Ints.TryGetValue(variable.Name, out var value))
                variable.Value = value;
        foreach (var variable in variables.FloatVariables)
            if (snapshot.Floats.TryGetValue(variable.Name, out var value))
                variable.Value = value;
        foreach (var variable in variables.StringVariables)
            if (snapshot.Strings.TryGetValue(variable.Name, out var value))
                variable.Value = value;
    }
}
