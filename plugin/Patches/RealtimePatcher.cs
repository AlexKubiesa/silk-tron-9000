using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using HarmonyLib;
using UnityEngine;

namespace SilkTronPlugin;

/// <summary>
/// Redirects every read of Unity's unscaled/real-time clocks in the game's code to <see cref="StepClock"/>.
/// Found by scanning method IL, since the game reads these clocks in ~90 files (input, FSMs, animation, UI).
/// </summary>
public static class RealtimePatcher
{
    private static readonly string[] TargetAssemblyPrefixes =
    {
        "Assembly-CSharp", "PlayMaker", "TeamCherry.",
    };

    private static readonly Dictionary<MethodInfo, MethodInfo> Replacements = new()
    {
        [AccessTools.PropertyGetter(typeof(Time), nameof(Time.unscaledDeltaTime))] =
            AccessTools.PropertyGetter(typeof(StepClock), nameof(StepClock.UnscaledDeltaTime)),
        [AccessTools.PropertyGetter(typeof(Time), nameof(Time.unscaledTime))] =
            AccessTools.PropertyGetter(typeof(StepClock), nameof(StepClock.UnscaledTime)),
        [AccessTools.PropertyGetter(typeof(Time), nameof(Time.unscaledTimeAsDouble))] =
            AccessTools.PropertyGetter(typeof(StepClock), nameof(StepClock.UnscaledTimeAsDouble)),
        [AccessTools.PropertyGetter(typeof(Time), nameof(Time.realtimeSinceStartup))] =
            AccessTools.PropertyGetter(typeof(StepClock), nameof(StepClock.RealtimeSinceStartup)),
        [AccessTools.PropertyGetter(typeof(Time), nameof(Time.realtimeSinceStartupAsDouble))] =
            AccessTools.PropertyGetter(typeof(StepClock), nameof(StepClock.RealtimeSinceStartupAsDouble)),
    };

    private const byte CallOpcode = 0x28;

    public static void Apply(Harmony harmony)
    {
        var stopwatch = Stopwatch.StartNew();
        var transpiler = new HarmonyMethod(typeof(RealtimePatcher), nameof(Transpiler));

        var methods = AppDomain.CurrentDomain.GetAssemblies()
            .Where(a => TargetAssemblyPrefixes.Any(p => a.GetName().Name.StartsWith(p)))
            .SelectMany(AccessTools.GetTypesFromAssembly)
            .Where(t => !t.ContainsGenericParameters)
            .SelectMany(GetPatchableMethods)
            // Unity's own realtime wait, used by many game coroutines.
            .Append(AccessTools.PropertyGetter(typeof(WaitForSecondsRealtime), nameof(WaitForSecondsRealtime.keepWaiting)))
            .Where(ReadsRealtimeClock)
            .ToList();

        int failed = 0;
        foreach (var method in methods)
        {
            try
            {
                harmony.Patch(method, transpiler: transpiler);
            }
            catch (Exception e)
            {
                failed++;
                Plugin.Logger.LogWarning($"Could not redirect real-time clock in {method.DeclaringType}.{method.Name}: {e.Message}");
            }
        }

        Plugin.Logger.LogInfo($"Redirected real-time clock reads in {methods.Count - failed} methods ({failed} failed) in {stopwatch.ElapsedMilliseconds} ms");
    }

    private static IEnumerable<MethodBase> GetPatchableMethods(Type type)
    {
        const BindingFlags flags = BindingFlags.DeclaredOnly | BindingFlags.Public | BindingFlags.NonPublic |
                                   BindingFlags.Instance | BindingFlags.Static;
        return type.GetMethods(flags).Cast<MethodBase>()
            .Concat(type.GetConstructors(flags))
            .Where(m => !m.IsAbstract && !m.ContainsGenericParameters);
    }

    private static bool ReadsRealtimeClock(MethodBase method)
    {
        byte[] il;
        try
        {
            il = method.GetMethodBody()?.GetILAsByteArray();
        }
        catch
        {
            return false;
        }
        if (il == null)
            return false;

        // Cheap byte scan for "call <token>"; resolving the token filters out false matches.
        for (int i = 0; i + 4 < il.Length; i++)
        {
            if (il[i] != CallOpcode)
                continue;
            int token = BitConverter.ToInt32(il, i + 1);
            if (ResolvesToClockGetter(method.Module, token))
                return true;
        }
        return false;
    }

    private static readonly Dictionary<(Module, int), bool> TokenCache = new();

    private static bool ResolvesToClockGetter(Module module, int token)
    {
        if (TokenCache.TryGetValue((module, token), out bool result))
            return result;

        try
        {
            result = module.ResolveMethod(token) is MethodInfo m && Replacements.ContainsKey(m);
        }
        catch
        {
            result = false;
        }
        TokenCache[(module, token)] = result;
        return result;
    }

    private static IEnumerable<CodeInstruction> Transpiler(IEnumerable<CodeInstruction> instructions)
    {
        foreach (var instruction in instructions)
        {
            if (instruction.opcode == OpCodes.Call && instruction.operand is MethodInfo m &&
                Replacements.TryGetValue(m, out var replacement))
            {
                instruction.operand = replacement;
            }
            yield return instruction;
        }
    }
}
