using System.IO;
using System.Linq;
using System.Text;
using BepInEx;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace SilkTronPlugin;

/// <summary>
/// Writes every GameObject in the active scene, including inactive ones, to BepInEx/silktron_scene_dump.txt.
/// Each line is the object's name, then its position, its components, and the state of any PlayMaker FSM.
/// For finding a boss that is disabled until its fight starts, and what controls a gate or a bench.
/// </summary>
public static class SceneDump
{
    private const string DumpFileName = "silktron_scene_dump.txt";

    public static void Write()
    {
        var scene = SceneManager.GetActiveScene();
        var sb = new StringBuilder();
        sb.AppendLine($"# Scene {scene.name}. Objects marked [off] are inactive.");

        foreach (var root in scene.GetRootGameObjects())
        {
            Append(sb, root.transform, 0);
        }

        var path = Path.Combine(Paths.BepInExRootPath, DumpFileName);
        File.WriteAllText(path, sb.ToString());
        Plugin.Logger.LogInfo($"Scene dump: wrote {path}");
    }

    private static void Append(StringBuilder sb, Transform transform, int depth)
    {
        var gameObject = transform.gameObject;
        var position = transform.position;
        var components = gameObject.GetComponents<Component>()
            .Where(c => c != null && !(c is Transform))
            .Select(Describe);

        sb.Append(new string(' ', depth * 2));
        sb.Append(gameObject.name);
        sb.Append(gameObject.activeSelf ? "" : " [off]");
        sb.Append($" ({position.x:F1}, {position.y:F1})");
        sb.Append(" : ");
        sb.AppendLine(string.Join(", ", components));

        foreach (Transform child in transform)
        {
            Append(sb, child, depth + 1);
        }
    }

    private static string Describe(Component component)
    {
        if (component is PlayMakerFSM fsm)
        {
            try
            {
                return $"FSM {fsm.FsmName}={fsm.ActiveStateName}";
            }
            catch (System.Exception)
            {
                return $"FSM {fsm.FsmName}";
            }
        }

        if (component is BoxCollider2D box)
        {
            var scale = box.transform.lossyScale;
            var center = box.transform.TransformPoint(box.offset);
            return $"BoxCollider2D {box.size.x * scale.x:F1}x{box.size.y * scale.y:F1} at ({center.x:F1}, {center.y:F1})";
        }

        return component.GetType().Name;
    }
}
