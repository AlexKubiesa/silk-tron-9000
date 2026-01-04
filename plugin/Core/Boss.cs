using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace SilkTronPlugin;

public enum BossId
{
    Lace = 0,
    MossMother = 1
}

public class Boss(
    BossId id,
    string hrid,
    string scene,
    string entryGate,
    Vector3 heroSpawnPosition,
    Vector3 bossSpawnPosition,
    int hp)
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
            hp: 800),
        new Boss(
            id: BossId.MossMother,
            hrid: "MossMother",
            scene: "Tut_03",
            entryGate: "right1",
            heroSpawnPosition: new Vector3(49.71f, 17.57f, 0f),
            bossSpawnPosition: new Vector3(54.77f, 25.76f, 0f),
            hp: 120)
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
}
