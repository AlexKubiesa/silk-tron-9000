using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using BepInEx;
using SilkTronPlugin.EpisodeManagement;

namespace SilkTronPlugin;

/// <summary>
/// Manual-mode tools for seeing and changing the progress flags the game keeps: PlayerData fields
/// and the per-scene persistent bools and ints (a defeated boss, a broken wall, ...).
///
/// Dump writes every flag to BepInEx/silktron_flags_dump.txt.
/// Apply reads BepInEx/silktron_flags.txt, one edit per line ('#' starts a comment):
///   player SomeField true
///   scene Belltown_Shrine Some Item Id false   (or an int value, for the scene's ints)
///   unscene Belltown_Shrine Some Item Id       (forget the entry, which puts it back to its default)
/// An item id may contain spaces, but not two in a row.
///
/// The game writes a scene's flags back from the objects in it when you leave it, which undoes an
/// edit to that scene's entries. Apply scene edits from a different room, then enter the scene.
/// </summary>
public static class FlagTools
{
    private const string DumpFileName = "silktron_flags_dump.txt";
    private const string EditFileName = "silktron_flags.txt";

    public static void Dump()
    {
        var sb = new StringBuilder();

        sb.AppendLine("# Scene persistent bools: scene / id = value");
        foreach (var line in Collect(SceneData.instance.PersistentBools))
            sb.AppendLine(line);

        sb.AppendLine("\n# Scene persistent ints: scene / id = value");
        foreach (var line in Collect(SceneData.instance.PersistentInts))
            sb.AppendLine(line);

        sb.AppendLine("\n# PlayerData bools: field = value");
        var playerData = PlayerData.instance;
        foreach (var field in PlayerDataBoolFields().OrderBy(f => f.Name))
            sb.AppendLine($"{field.Name} = {field.GetValue(playerData)}");

        var path = Path.Combine(Paths.BepInExRootPath, DumpFileName);
        File.WriteAllText(path, sb.ToString());
        Plugin.Logger.LogInfo($"Flags: wrote {path}");
    }

    public static void Apply()
    {
        var path = Path.Combine(Paths.BepInExRootPath, EditFileName);
        if (!File.Exists(path))
        {
            Plugin.Logger.LogWarning($"Flags: {path} does not exist.");
            return;
        }

        foreach (var rawLine in File.ReadAllLines(path))
        {
            var line = rawLine.Split('#')[0];
            var parts = line.Split((char[])null, System.StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length == 0)
                continue;

            if (parts[0] == "player" && parts.Length == 3 && bool.TryParse(parts[2], out var playerValue))
            {
                SetPlayerBool(parts[1], playerValue);
            }
            else if (parts[0] == "scene" && parts.Length >= 4)
            {
                SetSceneValue(parts[1], string.Join(" ", parts.Skip(2).Take(parts.Length - 3)), parts[parts.Length - 1]);
            }
            else if (parts[0] == "unscene" && parts.Length >= 3)
            {
                RemoveSceneEntry(parts[1], string.Join(" ", parts.Skip(2)));
            }
            else
            {
                Plugin.Logger.LogWarning($"Flags: cannot read line \"{rawLine}\"");
            }
        }
    }

    private static IEnumerable<FieldInfo> PlayerDataBoolFields()
    {
        return typeof(PlayerData)
            .GetFields(BindingFlags.Public | BindingFlags.Instance)
            .Where(f => f.FieldType == typeof(bool));
    }

    private static List<string> Collect<T, TContainer>(
        SceneData.PersistentItemDataCollection<T, TContainer> collection)
        where TContainer : SceneData.SerializableItemData<T>, new()
    {
        var lines = new List<string>();
        collection.Mutate(item => lines.Add($"{item.SceneName} / {item.ID} = {item.Value}"));
        lines.Sort();
        return lines;
    }

    private static void SetPlayerBool(string fieldName, bool value)
    {
        var field = PlayerDataBoolFields().FirstOrDefault(f => f.Name == fieldName);
        if (field == null)
        {
            Plugin.Logger.LogWarning($"Flags: PlayerData has no bool field {fieldName}");
            return;
        }

        var old = field.GetValue(PlayerData.instance);
        field.SetValue(PlayerData.instance, value);
        Plugin.Logger.LogInfo($"Flags: PlayerData.{fieldName} {old} -> {value}");
    }

    private static void SetSceneValue(string sceneName, string id, string text)
    {
        var found = false;

        if (bool.TryParse(text, out var boolValue))
        {
            SceneData.instance.PersistentBools.Mutate(item =>
            {
                if (item.SceneName != sceneName || item.ID != id)
                    return;
                Plugin.Logger.LogInfo($"Flags: {sceneName}/{id} {item.Value} -> {boolValue}");
                item.Value = boolValue;
                found = true;
            });
        }
        else if (int.TryParse(text, out var intValue))
        {
            SceneData.instance.PersistentInts.Mutate(item =>
            {
                if (item.SceneName != sceneName || item.ID != id)
                    return;
                Plugin.Logger.LogInfo($"Flags: {sceneName}/{id} {item.Value} -> {intValue}");
                item.Value = intValue;
                found = true;
            });
        }
        else
        {
            Plugin.Logger.LogWarning($"Flags: \"{text}\" is neither true, false nor an integer");
            return;
        }

        if (!found)
        {
            Plugin.Logger.LogWarning($"Flags: no entry {sceneName}/{id} to change. Use 'unscene' to reset one, or find the id in the dump.");
        }
    }

    private static void RemoveSceneEntry(string sceneName, string id)
    {
        if (ScenePersistence.RemoveEntry(sceneName, id))
        {
            Plugin.Logger.LogInfo($"Flags: removed entry {sceneName}/{id}");
        }
        else
        {
            Plugin.Logger.LogWarning($"Flags: no entry {sceneName}/{id} to remove");
        }
    }
}
