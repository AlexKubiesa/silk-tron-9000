using UnityEngine;

namespace SilkTronPlugin.EpisodeManagement;

public class MossMotherEpisodeResetter : EpisodeResetterBase
{
    protected override void OnPlayerAcceptingInput()
    {
        // Destroying the moss vine clusters removes the fog of war from the Moss Mother room.
        Object.Destroy(GameObject.Find("Moss Vine Cluster"));
        Object.Destroy(GameObject.Find("Moss Vine Cluster (1)"));
    }

    protected override void ResetPlayerData()
    {
        base.ResetPlayerData();
        HeroController.instance.playerData.defeatedMossMother = false;
    }

    protected override void ResetAllBossFsms(HealthManager boss)
    {
        base.ResetAllBossFsms(boss);

        foreach (var fsm in boss.GetComponentsInChildren<PlayMakerFSM>(true))
        {
            // In the game's code, Moss Mother is called "Mossbone Mother".
            if (fsm.FsmName == "Control" && fsm.gameObject.name == "Mossbone Mother")
            {
                // When soft-resetting, Moss Mother can get stuck in the "Slam RePos" state.
                fsm.SetState("Idle");
            }
        }
    }
}
