namespace SilkTronPlugin;

public static class HandicapManager
{
    public static void ApplyHandicaps()
    {
        GameManager.instance.playerData.hasHarpoonDash = CommandLineArgs.PlayerHasClawline;
        GameManager.instance.playerData.hasDash = CommandLineArgs.PlayerHasDash;
        GameManager.instance.playerData.hasDoubleJump = CommandLineArgs.PlayerHasDoubleJump;
        GameManager.instance.playerData.hasBrolly = CommandLineArgs.PlayerHasDriftersCloak;
        // TODO: Disable Silkspear in game logic based on command-line arg.
    }
}
