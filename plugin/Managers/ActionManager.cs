using HarmonyLib;
using UnityEngine.InputSystem.Controls;

namespace SilkTronPlugin;

public class ActionManager
{
    public static bool IsLeftPressed { get; set; }
    public static bool IsRightPressed { get; set; }
    public static bool IsUpPressed { get; set; }
    public static bool IsDownPressed { get; set; }
    public static bool IsJumpPressed { get; set; }
    public static bool IsAttackPressed { get; set; }
    public static bool IsDashPressed { get; set; }
    public static bool IsClawlinePressed { get; set; }
    public static bool IsSkillPressed { get; set; }
    public static bool IsHealPressed { get; set; }

    public static bool IsAgentControlEnabled { get; set; } = false;

    public static void ResetInputs()
    {
        IsLeftPressed = false;
        IsRightPressed = false;
        IsUpPressed = false;
        IsDownPressed = false;
        IsJumpPressed = false;
        IsAttackPressed = false;
        IsDashPressed = false;
        IsClawlinePressed = false;
        IsSkillPressed = false;
        IsHealPressed = false;
    }
}

[HarmonyPatch(typeof(ButtonControl), nameof(ButtonControl.isPressed), MethodType.Getter)]
public static class ButtonControlPatch
{
    public static bool Prefix(ButtonControl __instance, ref bool __result)
    {
        string keyName = __instance.name;

        switch (keyName)
        {
            case "leftArrow":
                __result = ActionManager.IsLeftPressed;
                return false;
            case "rightArrow":
                __result = ActionManager.IsRightPressed;
                return false;
            case "upArrow":
                __result = ActionManager.IsUpPressed;
                return false;
            case "downArrow":
                __result = ActionManager.IsDownPressed;
                return false;
            case "z":
                __result = ActionManager.IsJumpPressed;
                return false;
            case "x":
                __result = ActionManager.IsAttackPressed;
                return false;
            case "c":
                __result = ActionManager.IsDashPressed;
                return false;
            case "s":
                __result = ActionManager.IsClawlinePressed;
                return false;
            case "f":
                __result = ActionManager.IsSkillPressed;
                return false;
            case "a":
                __result = ActionManager.IsHealPressed;
                return false;
        }

        return true;
    }
}