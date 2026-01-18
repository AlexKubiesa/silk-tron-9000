using System.Collections;
using HarmonyLib;

namespace SilkTronPlugin;

[HarmonyPatch]
public class PlayerDeathPatch
{
    [HarmonyPatch(typeof(HeroController), nameof(HeroController.Die))]
    [HarmonyPrefix]
    private static bool HeroController_Die(ref IEnumerator __result)
    {
        __result = EmptyCoroutine();
        return false;
    }

    [HarmonyPatch(typeof(GameManager), nameof(GameManager.PlayerDead))]
    [HarmonyPrefix]
    private static bool GameManager_PlayerDead(ref IEnumerator __result)
    {
        __result = EmptyCoroutine();
        return false;
    }

    private static IEnumerator EmptyCoroutine()
    {
        yield break;
    }
}