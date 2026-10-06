using System;
using System.Collections;
using UnityEngine;

namespace SilkTronPlugin;

public class StepModeManager : MonoBehaviour
{
    public static StepModeManager Instance { get; private set; }

    private bool isEnabled = false;
    private bool isSteppingFrame = false;

    public bool IsEnabled => isEnabled;
    public bool IsSteppingFrame => isSteppingFrame;

    private void Awake()
    {
        Instance = this;
    }

    public void EnableStepMode()
    {
        if (CommandLineArgs.Manual)
            return;

        isEnabled = true;
        // Advance game time by exactly one step's worth per frame, however long the frame took
        // in real time. Otherwise time spent waiting for Python leaks into the next step, so
        // steps get longer whenever the trainer is slow (e.g. with many instances).
        Time.captureDeltaTime = Time.fixedDeltaTime * Constants.FramesPerStep;
        Time.timeScale = 0f;
    }

    public void DisableStepMode()
    {
        isEnabled = false;
        Time.captureDeltaTime = 0f;
        Time.timeScale = CommandLineArgs.TimeScale;
    }

    public IEnumerator Step()
    {
        Plugin.Logger.LogDebug("Stepping one frame");
        isSteppingFrame = true;
        // With captureDeltaTime set, a time scale of 1 advances exactly FramesPerStep fixed updates.
        Time.timeScale = 1f;

        for (int i = 0; i < Constants.FramesPerStep; i++)
        {
            yield return new WaitForFixedUpdate();
        }

        Time.timeScale = 0f;
        SharedMemoryManager.Instance.WriteGameState();
        SharedMemoryManager.Instance.WriteState(StateType.Step);
        isSteppingFrame = false;
        Plugin.Logger.LogDebug("Finished stepping one frame");
    }
}