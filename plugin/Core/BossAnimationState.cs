using System.Collections.Generic;
using System.Linq;

namespace SilkTronPlugin;

public class BossAnimationState(BossId bossId, int id, string clipName)
{
    public BossId BossId { get; } = bossId;
    public int Id { get; } = id;
    public string ClipName { get; } = clipName;
}

public class BossAnimationStates(
    BossId bossId,
    BossAnimationState[] knownStates,
    BossAnimationState idleState,
    BossAnimationState unknownState)
{
    public BossId BossId { get; } = bossId;
    public BossAnimationState[] KnownStates { get; } = knownStates;
    public BossAnimationState IdleState { get; } = idleState;
    public BossAnimationState UnknownState { get; } = unknownState;
}

public static class BossAnimationMapper
{
    private static readonly BossAnimationStates[] AnimationStates =
    [
        new BossAnimationStates(
            bossId: BossId.Lace,
            knownStates:
            [
                new BossAnimationState(BossId.Lace, 0, "Idle"),
                new BossAnimationState(BossId.Lace, 1, "Combo Slash"),
                new BossAnimationState(BossId.Lace, 2, "Antic"),
                new BossAnimationState(BossId.Lace, 3, "Rising Slash"),
                new BossAnimationState(BossId.Lace, 4, "Charge Antic"),
                new BossAnimationState(BossId.Lace, 5, "RapidSlash Charge"),
                new BossAnimationState(BossId.Lace, 6, "TurnToIdle"),
                new BossAnimationState(BossId.Lace, 7, "Counter Stance"),
                new BossAnimationState(BossId.Lace, 8, "Engarde"),
                new BossAnimationState(BossId.Lace, 9, "Evade"),
                new BossAnimationState(BossId.Lace, 10, "Forward Hop"),
                new BossAnimationState(BossId.Lace, 11, "NPC Idle Right"),
                new BossAnimationState(BossId.Lace, 12, "NPC Idle Turn Left"),
                new BossAnimationState(BossId.Lace, 13, "NPC Idle Left"),
                new BossAnimationState(BossId.Lace, 14, "NPC Idle Turn Right"),
                new BossAnimationState(BossId.Lace, 15, "Possession"),
                new BossAnimationState(BossId.Lace, 16, "Stun"),
                new BossAnimationState(BossId.Lace, 17, "Charge"),
                new BossAnimationState(BossId.Lace, 18, "Charge Recover"),
                new BossAnimationState(BossId.Lace, 19, "Downstab Antic"),
                new BossAnimationState(BossId.Lace, 20, "Downstab"),
                new BossAnimationState(BossId.Lace, 21, "Downstab End"),
                new BossAnimationState(BossId.Lace, 22, "Counter Antic"),
                new BossAnimationState(BossId.Lace, 23, "Counter End"),
                new BossAnimationState(BossId.Lace, 24, "Counter Hit"),
                new BossAnimationState(BossId.Lace, 25, "RapidSlash End"),
                new BossAnimationState(BossId.Lace, 26, "RapidSlash Loop"),
                new BossAnimationState(BossId.Lace, 27, "RapidSlash Effect"),
                new BossAnimationState(BossId.Lace, 28, "Jump Antic"),
                new BossAnimationState(BossId.Lace, 29, "Conduct"),
                new BossAnimationState(BossId.Lace, 30, "CrossSlash Antic"),
                new BossAnimationState(BossId.Lace, 31, "Conduct End"),
                new BossAnimationState(BossId.Lace, 32, "Stun Air"),
                new BossAnimationState(BossId.Lace, 33, "Stun Recover"),
                new BossAnimationState(BossId.Lace, 34, "Jump AnticQ"),
                new BossAnimationState(BossId.Lace, 35, "Jump Away"),
                new BossAnimationState(BossId.Lace, 36, "Eye Flash"),
                new BossAnimationState(BossId.Lace, 37, "MultiHit Slash"),
                new BossAnimationState(BossId.Lace, 38, "Pose Lean"),
                new BossAnimationState(BossId.Lace, 39, "Pose Upright"),
                new BossAnimationState(BossId.Lace, 40, "Pose Swish"),
                new BossAnimationState(BossId.Lace, 41, "Dash Burst"),
                new BossAnimationState(BossId.Lace, 42, "AirDash Burst"),
                new BossAnimationState(BossId.Lace, 43, "Stun Hit"),
                new BossAnimationState(BossId.Lace, 44, "Trap Stun"),
                new BossAnimationState(BossId.Lace, 45, "Pose Hornet Defeated"),
                new BossAnimationState(BossId.Lace, 46, "NPC Sit"),
                new BossAnimationState(BossId.Lace, 47, "Swish Block"),
                new BossAnimationState(BossId.Lace, 48, "ConductToIdle"),
                new BossAnimationState(BossId.Lace, 49, "NPC Sit Antic"),
                new BossAnimationState(BossId.Lace, 50, "NPC SitLook"),
                new BossAnimationState(BossId.Lace, 51, "SitToIdle"),
                new BossAnimationState(BossId.Lace, 52, "Combo Slash Q"),
                new BossAnimationState(BossId.Lace, 53, "Downstab Antic Q"),
                new BossAnimationState(BossId.Lace, 54, "Bomb Slash Antic"),
                new BossAnimationState(BossId.Lace, 55, "Bomb Slash"),
                new BossAnimationState(BossId.Lace, 56, "Fall"),
                new BossAnimationState(BossId.Lace, 57, "Land"),
                new BossAnimationState(BossId.Lace, 58, "Death 1"),
                new BossAnimationState(BossId.Lace, 59, "Death 2"),
                new BossAnimationState(BossId.Lace, 60, "Lie"),
                new BossAnimationState(BossId.Lace, 61, "LieToWake"),
                new BossAnimationState(BossId.Lace, 62, "Combo Slash Triple"),
                new BossAnimationState(BossId.Lace, 63, "P2 Shift Old"),
                new BossAnimationState(BossId.Lace, 64, "ChargeMulti Antic"),
                new BossAnimationState(BossId.Lace, 65, "ChargeMulti"),
                new BossAnimationState(BossId.Lace, 66, "ChargeMulti Recover"),
                new BossAnimationState(BossId.Lace, 67, "Rising Slash Multi"),
                new BossAnimationState(BossId.Lace, 68, "Roar"),
                new BossAnimationState(BossId.Lace, 69, "Death Stagger"),
                new BossAnimationState(BossId.Lace, 70, "Laugh"),
                new BossAnimationState(BossId.Lace, 71, "Tele In"),
                new BossAnimationState(BossId.Lace, 72, "Death Air"),
                new BossAnimationState(BossId.Lace, 73, "Death Land Stun"),
                new BossAnimationState(BossId.Lace, 74, "Tele Out"),
                new BossAnimationState(BossId.Lace, 75, "Wall Bounce"),
                new BossAnimationState(BossId.Lace, 76, "Charge Crossup"),
                new BossAnimationState(BossId.Lace, 77, "Quick Slash"),
                new BossAnimationState(BossId.Lace, 78, "RapidSlashAir TeleIn"),
                new BossAnimationState(BossId.Lace, 79, "RapidSlashAir"),
                new BossAnimationState(BossId.Lace, 80, "Sing"),
                new BossAnimationState(BossId.Lace, 81, "Sing End"),
                new BossAnimationState(BossId.Lace, 82, "RapidSlashAir End"),
                new BossAnimationState(BossId.Lace, 83, "Tele Out Fast"),
                new BossAnimationState(BossId.Lace, 84, "Counter Antic Fast"),
                new BossAnimationState(BossId.Lace, 85, "MultiHit Slash Air"),
                new BossAnimationState(BossId.Lace, 86, "Multihit AirEnd"),
                new BossAnimationState(BossId.Lace, 87, "P2 Shift"),
                new BossAnimationState(BossId.Lace, 88, "Mid Battle Roar"),
                new BossAnimationState(BossId.Lace, 89, "Counter Flash"),
                new BossAnimationState(BossId.Lace, 90, "RapidSlashAir End Q"),
                new BossAnimationState(BossId.Lace, 91, "Swish Block Long"),
                new BossAnimationState(BossId.Lace, 92, "Combo Strike 1"),
                new BossAnimationState(BossId.Lace, 93, "Combo Strike 2"),
                new BossAnimationState(BossId.Lace, 94, "Charge Strike"),
                new BossAnimationState(BossId.Lace, 95, "Downstab Strike"),
                new BossAnimationState(BossId.Lace, 96, "Downstab Followup"),
                new BossAnimationState(BossId.Lace, 97, "Forward Hop Intro"),
                new BossAnimationState(BossId.Lace, 98, "Combo Slash LongAntic"),
                new BossAnimationState(BossId.Lace, 99, "Forward Hop Slow"),
                new BossAnimationState(BossId.Lace, 100, "Lava Damage"),
                new BossAnimationState(BossId.Lace, 101, "Tele In Fast"),
            ],
            idleState: new BossAnimationState(BossId.Lace, 0, "Idle"),
            unknownState: new BossAnimationState(BossId.Lace, 102, "Unknown")
        ),

        new BossAnimationStates(
            bossId: BossId.MossMother,
            knownStates:
            [
                new BossAnimationState(BossId.MossMother, 0, "Antic"),
                new BossAnimationState(BossId.MossMother, 1, "Fly"),
                new BossAnimationState(BossId.MossMother, 2, "Charge"),
                new BossAnimationState(BossId.MossMother, 3, "Charge Recover"),
                new BossAnimationState(BossId.MossMother, 4, "Roar"),
                new BossAnimationState(BossId.MossMother, 5, "FlyUp"),
                new BossAnimationState(BossId.MossMother, 6, "Smash"),
                new BossAnimationState(BossId.MossMother, 7, "TurnToFly"),
                new BossAnimationState(BossId.MossMother, 8, "RoofAntic"),
                new BossAnimationState(BossId.MossMother, 9, "Gate Closed"),
                new BossAnimationState(BossId.MossMother, 10, "Gate Close"),
                new BossAnimationState(BossId.MossMother, 11, "Gate Open"),
                new BossAnimationState(BossId.MossMother, 12, "Stun"),
                new BossAnimationState(BossId.MossMother, 13, "Recover"),
                new BossAnimationState(BossId.MossMother, 14, "Stun Hit"),
                new BossAnimationState(BossId.MossMother, 15, "Gate Hit"),
            ],
            idleState: new BossAnimationState(BossId.MossMother, 1, "Fly"),
            unknownState: new BossAnimationState(BossId.MossMother, 16, "Unknown")
        )
    ];

