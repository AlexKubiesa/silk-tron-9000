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
        playerData.hasHarpoonDash = CommandLineArgs.PlayerHasClawline;
        playerData.hasWalljump = CommandLineArgs.PlayerHasClingGrip;
        playerData.hasDash = CommandLineArgs.PlayerHasDash;
        playerData.hasDoubleJump = CommandLineArgs.PlayerHasDoubleJump;
        playerData.hasBrolly = CommandLineArgs.PlayerHasDriftersCloak;
        playerData.hasChargeSlash = CommandLineArgs.PlayerHasNeedleStrike;
        ApplyHunterCrestVersion(playerData);
        // Must be applied after hunter crest version, to ensure Silkspear is removed from the correct crest.
        ApplyHasSilkspear(playerData);
        ApplyMaxHealth(playerData);
        ApplyMaxSilk(playerData);
        playerData.nailUpgrades = CommandLineArgs.PlayerNeedleUpgrades;
        playerData.silkRegenMax = CommandLineArgs.PlayerSilkHearts;
    }

    private static void ApplyHunterCrestVersion(PlayerData playerData)
    {
        string crestId = playerData.CurrentCrestID;
        if (crestId.StartsWith("Hunter"))
        {
            string newCrestId = GetHunterCrestId(CommandLineArgs.PlayerHunterCrestVersion);
            if (newCrestId != crestId)
            {
                Plugin.Logger.LogInfo($"Changing hunter crest from {crestId} to {newCrestId}");
                playerData.CurrentCrestID = newCrestId;
            }
        }
    }

    private static string GetHunterCrestId(int version) => version switch
    {
        1 => "Hunter",
        2 => "Hunter_v2",
        3 => "Hunter_v3",
        _ => throw new System.ArgumentOutOfRangeException($"Invalid hunter crest version: {version}"),
    };

    private static void ApplyHasSilkspear(PlayerData playerData)
    {
        if (!CommandLineArgs.PlayerHasSilkspear)
        {
            string crest = playerData.CurrentCrestID;
            var toolCrestData = playerData.ToolEquips.GetData(crest);
            for (int i = 0; i < toolCrestData.Slots.Count; i++)
            {
                var slotData = toolCrestData.Slots[i];
                if (slotData.EquippedTool == Constants.SilkspearToolName)
                {
                    slotData.EquippedTool = null;
                    // We need to assign slotData back to the list because it's a struct.
                    toolCrestData.Slots[i] = slotData;
                    break;
                }
            }
        }
    }

    private static void ApplyMaxHealth(PlayerData playerData)
    {
        playerData.maxHealthBase = CommandLineArgs.PlayerMaxHealth;
        playerData.maxHealth = CommandLineArgs.PlayerMaxHealth;
        playerData.health = CommandLineArgs.PlayerMaxHealth;
        playerData.prevHealth = CommandLineArgs.PlayerMaxHealth;
    }

    private static void ApplyMaxSilk(PlayerData playerData)
    {
        playerData.silk = CommandLineArgs.PlayerMaxSilk;
        playerData.silkMax = CommandLineArgs.PlayerMaxSilk;
    }
}