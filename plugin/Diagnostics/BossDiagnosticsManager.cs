using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using BepInEx;
using GlobalEnums;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace SilkTronPlugin;

/// <summary>
/// Manual-mode tooling for gathering what is needed to add a boss. Play the fight by hand
/// and this records what the agent's observation would see, then writes it to the BepInEx log.
///
/// F3: find the boss and log its scene, animation clips and FSMs.
/// F4: log what has been recorded since the last reset, and write the main FSM's state timeline to BepInEx/silktron_state_timeline.txt.
/// F5: clear the recorded data. It is also cleared on every scene load.
/// F6: jump to the scene named in BepInEx/silktron_jump.txt ("SceneName GateName", read when F6 is pressed).
/// F7: log the transition points (gates) of the current scene.
/// F8: write every progress flag to BepInEx/silktron_flags_dump.txt. F9: apply BepInEx/silktron_flags.txt (see FlagTools).
/// F11: hard reset the episode, as Python would. F12: soft reset it.
/// F10: write every GameObject in the scene, including inactive ones, to BepInEx/silktron_scene_dump.txt.
///
/// Every scene load also logs the gate the hero entered through and the scene's transition points.
/// Scene names can be listed without the game by running list_scenes.py.
/// </summary>
public class BossDiagnosticsManager : MonoBehaviour
{
    public static BossDiagnosticsManager Instance;

    private const string JumpFileName = "silktron_jump.txt";
    private const int FsmRefreshFrames = 30;
    private const int HazardSampleFrames = 5;
    private const int FindBossFrames = 60;
    // The hero is parked far off-screen while a scene loads.
    private const float MaxSaneCoordinate = 1000f;

    private class Extent
    {
        public float MinX = float.PositiveInfinity;
        public float MaxX = float.NegativeInfinity;
        public float MinY = float.PositiveInfinity;
        public float MaxY = float.NegativeInfinity;

        public bool HasData => MinX <= MaxX;

        public void Clear()
        {
            MinX = MinY = float.PositiveInfinity;
            MaxX = MaxY = float.NegativeInfinity;
        }

        public void Add(float x, float y)
        {
            MinX = Mathf.Min(MinX, x);
            MaxX = Mathf.Max(MaxX, x);
            MinY = Mathf.Min(MinY, y);
            MaxY = Mathf.Max(MaxY, y);
        }

        public override string ToString()
        {
            return HasData
                ? $"x [{MinX:F2}, {MaxX:F2}]  y [{MinY:F2}, {MaxY:F2}]"
                : "no data";
        }
    }

    private class ClipStats
    {
        public int Samples;
        public int ClipFrames;
    }

    private class HazardStats
    {
        public int Samples;
        public int MaxSimultaneous;
        public int Layer;
        public Vector2 Size;
        public bool UnderBoss;
    }

    private readonly Extent playerPos = new Extent();
    private readonly Extent bossPos = new Extent();
    private readonly Extent bossVelocity = new Extent();
    private int bossHpMin = int.MaxValue;
    private int bossHpMax = int.MinValue;
    private int bossFrames;
    private bool bossHasRigidbody;

    private readonly List<string> clipOrder = new List<string>();
    private readonly Dictionary<string, ClipStats> clips = new Dictionary<string, ClipStats>();

    private readonly List<string> fsmOrder = new List<string>();
    private readonly Dictionary<string, List<string>> fsmStates = new Dictionary<string, List<string>>();

    private const int MaxTimelineEntries = 20000;
    private const string TimelineFileName = "silktron_state_timeline.txt";

    private readonly List<string> timeline = new List<string>();
    private float timelineStart;

    private readonly Dictionary<string, HazardStats> hazards = new Dictionary<string, HazardStats>();

    private HealthManager variablesBoss;
    private Dictionary<string, string> initialVariables;

    private HealthManager fsmCacheBoss;
    private PlayMakerFSM[] fsmCache = new PlayMakerFSM[0];
    private int frame;

    private void Awake()
    {
        if (Instance != null && Instance != this)
        {
            Destroy(gameObject);
            return;
        }

        Instance = this;
        DontDestroyOnLoad(gameObject);
        SceneManager.sceneLoaded += OnSceneLoaded;
        Plugin.Logger.LogInfo("Boss diagnostics ready. F3: scan boss | F4: dump report | F5: reset tracking | F6: jump | F7: list gates | F8: dump flags | F9: apply flags | F10: dump scene | F11: hard reset | F12: soft reset");
    }

