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
        // Has clawline
        playerData.hasHarpoonDash = CommandLineArgs.PlayerHasClawline;

        // Has dash
        playerData.hasDash = CommandLineArgs.PlayerHasDash;

        // Has double jump
        playerData.hasDoubleJump = CommandLineArgs.PlayerHasDoubleJump;

        // Has drifter's cloak
        playerData.hasBrolly = CommandLineArgs.PlayerHasDriftersCloak;

        // Has needle strike
        playerData.hasChargeSlash = CommandLineArgs.PlayerHasNeedleStrike;

        // Has silkspear
        if (!CommandLineArgs.PlayerHasSilkspear)
        {
            string crest = playerData.CurrentCrestID;
            var toolCrestData = playerData.ToolEquips.GetData(crest);
            for (int i = 0; i < toolCrestData.Slots.Count; i++)
            {
                var slotData = toolCrestData.Slots[i];
                if (slotData.EquippedTool == "Silk Spear")
                {
                    slotData.EquippedTool = null;
                    // We need to assign slotData back to the list because it's a struct.
                    toolCrestData.Slots[i] = slotData;
                    break;
                }
            }
        }

        // Max health
        playerData.maxHealthBase = CommandLineArgs.PlayerMaxHealth;
        playerData.maxHealth = CommandLineArgs.PlayerMaxHealth;
        playerData.health = CommandLineArgs.PlayerMaxHealth;
        playerData.prevHealth = CommandLineArgs.PlayerMaxHealth;

        // Max silk
        playerData.silk = CommandLineArgs.PlayerMaxSilk;
        playerData.silkMax = CommandLineArgs.PlayerMaxSilk;

        // Nail upgrades
        playerData.nailUpgrades = CommandLineArgs.PlayerNeedleUpgrades;

        // Silk hearts
        playerData.silkRegenMax = CommandLineArgs.PlayerSilkHearts;
    }
}