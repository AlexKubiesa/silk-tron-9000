using System;

namespace SilkTronPlugin;

public static class CommandLineArgs
{
    public static int Id { get; private set; } = 0;
    public static float TimeScale { get; private set; } = 1.0f;
    public static bool Manual { get; private set; } = false;
    public static bool NoFx { get; private set; } = false;
    public static bool PlayerHasClawline { get; private set; } = true;
    public static bool PlayerHasDash { get; private set; } = true;
    public static bool PlayerHasSilkspear { get; private set; } = true;
    public static Boss Boss { get; private set; } = Boss.GetById(BossId.Lace);

    public static void Parse()
    {
        var args = Environment.GetCommandLineArgs();
        for (int i = 0; i < args.Length; i++)
        {
            if (args[i] == "--id" && i + 1 < args.Length)
            {
                if (int.TryParse(args[i + 1], out int id))
                {
                    Id = id;
                    Plugin.Logger.LogInfo($"Set Instance ID to {Id}");
                }
            }
            else if (args[i] == "--time-scale" && i + 1 < args.Length)
            {
                if (float.TryParse(args[i + 1], out float timeScale))
                {
                    TimeScale = timeScale;
                    Plugin.Logger.LogInfo($"Set Time Scale to {TimeScale}");
                }
            }
            else if (args[i] == "--manual")
            {
                Manual = true;
                Plugin.Logger.LogInfo("Set Manual mode to true");
            }
            else if (args[i] == "--no-fx")
            {
                NoFx = true;
                Plugin.Logger.LogInfo("Set NoFx mode to true");
            }
            else if (args[i] == "--player-has-clawline" && i + 1 < args.Length)
            {
                if (bool.TryParse(args[i + 1], out bool hasClawline))
                {
                    PlayerHasClawline = hasClawline;
                    Plugin.Logger.LogInfo($"Set PlayerHasClawline to {PlayerHasClawline}");
                }
            }
            else if (args[i] == "--player-has-dash" && i + 1 < args.Length)
            {
                if (bool.TryParse(args[i + 1], out bool hasDash))
                {
                    PlayerHasDash = hasDash;
                    Plugin.Logger.LogInfo($"Set PlayerHasDash to {PlayerHasDash}");
                }
            }
            else if (args[i] == "--player-has-silkspear" && i + 1 < args.Length)
            {
                if (bool.TryParse(args[i + 1], out bool hasSilkspear))
                {
                    PlayerHasSilkspear = hasSilkspear;
                    Plugin.Logger.LogInfo($"Set PlayerHasSilkspear to {PlayerHasSilkspear}");
                }
            }
            else if (args[i] == "--boss" && i + 1 < args.Length)
            {
                var boss = Boss.GetByHrid(args[i + 1]);
                if (boss != null)
                {
                    Boss = boss;
                    Plugin.Logger.LogInfo($"Set Boss to {boss.Name}");
                }
            }
        }
    }
}