    private void Update()
    {
        if (Input.GetKeyDown(KeyCode.F3))
            LogScan();

        if (Input.GetKeyDown(KeyCode.F4))
            LogReport();

        if (Input.GetKeyDown(KeyCode.F5))
            ResetTracking();

        if (Input.GetKeyDown(KeyCode.F6))
            JumpToScene();

        if (Input.GetKeyDown(KeyCode.F7))
            LogTransitions();

        if (Input.GetKeyDown(KeyCode.F8))
            FlagTools.Dump();

        if (Input.GetKeyDown(KeyCode.F9))
            FlagTools.Apply();

        if (Input.GetKeyDown(KeyCode.F10))
            SceneDump.Write();

        if (Input.GetKeyDown(KeyCode.F11))
            GameManager.instance.StartCoroutine(EpisodeResetter.ResetEpisode());

        if (Input.GetKeyDown(KeyCode.F12))
            GameManager.instance.StartCoroutine(EpisodeResetter.SoftResetEpisode());

        Sample();
    }

    private void OnDestroy()
    {
        SceneManager.sceneLoaded -= OnSceneLoaded;

        if (Instance == this)
        {
            Instance = null;
        }
    }

    private void OnSceneLoaded(Scene scene, LoadSceneMode mode)
    {
        // What was recorded in another room says nothing about this one.
        ResetTracking();
        StartCoroutine(LogTransitionsNextFrame());
    }

    private IEnumerator LogTransitionsNextFrame()
    {
        // The scene's objects are not all there yet when it loads.
        yield return new WaitForEndOfFrame();
        LogTransitions();
    }

    private void JumpToScene()
    {
        var path = Path.Combine(Paths.BepInExRootPath, JumpFileName);
        if (!File.Exists(path))
        {
            Plugin.Logger.LogWarning($"Jump: {path} does not exist. Create it containing \"SceneName GateName\".");
            return;
        }

        var parts = File.ReadAllText(path).Split((char[])null, System.StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length == 0 || HeroController.instance == null || GameManager.instance == null)
        {
            Plugin.Logger.LogWarning($"Jump: {path} is empty, or the game is not ready.");
            return;
        }

        var gate = parts.Length > 1 ? parts[1] : "";
        Plugin.Logger.LogInfo($"Jump: loading {parts[0]} via gate \"{gate}\"");

        GameManager.instance.BeginSceneTransition(new GameManager.SceneLoadInfo
        {
            SceneName = parts[0],
            EntryGateName = gate,
            HeroLeaveDirection = GatePosition.unknown,
            EntryDelay = 0f,
            Visualization = GameManager.SceneLoadVisualizations.Default,
            AlwaysUnloadUnusedAssets = true,
        });
    }

    private static void LogTransitions()
    {
        var sb = new StringBuilder();
        sb.AppendLine("\n========== SCENE TRANSITIONS ==========");
        sb.AppendLine($"Scene: {SceneManager.GetActiveScene().name}");
        if (GameManager.instance != null)
        {
            sb.AppendLine($"Entered through gate: \"{GameManager.instance.entryGateName}\"");
        }

        if (HeroController.instance != null)
        {
            sb.AppendLine($"Hero position: {HeroController.instance.transform.position}");
        }

        sb.AppendLine("Gates (name at position -> leads to scene, arriving at gate):");
        foreach (var point in FindObjectsByType<TransitionPoint>(FindObjectsSortMode.None).OrderBy(p => p.name))
        {
            sb.AppendLine($"  {point.name} at {point.transform.position} -> {point.targetScene}, {point.entryPoint}");
        }

        sb.AppendLine("========== END SCENE TRANSITIONS ==========\n");
        Plugin.Logger.LogInfo(sb.ToString());
    }

    private void ResetTracking()
    {
        playerPos.Clear();
        bossPos.Clear();
        bossVelocity.Clear();
        bossHpMin = int.MaxValue;
        bossHpMax = int.MinValue;
        bossFrames = 0;
        clipOrder.Clear();
        clips.Clear();
        fsmOrder.Clear();
        fsmStates.Clear();
        hazards.Clear();
        timeline.Clear();
        timelineStart = Time.time;
        variablesBoss = null;
        initialVariables = null;
        Plugin.Logger.LogInfo("Boss diagnostics: tracking reset");
    }

