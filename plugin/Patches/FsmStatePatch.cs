using HarmonyLib;
using HutongGames.PlayMaker;

namespace SilkTronPlugin.Patches;

/// <summary>
/// Reports every state the boss's main FSM enters, including those that are left within the same
/// frame, which polling ActiveStateName misses. It is applied by hand so that a game update that
/// renames the method only loses this, rather than breaking every patch.
/// </summary>
internal static class FsmStatePatch
{
    public static void Apply(Harmony harmony)
    {
        var target = AccessTools.Method(typeof(Fsm), "EnterState", new[] { typeof(FsmState) });
        if (target == null)
        {
            Plugin.Logger.LogWarning("Fsm.EnterState not found. Boss states that last less than a frame will be missed.");
            return;
        }

        try
        {
            harmony.Patch(target, postfix: new HarmonyMethod(typeof(FsmStatePatch), nameof(Postfix)));
        }
        catch (System.Exception e)
        {
            Plugin.Logger.LogWarning($"Could not patch Fsm.EnterState: {e.Message}");
        }
    }

    private static void Postfix(Fsm __instance, FsmState __0)
    {
        var bossFsm = BossStateManager.CurrentBossFsm;
        if (bossFsm == null || __instance != bossFsm.Fsm || __0 == null)
            return;

        BossStateManager.OnStateEntered(__0.Name);
    }
}
