using UnityEngine;

namespace SilkTronPlugin;

/// <summary>
/// Replacement for Unity's unscaled/real-time clocks, used by game code via <see cref="RealtimePatcher"/>.
/// Outside step mode it follows real time. In step mode it advances exactly like the game clock, so
/// anything the game times in real seconds (input buffering, realtime FSM waits, realtime animations)
/// doesn't depend on how long the trainer takes between steps.
/// </summary>
public static class StepClock
{
    // How far the virtual clock lags behind Unity's unscaled clock.
    private static double offset;
    private static int lastSyncedFrame = -1;

    private static bool InStepMode => StepModeManager.Instance != null && StepModeManager.Instance.IsEnabled;

    /// <summary>
    /// Accounts for the current frame. Runs lazily on first use each frame, and is also called every
    /// frame by <see cref="StepModeManager"/> so no frame is missed.
    /// </summary>
    public static void Sync()
    {
        int frame = Time.frameCount;
        if (frame == lastSyncedFrame)
            return;
        lastSyncedFrame = frame;

        if (InStepMode)
        {
            // This frame should advance the virtual clock by the game time it simulated, not by the
            // real time it took.
            offset += Time.unscaledDeltaTime - Time.deltaTime;
        }
    }

    public static float UnscaledDeltaTime
    {
        get
        {
            Sync();
            return InStepMode ? Time.deltaTime : Time.unscaledDeltaTime;
        }
    }

    public static double UnscaledTimeAsDouble
    {
        get
        {
            Sync();
            return Time.unscaledTimeAsDouble - offset;
        }
    }

    public static float UnscaledTime => (float)UnscaledTimeAsDouble;

    public static double RealtimeSinceStartupAsDouble
    {
        get
        {
            Sync();
            // In step mode real time is frozen within a frame (like game time), since real time spent
            // inside a frame includes waiting for the trainer.
            return (InStepMode ? Time.unscaledTimeAsDouble : Time.realtimeSinceStartupAsDouble) - offset;
        }
    }

    public static float RealtimeSinceStartup => (float)RealtimeSinceStartupAsDouble;
}
