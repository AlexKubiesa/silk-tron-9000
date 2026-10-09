using HarmonyLib;
using UnityEngine;

namespace SilkTronPlugin;

[HarmonyPatch]
public class BossDeathPatch
{
    [HarmonyPatch(typeof(HealthManager), nameof(HealthManager.Die),
        new[] { typeof(float?), typeof(AttackTypes), typeof(bool) })]
    [HarmonyPrefix]
    private static bool HealthManager_Die_3(HealthManager __instance)
    {
        return HandleBossDeath(__instance);
    }

    [HarmonyPatch(typeof(HealthManager), nameof(HealthManager.Die),
        new[] { typeof(float?), typeof(AttackTypes), typeof(bool), typeof(float) })]
    [HarmonyPrefix]
    private static bool HealthManager_Die_4(HealthManager __instance)
    {
        return HandleBossDeath(__instance);
    }

    [HarmonyPatch(typeof(HealthManager), nameof(HealthManager.Die),
        new[] { typeof(float?), typeof(AttackTypes), typeof(NailElements), typeof(GameObject),
                typeof(bool), typeof(float), typeof(bool), typeof(bool) })]
    [HarmonyPrefix]
    private static bool HealthManager_Die_8(HealthManager __instance)
    {
        return HandleBossDeath(__instance);
    }

    private static bool HandleBossDeath(HealthManager instance)
    {
        if (instance == BossStateManager.CurrentBoss)
        {
            if (CommandLineArgs.Demo)
            {
                // Let the boss die for real. The episode is then reset by reloading its scene.
                Plugin.Logger.LogInfo("Boss death allowed (demo mode)");
                DemoDeathPlayback.MarkBossDied();
                return true;
            }

            Plugin.Logger.LogInfo("Boss death blocked");
            return false;
        }

        return true;
    }
}