    private static Dictionary<string, BossAnimationState> StatesByClipName;
    private static Dictionary<int, BossAnimationState> StatesById;
    private static BossAnimationState IdleState;
    private static BossAnimationState UnknownState;

    private static void Initialize()
    {
        if (StatesByClipName != null)
        {
            return;
        }

        var bossId = CommandLineArgs.Boss.Id;
        var bossAnimationStates = AnimationStates.First(s => s.BossId == bossId);

        StatesByClipName = bossAnimationStates.KnownStates.ToDictionary(state => state.ClipName);
        StatesById = bossAnimationStates.KnownStates.ToDictionary(state => state.Id);
        IdleState = bossAnimationStates.IdleState;
        UnknownState = bossAnimationStates.UnknownState;
    }

    public static BossAnimationState GetByClipName(string clipName)
    {
        Initialize();

        if (string.IsNullOrEmpty(clipName))
            return UnknownState;

        return StatesByClipName.TryGetValue(clipName, out var state) ? state : UnknownState;
    }

    public static BossAnimationState GetById(int id)
    {
        Initialize();
        return StatesById.TryGetValue(id, out var state) ? state : UnknownState;
    }

    public static BossAnimationState GetIdleState()
    {
        Initialize();
        return IdleState;
    }

    public static BossAnimationState GetUnknownState()
    {
        Initialize();
        return UnknownState;
    }
}