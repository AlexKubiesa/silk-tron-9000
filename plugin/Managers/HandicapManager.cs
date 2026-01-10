namespace SilkTronPlugin;

public static class HandicapManager
{
    public static void ApplyHandicaps()
    {
        GameManager.instance.playerData.hasHarpoonDash = CommandLineArgs.PlayerHasClawline;
    }
}