    private void Sample()
    {
        frame++;

        var hero = HeroController.instance;
        if (hero != null && IsSane(hero.transform.position))
        {
            playerPos.Add(hero.transform.position.x, hero.transform.position.y);
        }

        var boss = BossStateManager.CurrentBoss;
        if (boss == null)
        {
            if (frame % FindBossFrames == 0)
            {
                BossStateManager.FindBoss(quiet: true);
            }

            return;
        }

        bossFrames++;
        bossPos.Add(boss.transform.position.x, boss.transform.position.y);
        bossHpMin = Mathf.Min(bossHpMin, boss.hp);
        bossHpMax = Mathf.Max(bossHpMax, boss.hp);

        // This is the velocity GameStateCollector gives the agent. Without a Rigidbody2D it is always zero.
        var rb = BossStateManager.CurrentBossRb;
        bossHasRigidbody = rb != null;
        if (rb != null)
        {
            bossVelocity.Add(rb.linearVelocity.x, rb.linearVelocity.y);
        }

        SampleClip(boss);
        SampleFsms(boss);

        if (variablesBoss != boss && BossStateManager.CurrentBossFsm != null)
        {
            variablesBoss = boss;
            initialVariables = SnapshotVariables(BossStateManager.CurrentBossFsm);
        }

        if (hero != null && frame % HazardSampleFrames == 0)
        {
            SampleHazards(boss, hero);
        }
    }

    /// <summary>Records a state entered by the boss's main FSM, with the boss's hp, for the timeline written by F4.</summary>
    public void RecordStateEntered(string stateName)
    {
        if (timeline.Count >= MaxTimelineEntries)
            return;

        var boss = BossStateManager.CurrentBoss;
        var hp = boss != null ? boss.hp : -1;
        var position = boss != null ? boss.transform.position : Vector3.zero;
        timeline.Add($"{Time.time - timelineStart:F2}s hp {hp} boss ({position.x:F1}, {position.y:F1}) {stateName}");
    }

    private static Dictionary<string, string> SnapshotVariables(PlayMakerFSM fsm)
    {
        var variables = new Dictionary<string, string>();
        var fsmVariables = fsm.FsmVariables;

        foreach (var variable in fsmVariables.BoolVariables)
            variables[$"bool {variable.Name}"] = variable.Value.ToString();
        foreach (var variable in fsmVariables.IntVariables)
            variables[$"int {variable.Name}"] = variable.Value.ToString();
        foreach (var variable in fsmVariables.FloatVariables)
            variables[$"float {variable.Name}"] = variable.Value.ToString("F2");
        foreach (var variable in fsmVariables.StringVariables)
            variables[$"string {variable.Name}"] = variable.Value;

        return variables;
    }

    private static bool IsSane(Vector3 position)
    {
        return Mathf.Abs(position.x) < MaxSaneCoordinate && Mathf.Abs(position.y) < MaxSaneCoordinate;
    }

    private void SampleClip(HealthManager boss)
    {
        var animator = boss.GetComponent<tk2dSpriteAnimator>();
        if (animator == null || animator.CurrentClip == null)
            return;

        var clip = animator.CurrentClip;
        if (!clips.TryGetValue(clip.name, out var stats))
        {
            stats = new ClipStats { ClipFrames = clip.frames != null ? clip.frames.Length : 0 };
            clips[clip.name] = stats;
            clipOrder.Add(clip.name);
        }

        stats.Samples++;
    }

    private void SampleFsms(HealthManager boss)
    {
        // Projectiles and other children come and go, so the FSM list is refreshed now and then.
        if (boss != fsmCacheBoss || frame % FsmRefreshFrames == 0)
        {
            fsmCacheBoss = boss;
            fsmCache = boss.GetComponentsInChildren<PlayMakerFSM>(true);
        }

        foreach (var fsm in fsmCache)
        {
            if (fsm == null)
                continue;

            try
            {
                var state = fsm.ActiveStateName;
                if (string.IsNullOrEmpty(state))
                    continue;

                var key = $"{fsm.FsmName} @ {RelativePath(fsm.transform, boss.transform)}";
                if (!fsmStates.TryGetValue(key, out var states))
                {
                    states = new List<string>();
                    fsmStates[key] = states;
                    fsmOrder.Add(key);
                }

                if (!states.Contains(state))
                {
                    states.Add(state);
                }
            }
            catch (System.Exception)
            {
                // The FSM has not been initialised yet.
            }
        }
    }

