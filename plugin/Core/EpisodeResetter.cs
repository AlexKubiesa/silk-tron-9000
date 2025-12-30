using System.Collections;
using SilkTronPlugin.EpisodeManagement;

namespace SilkTronPlugin;

public static class EpisodeResetter
{
    private static EpisodeResetterBase _instance;

    public static bool IsInitialStateCaptured => _instance.IsInitialStateCaptured;

    /// <summary>
    /// Initializes the EpisodeResetter facade based on the selected boss in command
    /// line arguments. Must be called after CommandLineArgs.Parse().
    /// </summary>
    public static void Initialize()
    {
        switch (CommandLineArgs.Boss.Name)
        {
            case "Lace":
                _instance = new LaceEpisodeResetter();
                break;
            case "Moss Mother":
                _instance = new MossMotherEpisodeResetter();
                break;
            default:
                Plugin.Logger.LogError($"No EpisodeResetter found for boss {CommandLineArgs.Boss.Name}");
                break;
        }
    }

    public static void CaptureInitialState() => _instance.CaptureInitialState();

    public static IEnumerator SoftResetEpisode() => _instance.SoftResetEpisode();

    public static IEnumerator ResetEpisode() => _instance.ResetEpisode();
}