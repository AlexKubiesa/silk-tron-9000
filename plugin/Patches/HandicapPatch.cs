using HarmonyLib;

namespace SilkTronPlugin.Patches;

[HarmonyPatch]
public static class HandicapPatch
{
    [HarmonyPatch(typeof(GameManager), nameof(GameManager.GetLoadedSaveSlotData))]
    [HarmonyPostfix]
    public static void GameManager_GetLoadedSaveSlotData_Postfix(SaveStats __result)
    {
        SetHandicaps(__result);
    }

    [HarmonyPatch(typeof(GameManager), nameof(GameManager.SetLoadedGameData), [typeof(SaveGameData), typeof(int)])]
    [HarmonyPostfix]
    public static void GameManager_SetLoadedGameData_Postfix(SaveGameData saveGameData, int saveSlot)
    {
        SetHandicaps(saveGameData.playerData);
    }

    private static void SetHandicaps(SaveStats saveStats)
    {
        SetHandicaps(saveStats.saveGameData);
        saveStats.MaxHealth = CommandLineArgs.PlayerMaxHealth;
    }

    private static void SetHandicaps(SaveGameData saveGameData)
    {
        SetHandicaps(saveGameData.playerData);
    }

    private static void SetHandicaps(PlayerData playerData)
    {
        playerData.maxHealthBase = CommandLineArgs.PlayerMaxHealth;
        playerData.maxHealth = CommandLineArgs.PlayerMaxHealth;
        playerData.health = CommandLineArgs.PlayerMaxHealth;
        playerData.prevHealth = CommandLineArgs.PlayerMaxHealth;
    }
}