    private void SampleHazards(HealthManager boss, HeroController hero)
    {
        var simultaneous = new Dictionary<string, int>();

        foreach (var damageHero in FindObjectsByType<DamageHero>(FindObjectsSortMode.None))
        {
            if (damageHero == null || !damageHero.isActiveAndEnabled)
                continue;

            if (damageHero.transform.IsChildOf(hero.transform))
                continue;

            var collider = damageHero.GetComponent<Collider2D>();
            if (collider == null || !collider.enabled)
                continue;

            var parent = damageHero.transform.parent;
            var key = parent != null ? $"{parent.name}/{damageHero.name}" : damageHero.name;

            simultaneous[key] = simultaneous.TryGetValue(key, out var count) ? count + 1 : 1;

            if (!hazards.TryGetValue(key, out var stats))
            {
                stats = new HazardStats();
                hazards[key] = stats;
            }

            stats.Samples++;
            stats.Layer = damageHero.gameObject.layer;
            stats.Size = collider.bounds.size;
            stats.UnderBoss = damageHero.transform.IsChildOf(boss.transform);
        }

        foreach (var entry in simultaneous)
        {
            hazards[entry.Key].MaxSimultaneous = Mathf.Max(hazards[entry.Key].MaxSimultaneous, entry.Value);
        }
    }

    private void LogScan()
    {
        var sb = new StringBuilder();
        sb.AppendLine("\n========== BOSS SCAN ==========");

        sb.AppendLine($"Scene: {SceneManager.GetActiveScene().name}");
        if (HeroController.instance != null)
        {
            sb.AppendLine($"Hero position: {HeroController.instance.transform.position}");
        }

        BossStateManager.FindBoss();
        var boss = BossStateManager.CurrentBoss;

        sb.AppendLine("\n--- HealthManagers in scene (* = picked by BossStateManager.FindBoss, [off] = inactive) ---");
        foreach (var healthManager in FindObjectsByType<HealthManager>(FindObjectsInactive.Include, FindObjectsSortMode.None).OrderByDescending(hm => hm.hp))
        {
            var marker = healthManager == boss ? "*" : " ";
            var inactive = healthManager.gameObject.activeInHierarchy ? "" : " [off]";
            sb.AppendLine($"{marker} {healthManager.name}{inactive}: hp {healthManager.hp}, position {healthManager.transform.position}, layer {healthManager.gameObject.layer}");
        }

        if (boss == null)
        {
            sb.AppendLine("\nFindBoss picked nothing. It needs a name containing \"Boss\" or \"Lace\", or hp >= 100.");
            sb.AppendLine("========== END BOSS SCAN ==========\n");
            Plugin.Logger.LogInfo(sb.ToString());
            return;
        }

        sb.AppendLine($"\nBoss: {boss.name}, hp {boss.hp}, position {boss.transform.position}");
        sb.AppendLine($"Rigidbody2D: {(BossStateManager.CurrentBossRb != null ? "yes" : "NO - boss velocity observation will always be 0")}");

        LogAnimators(sb, boss);
        LogFsms(sb, boss);

        sb.AppendLine("========== END BOSS SCAN ==========\n");
        Plugin.Logger.LogInfo(sb.ToString());
    }

    private static void LogAnimators(StringBuilder sb, HealthManager boss)
    {
        sb.AppendLine("\n--- tk2dSpriteAnimators ---");

        var rootAnimator = boss.GetComponent<tk2dSpriteAnimator>();
        if (rootAnimator == null)
        {
            sb.AppendLine("WARNING: the boss has no tk2dSpriteAnimator on its root, so GameStateCollector will report Unknown for every frame.");
        }

        foreach (var animator in boss.GetComponentsInChildren<tk2dSpriteAnimator>(true))
        {
            var library = animator.Library;
            var clipCount = library != null && library.clips != null ? library.clips.Length : 0;
            var isRoot = animator == rootAnimator;
            sb.AppendLine($"{RelativePath(animator.transform, boss.transform)}{(isRoot ? " (root, read by GameStateCollector)" : "")}: {clipCount} clips");

            if (clipCount == 0)
                continue;

            if (!isRoot)
            {
                sb.AppendLine("  " + string.Join(", ", library.clips.Select(c => c.name)));
                continue;
            }

            var duplicates = library.clips.GroupBy(c => c.name).Where(g => g.Count() > 1).Select(g => g.Key).ToList();
            if (duplicates.Count > 0)
            {
                sb.AppendLine($"  WARNING: duplicate clip names (BossAnimationMapper's ToDictionary would throw): {string.Join(", ", duplicates)}");
            }

            sb.AppendLine("  Paste into BossAnimationMapper:");
            for (int i = 0; i < library.clips.Length; i++)
            {
                var clip = library.clips[i];
                var frames = clip.frames != null ? clip.frames.Length : 0;
                sb.AppendLine($"  new BossAnimationState(BossId.{CommandLineArgs.Boss.Id}, {i}, \"{clip.name}\"),  // {frames} frames, {clip.fps} fps");
            }

            sb.AppendLine($"  The unknown state would be id {library.clips.Length}. NUM_BOSS_ANIMATION_STATES in constants.py must be at least {library.clips.Length + 1}.");
        }
    }

