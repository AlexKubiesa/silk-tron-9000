namespace SilkTronPlugin;

/// <summary>
/// How a boss's phases are told apart: each phase after the first begins when the boss's main FSM
/// enters a state with a given name prefix.
/// </summary>
public class BossPhases(string phase2State, string phase3State)
{
    /// <summary>For bosses whose phases are not tracked. They stay in phase 0.</summary>
    public static readonly BossPhases None = new BossPhases(null, null);

    /// <summary>Prefix of the first FSM state of phase 2, or null if there is none.</summary>
    public string Phase2State { get; } = phase2State;

    /// <summary>Prefix of the first FSM state of phase 3, or null if there is none.</summary>
    public string Phase3State { get; } = phase3State;

    /// <summary>The phase (0 to 2) after the boss's FSM enters a state. A boss never goes back to an earlier phase.</summary>
    public int Advance(int currentPhase, string stateName)
    {
        if (currentPhase < 1 && Phase2State != null && stateName.StartsWith(Phase2State))
        {
            currentPhase = 1;
        }

        if (currentPhase < 2 && Phase3State != null && stateName.StartsWith(Phase3State))
        {
            currentPhase = 2;
        }

        return currentPhase;
    }
}
