using System.Collections.Generic;
using UnityEngine;

namespace SilkTronPlugin;

public class Boss(
    string name,
    string scene,
    string entryGate,
    Vector3 heroSpawnPosition,
    Vector3 bossSpawnPosition,
    int hp)
{
    public static Dictionary<string, Boss> Bosses = new()
    {
        {
            "Lace",
            new Boss(
                name: "Lace",
                scene: "Song_Tower_01",
                entryGate: "door_cutsceneEndLaceTower",
                heroSpawnPosition: new Vector3(49.27f, 100.5677f, 0f),
                bossSpawnPosition: new Vector3(59.19379f, 100.5931f, 0f),
                hp: 800)
        },
        {
            "MossMother",
            new Boss(
                name: "MossMother",
                scene: "Tut_03",
                entryGate: "right1",
                heroSpawnPosition: new Vector3(49.71f, 17.57f, 0f),
                bossSpawnPosition: new Vector3(54.77f, 0f, 0f),
                hp: 120)
        }
    };

    public string Name { get; } = name;
    public string Scene { get; } = scene;
    public string EntryGate { get; } = entryGate;
    public Vector3 HeroSpawnPosition { get; } = heroSpawnPosition;
    public Vector3 BossSpawnPosition { get; } = bossSpawnPosition;
    public int HP { get; } = hp;
}