    private static void LogFsms(StringBuilder sb, HealthManager boss)
    {
        sb.AppendLine("\n--- PlayMakerFSMs (all states) ---");

        foreach (var fsm in boss.GetComponentsInChildren<PlayMakerFSM>(true))
        {
            sb.AppendLine($"{fsm.FsmName} @ {RelativePath(fsm.transform, boss.transform)}");
            sb.AppendLine("  " + string.Join(", ", fsm.FsmStates.Select(s => s.Name)));
        }
    }

    private void LogReport()
    {
        var sb = new StringBuilder();
        sb.AppendLine("\n========== BOSS DIAGNOSTICS REPORT ==========");
        sb.AppendLine($"Scene: {SceneManager.GetActiveScene().name}");
        sb.AppendLine($"Frames with a boss: {bossFrames}");

        sb.AppendLine("\n--- Extents of HeroController/boss transform positions since the last reset (F5, or a scene load) ---");
        sb.AppendLine("To measure an arena: stand in it, press F5, walk to each corner and jump, then press F4.");
        sb.AppendLine($"Player position: {playerPos}");
        sb.AppendLine($"Boss position:   {bossPos}");
        sb.AppendLine($"Boss velocity:   {bossVelocity}{(bossFrames > 0 && !bossHasRigidbody ? "  (boss has no Rigidbody2D, so this is not recorded)" : "")}");
        if (bossHpMin <= bossHpMax)
        {
            sb.AppendLine($"Boss hp: {bossHpMin} to {bossHpMax} (the highest value seen is the max hp if you have not hit it yet)");
        }

        sb.AppendLine("\n--- Boss animation clips seen (name: samples, clip frames) ---");
        foreach (var name in clipOrder)
        {
            sb.AppendLine($"{name}: {clips[name].Samples}, {clips[name].ClipFrames}");
        }

        sb.AppendLine("\n--- Boss FSM states seen, in order of first appearance ---");
        foreach (var key in fsmOrder)
        {
            sb.AppendLine($"{key}");
            sb.AppendLine("  " + string.Join(" > ", fsmStates[key]));
        }

        sb.AppendLine("\n--- DamageHero objects with an enabled collider (candidate projectiles and hazards) ---");
        sb.AppendLine("name: samples, max at once, layer, collider size, [child of boss]");
        foreach (var entry in hazards.OrderBy(e => e.Value.Samples))
        {
            var stats = entry.Value;
            sb.AppendLine($"{entry.Key}: {stats.Samples}, {stats.MaxSimultaneous}, {stats.Layer}, {stats.Size.x:F1}x{stats.Size.y:F1}{(stats.UnderBoss ? ", child of boss" : "")}");
        }

        sb.AppendLine("\n--- Main FSM variables that differ from when the boss was first seen (name: first -> now) ---");
        if (initialVariables != null && BossStateManager.CurrentBossFsm != null)
        {
            foreach (var entry in SnapshotVariables(BossStateManager.CurrentBossFsm).OrderBy(e => e.Key))
            {
                if (initialVariables.TryGetValue(entry.Key, out var first) && first != entry.Value)
                {
                    sb.AppendLine($"{entry.Key}: {first} -> {entry.Value}");
                }
            }
        }

        var timelinePath = Path.Combine(Paths.BepInExRootPath, TimelineFileName);
        File.WriteAllLines(timelinePath, timeline);
        sb.AppendLine($"\nEvery state the main FSM entered, with the boss's hp ({timeline.Count} entries): {timelinePath}");

        sb.AppendLine("========== END BOSS DIAGNOSTICS REPORT ==========\n");
        Plugin.Logger.LogInfo(sb.ToString());
    }

    private static string RelativePath(Transform transform, Transform root)
    {
        if (transform == root)
            return ".";

        var parts = new List<string>();
        for (var current = transform; current != null && current != root; current = current.parent)
        {
            parts.Add(current.name);
        }

        parts.Reverse();
        return string.Join("/", parts);
    }
}
