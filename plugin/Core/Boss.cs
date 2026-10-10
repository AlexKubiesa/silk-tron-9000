using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace SilkTronPlugin;

public enum BossId
{
    Lace = 0,
    MossMother = 1,
    Widow = 2
}

public class Boss(
    BossId id,
    string hrid,
    string scene,
    string entryGate,
    Vector3 heroSpawnPosition,
    Vector3 bossSpawnPosition,
    int hp,
    BossPhases phases = null)
{
    private static readonly Boss[] Bosses =
    [
        new Boss(
            id: BossId.Lace,
            hrid: "Lace",
            scene: "Song_Tower_01",
            entryGate: "door_cutsceneEndLaceTower",
            heroSpawnPosition: new Vector3(49.27f, 100.5677f, 0f),
            bossSpawnPosition: new Vector3(59.19379f, 100.5931f, 0f),
            hp: 800,
            phases: new BossPhases(phase2State: "P2 Shift", phase3State: "P3 Roar")),
        new Boss(
            id: BossId.MossMother,
            hrid: "MossMother",
            scene: "Tut_03",
            entryGate: "right1",
            heroSpawnPosition: new Vector3(49.71f, 17.57f, 0f),
            bossSpawnPosition: new Vector3(54.77f, 25.76f, 0f),
            hp: 120),
        // The hero spawns in the centre of the arena's challenge region, so that arriving there starts the fight.
        // The boss spawn is where she waits, dormant, above the arena. WidowEpisodeResetter replaces it with where she is when the fight starts.
        // The phase states are the first states of the Control FSM's move choices for phases 2 and 3.
        new Boss(
            id: BossId.Widow,
            hrid: "Widow",
            scene: "Belltown_Shrine",
            entryGate: "top1",
            heroSpawnPosition: new Vector3(55.5f, 8.6f, 0f),
            bossSpawnPosition: new Vector3(57.01f, 52.01f, 0f),
            hp: 360,
            phases: new BossPhases(phase2State: "Move Choice P2", phase3State: "Move Choice P3"))
    ];

    private static readonly Dictionary<BossId, Boss> BossesById = Bosses.ToDictionary(boss => boss.Id);

    public static Boss GetById(BossId id)
    {
        return BossesById[id];
    }

    public static Boss GetByHrid(string hrid)
    {
        return Bosses.FirstOrDefault(boss => boss.Name == hrid);
    }

    public BossId Id { get; } = id;
    public string Name { get; } = hrid;
    public string Scene { get; } = scene;
    public string EntryGate { get; } = entryGate;
    public Vector3 HeroSpawnPosition { get; } = heroSpawnPosition;
    public Vector3 BossSpawnPosition { get; } = bossSpawnPosition;
    public int HP { get; } = hp;
    public BossPhases Phases { get; } = phases ?? BossPhases.None;
}
