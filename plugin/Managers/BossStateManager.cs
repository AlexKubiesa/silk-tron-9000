using System.Linq;
using UnityEngine;

namespace SilkTronPlugin;

public static class BossStateManager
{
    public static HealthManager CurrentBoss { get; private set; }
    public static Rigidbody2D CurrentBossRb { get; private set; }
    public static PlayMakerFSM CurrentBossFsm { get; private set; }

    private static int currentBossPhase = 0;
    private static string lastTrackedFsmState = "";

    public static int CurrentPhase => currentBossPhase;

    public static void FindBoss(bool quiet = false)
    {
        var healthManagers = Object.FindObjectsByType<HealthManager>(FindObjectsSortMode.None);
        CurrentBoss = healthManagers
            .Where(hm => hm != null && hm.hp > 0)
            .Where(hm => hm.name.Contains("Boss") ||
                         hm.name.Contains("Lace") ||
                         hm.hp >= 100)
            .OrderByDescending(hm => hm.hp)
            .FirstOrDefault();

        if (CurrentBoss != null)
        {
            CurrentBossRb = CurrentBoss.GetComponent<Rigidbody2D>();
            CurrentBossFsm = CurrentBoss.GetComponent<PlayMakerFSM>();
        }
        else
        {
            CurrentBossRb = null;
            CurrentBossFsm = null;
            if (!quiet)
            {
                Plugin.Logger.LogWarning("No boss found in scene");
            }
        }
    }

    /// <summary>The boss's current tk2d clip name as the game spells it, or null if it has none.</summary>
    public static string GetCurrentClipName()
    {
        if (CurrentBoss == null)
            return null;

        var animator = CurrentBoss.GetComponent<tk2dSpriteAnimator>();
        if (animator == null || animator.CurrentClip == null)
            return null;

        return animator.CurrentClip.name;
    }

    public static void ResetBoss()
    {
        if (CurrentBoss != null)
        {
            Plugin.Logger.LogInfo($"[Reset] Clearing previous boss reference: {CurrentBoss.name}");
        }
        CurrentBoss = null;
        CurrentBossRb = null;
        CurrentBossFsm = null;
    }

    public static void ResetBossPhase()
    {
        currentBossPhase = 0;
        lastTrackedFsmState = "";
    }

    public static void UpdateBossPhase()
    {
        if (CurrentBossFsm == null)
            return;

        string stateName = CurrentBossFsm.ActiveStateName;
        if (string.IsNullOrEmpty(stateName) || stateName == lastTrackedFsmState)
            return;

        lastTrackedFsmState = stateName;

        if (currentBossPhase < 1)
        {
            if (stateName.StartsWith("P2 Shift"))
            {
                currentBossPhase = 1;
            }
        }

        if (currentBossPhase < 2)
        {
            if (stateName.StartsWith("P3 Roar"))
            {
                currentBossPhase = 2;
            }
        }
    }
}