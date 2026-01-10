using System.Reflection;
using BepInEx;
using BepInEx.Logging;
using HarmonyLib;
using UnityEngine;

namespace SilkTronPlugin;

[BepInPlugin(MyPluginInfo.PLUGIN_GUID, MyPluginInfo.PLUGIN_NAME, MyPluginInfo.PLUGIN_VERSION)]
public class Plugin : BaseUnityPlugin
{
    public static Plugin Instance;
    public static bool IsReady = false;
    public static int InstanceId = 0;

    internal static new ManualLogSource Logger;

    private Harmony _harmony;

    private void Awake()
    {
        Instance = this;
        Logger = base.Logger;

        ParseCommandLineArgs();

        _harmony = new Harmony(MyPluginInfo.PLUGIN_GUID);
        _harmony.PatchAll();

        var stepModeManager = new GameObject("StepModeManager");
        DontDestroyOnLoad(stepModeManager);
        stepModeManager.AddComponent<StepModeManager>();

        var sharedMemoryManager = new GameObject("SharedMemoryManager");
        DontDestroyOnLoad(sharedMemoryManager);
        sharedMemoryManager.AddComponent<SharedMemoryManager>();

        var debugOverlayManager = new GameObject("DebugOverlayManager");
        DontDestroyOnLoad(debugOverlayManager);
        debugOverlayManager.AddComponent<DebugOverlayManager>();

        if (CommandLineArgs.Boss.Name == "Lace")
        {
            // TODO: RefreshProjectileCache takes 2 ms per call. Make it more efficient.
            var bossProjectileManager = new GameObject("BossProjectileManager");
            DontDestroyOnLoad(bossProjectileManager);
            bossProjectileManager.AddComponent<BossProjectileManager>();
        }

        var noFxManager = new GameObject("NoFxManager");
        DontDestroyOnLoad(noFxManager);
        noFxManager.AddComponent<NoFxManager>();

        Application.targetFrameRate = -1;
        QualitySettings.vSyncCount = 0;

        CheatManager.SceneEntryWait = 0f;
        CheatManager.DisableMusicSync = true;
        CheatManager.IsWorldRumbleDisabled = true;
        CheatManager.BoostModeActive = true;

        CameraShakeManager.ShakeSetting = CameraShakeManager.ShakeSettings.Off;
        VibrationManager.VibrationSetting = VibrationManager.VibrationSettings.Off;

        var backingField = typeof(ProjectBenchmark).GetField("<IsRunning>k__BackingField", BindingFlags.NonPublic | BindingFlags.Static);
        backingField?.SetValue(null, true);

        EpisodeResetter.Initialize();

        Logger.LogInfo($"Plugin {MyPluginInfo.PLUGIN_GUID} is loaded!");
    }

    private void ParseCommandLineArgs()
    {
        CommandLineArgs.Parse();
        InstanceId = CommandLineArgs.Id;
        ActionManager.IsAgentControlEnabled = !CommandLineArgs.Manual;
    }

    private void Start()
    {
        if (GameManager.instance != null && GameManager.instance.gameSettings != null)
        {
            GameManager.instance.gameSettings.particleEffectsLevel = 0;
        }
    }

    private void Update()
    {
        if (StepModeManager.Instance != null && StepModeManager.Instance.IsEnabled)
        {
            return;
        }

        if (CommandLineArgs.Manual)
        {
            Time.timeScale = 1.0f;
        }
        else
        {
            Time.timeScale = IsReady ? CommandLineArgs.TimeScale : 10.0f;
        }
    }
}
