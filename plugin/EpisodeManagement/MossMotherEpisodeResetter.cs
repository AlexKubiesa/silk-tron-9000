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
}
