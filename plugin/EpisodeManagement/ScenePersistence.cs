using System.Collections.Generic;
using System.Reflection;

namespace SilkTronPlugin.EpisodeManagement;

/// <summary>
/// The game remembers permanent changes (a defeated boss stays gone) in SceneData and PlayerData.
/// In demo mode the boss really dies, so those are put back to how they were at the start of the
/// fight before its scene is reloaded.
/// </summary>
public static class ScenePersistence
{
    private static Dictionary<string, bool> _bools;
    private static Dictionary<string, int> _ints;
    private static Dictionary<FieldInfo, bool> _playerDataBools;

    /// <summary>
    /// Set while a demo hard reset is leaving the boss scene, so <see cref="DemoSceneStatePatch"/>
    /// restores the entries each time the game saves the scene's state.
    /// </summary>
    public static bool RestorePending { get; set; }

    /// <summary>Remembers the scene's current entries. Only the first call has an effect.</summary>
    public static void CaptureOnce(string sceneName)
    {
        if (_bools != null)
            return;

        var data = SceneData.instance;
        _bools = Capture(data.PersistentBools, sceneName);
        _ints = Capture(data.PersistentInts, sceneName);
        Plugin.Logger.LogInfo($"Captured {_bools.Count + _ints.Count} persistent entries of {sceneName}");

        _playerDataBools = new Dictionary<FieldInfo, bool>();
        var playerData = PlayerData.instance;
        foreach (var field in typeof(PlayerData).GetFields(BindingFlags.Public | BindingFlags.Instance))
        {
            if (field.FieldType == typeof(bool))
                _playerDataBools[field] = (bool)field.GetValue(playerData);
        }
    }

    public static void Restore(string sceneName)
    {
        if (_bools == null)
            return;

        var data = SceneData.instance;
        Restore(data.PersistentBools, sceneName, _bools);
        Restore(data.PersistentInts, sceneName, _ints);

        var playerData = PlayerData.instance;
        foreach (var (field, original) in _playerDataBools)
        {
            if ((bool)field.GetValue(playerData) == original)
                continue;
            Plugin.Logger.LogInfo($"Restoring PlayerData.{field.Name} to {original}");
            field.SetValue(playerData, original);
        }
    }

    /// <summary>
    /// Forgets one of a scene's persistent entries, which puts it back to its default.
    /// Returns whether there was such an entry.
    /// </summary>
    public static bool RemoveEntry(string sceneName, string id)
    {
        var data = SceneData.instance;
        return RemoveEntry(data.PersistentBools, sceneName, id) || RemoveEntry(data.PersistentInts, sceneName, id);
    }

    private static bool RemoveEntry<T, TContainer>(
        SceneData.PersistentItemDataCollection<T, TContainer> collection, string sceneName, string id)
        where TContainer : SceneData.SerializableItemData<T>, new()
    {
        var found = false;
        collection.Mutate(item => found |= item.SceneName == sceneName && item.ID == id);
        if (found)
        {
            collection.Remove(sceneName, id);
        }

        return found;
    }

    private static Dictionary<string, T> Capture<T, TContainer>(
        SceneData.PersistentItemDataCollection<T, TContainer> collection, string sceneName)
        where TContainer : SceneData.SerializableItemData<T>, new()
    {
        var values = new Dictionary<string, T>();
        collection.Mutate(item =>
        {
            if (item.SceneName == sceneName)
                values[item.ID] = item.Value;
        });
        return values;
    }

    private static void Restore<T, TContainer>(
        SceneData.PersistentItemDataCollection<T, TContainer> collection, string sceneName,
        Dictionary<string, T> values)
        where TContainer : SceneData.SerializableItemData<T>, new()
    {
        var added = new List<string>();
        collection.Mutate(item =>
        {
            if (item.SceneName != sceneName)
                return;
            if (values.TryGetValue(item.ID, out var original))
                item.Value = original;
            else
                added.Add(item.ID);
        });

        // Entries created since the capture can't be removed while Mutate iterates.
        foreach (var id in added)
        {
            Plugin.Logger.LogInfo($"Removing persistent entry {sceneName}/{id}");
            collection.Remove(sceneName, id);
        }
    }
}
