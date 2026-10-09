using System;

namespace SilkTronPlugin;

public static class CommandLineArgs
{
    public static int Id { get; private set; } = 0;
    public static float TimeScale { get; private set; } = 1.0f;
    public static bool Manual { get; private set; } = false;
    public static bool NoFx { get; private set; } = false;
    public static bool Demo { get; private set; } = false;
    public static bool PlayerHasClawline { get; private set; } = true;
    public static bool PlayerHasClingGrip { get; private set; } = true;
    public static bool PlayerHasDash { get; private set; } = true;
    public static bool PlayerHasDoubleJump { get; private set; } = true;
    public static bool PlayerHasDriftersCloak { get; private set; } = true;
    public static bool PlayerHasNeedleStrike { get; private set; } = true;
    public static bool PlayerHasSilkspear { get; private set; } = true;
    public static int PlayerHunterCrestVersion { get; private set; } = 3;
    public static int PlayerMaxHealth { get; private set; } = 9;
    public static int PlayerMaxSilk { get; private set; } = 18;
    public static int PlayerNeedleUpgrades { get; private set; } = 4;
    public static int PlayerSilkHearts { get; private set; } = 3;
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
            else if (args[i] == "--demo")
            {
                Demo = true;
                Plugin.Logger.LogInfo("Set Demo mode to true");
            }
            else if (args[i] == "--player-has-clawline" && i + 1 < args.Length)
            {
                if (bool.TryParse(args[i + 1], out bool hasClawline))
                {
                    PlayerHasClawline = hasClawline;
                    Plugin.Logger.LogInfo($"Set PlayerHasClawline to {PlayerHasClawline}");
                }
            }
            else if (args[i] == "--player-has-cling-grip" && i + 1 < args.Length)
            {
                if (bool.TryParse(args[i + 1], out bool hasClingGrip))
                {
                    PlayerHasClingGrip = hasClingGrip;
                    Plugin.Logger.LogInfo($"Set PlayerHasClingGrip to {PlayerHasClingGrip}");
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
            else if (args[i] == "--player-has-double-jump" && i + 1 < args.Length)
            {
                if (bool.TryParse(args[i + 1], out bool hasDoubleJump))
                {
                    PlayerHasDoubleJump = hasDoubleJump;
                    Plugin.Logger.LogInfo($"Set PlayerHasDoubleJump to {PlayerHasDoubleJump}");
                }
            }
            else if (args[i] == "--player-has-drifters-cloak" && i + 1 < args.Length)
            {
                if (bool.TryParse(args[i + 1], out bool hasDriftersCloak))
                {
                    PlayerHasDriftersCloak = hasDriftersCloak;
                    Plugin.Logger.LogInfo($"Set PlayerHasDriftersCloak to {PlayerHasDriftersCloak}");
                }
            }
            else if (args[i] == "--player-has-needle-strike" && i + 1 < args.Length)
            {
                if (bool.TryParse(args[i + 1], out bool hasNeedleStrike))
                {
                    PlayerHasNeedleStrike = hasNeedleStrike;
                    Plugin.Logger.LogInfo($"Set PlayerHasNeedleStrike to {PlayerHasNeedleStrike}");
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
            else if (args[i] == "--player-hunter-crest-version" && i + 1 < args.Length)
            {
                if (int.TryParse(args[i + 1], out int hunterCrestVersion))
                {
                    PlayerHunterCrestVersion = hunterCrestVersion;
                    Plugin.Logger.LogInfo($"Set PlayerHunterCrestVersion to {PlayerHunterCrestVersion}");
                }
            }
            else if (args[i] == "--player-max-health" && i + 1 < args.Length)
            {
                if (int.TryParse(args[i + 1], out int maxHealth))
                {
                    PlayerMaxHealth = maxHealth;
                    Plugin.Logger.LogInfo($"Set PlayerMaxHealth to {PlayerMaxHealth}");
                }
            }
            else if (args[i] == "--player-max-silk" && i + 1 < args.Length)
            {
                if (int.TryParse(args[i + 1], out int maxSilk))
                {
                    PlayerMaxSilk = maxSilk;
                    Plugin.Logger.LogInfo($"Set PlayerMaxSilk to {PlayerMaxSilk}");
                }
            }
            else if (args[i] == "--player-needle-upgrades" && i + 1 < args.Length)
            {
                if (int.TryParse(args[i + 1], out int needleUpgrades))
                {
                    PlayerNeedleUpgrades = needleUpgrades;
                    Plugin.Logger.LogInfo($"Set PlayerNeedleUpgrades to {PlayerNeedleUpgrades}");
                }
            }
            else if (args[i] == "--player-silk-hearts" && i + 1 < args.Length)
            {
                if (int.TryParse(args[i + 1], out int silkHearts))
                {
                    PlayerSilkHearts = silkHearts;
                    Plugin.Logger.LogInfo($"Set PlayerSilkHearts to {PlayerSilkHearts}");
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