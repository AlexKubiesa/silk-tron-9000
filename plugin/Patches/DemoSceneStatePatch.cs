using HarmonyLib;
using SilkTronPlugin.EpisodeManagement;

namespace SilkTronPlugin;

[HarmonyPatch]
public class DemoSceneStatePatch
{
    // The game writes each persistent item's state (e.g. "boss defeated") to SceneData while leaving
    // a scene, which is after the episode resetter asked for the scene to be reloaded. Undo that
    // straight afterwards so the reloaded scene starts a fresh fight. Bosses that need other changes to
    // that state have the resetter make them through ScenePersistence.AfterLevelStateSaved.
    [HarmonyPatch(typeof(GameManager), nameof(GameManager.SaveLevelState))]
    [HarmonyPostfix]
    private static void GameManager_SaveLevelState()
    {
        if (ScenePersistence.RestorePending)
        {
            ScenePersistence.Restore(CommandLineArgs.Boss.Scene);
        }

        ScenePersistence.AfterLevelStateSaved?.Invoke();
    }
}
