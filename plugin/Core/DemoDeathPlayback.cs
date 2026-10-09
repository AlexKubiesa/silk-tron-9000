using System.Collections;
using HarmonyLib;
using UnityEngine;

namespace SilkTronPlugin;

/// <summary>
/// In demo mode (--demo) the player and boss death animations play out instead of being skipped.
/// The agent's reset is held back until they finish.
///
/// The boss dies for real, so its scene is reloaded afterwards (see <see cref="ScenePersistence"/>).
/// The player's death is only a visual replica: the game's own death sequence saves the game and
/// zeroes silk, so it stays blocked.
/// </summary>
public static class DemoDeathPlayback
{
    // Real-time (not game-time) caps, so a death that never finishes can't hang the reset.
    private const float BossDeathTimeoutSeconds = 10f;
    private const float BossDeathLingerSeconds = 2f;
    private const float PlayerDeathTimeoutSeconds = 10f;

    private static readonly System.Reflection.FieldInfo HeroRendererField =
        AccessTools.Field(typeof(HeroController), "renderer");
    private static readonly System.Reflection.MethodInfo GetHeroDeathPrefabMethod =
        AccessTools.Method(typeof(HeroController), "GetHeroDeathPrefab");

    public static bool PlayerDied { get; private set; }
    public static bool BossDied { get; private set; }
    private static bool _playerDeathActive;

    public static void MarkBossDied()
    {
        BossDied = true;
    }

    /// <summary>Replacement for the game's HeroController.Die: shows the death without its side effects.</summary>
    public static IEnumerator PlayerDeath(HeroController hero)
    {
        if (_playerDeathActive)
            yield break;

        _playerDeathActive = true;
        PlayerDied = true;

        var renderer = HeroRendererField?.GetValue(hero) as Renderer;
        GameObject deathObject = null;
        float deathWait = 4f;
        try
        {
            var prefab = GetHeroDeathPrefabMethod?.Invoke(hero, new object[] { false, false, false }) as GameObject;
            if (prefab != null)
            {
                deathObject = prefab.Spawn();
                deathObject.transform.position = hero.transform.position;
                deathObject.transform.localScale =
                    hero.transform.localScale.MultiplyElements(prefab.transform.localScale);
                deathObject.SetActive(true);

                var animator = deathObject.GetComponent<tk2dSpriteAnimator>();
                if (animator != null)
                    animator.Library = hero.GetComponent<HeroAnimationController>().animator.Library;

                var sequence = deathObject.GetComponent<HeroDeathSequence>();
                if (sequence != null)
                    deathWait = sequence.DeathWait;
            }

            if (renderer != null)
                renderer.enabled = false;
        }
        catch (System.Exception e)
        {
            Plugin.Logger.LogWarning($"Could not start the player death animation: {e}");
        }

        yield return new WaitForSeconds(deathWait);

        try
        {
            if (renderer != null)
                renderer.enabled = true;
            if (deathObject != null)
                deathObject.Recycle();
        }
        finally
        {
            _playerDeathActive = false;
        }
    }

    /// <summary>
    /// Waits for any death animation started this episode to finish. Call after leaving step mode,
    /// when the game runs in real time. Afterwards <see cref="BossDied"/> says whether the boss
    /// really died, in which case the episode needs a hard reset.
    /// </summary>
    public static IEnumerator PlayOut()
    {
        if (!PlayerDied && !BossDied)
            yield break;

        var hero = HeroController.instance;
        ActionManager.ResetInputs();
        if (hero != null)
        {
            // Nothing else may hurt the hero while the animations run.
            hero.damageMode = GlobalEnums.DamageMode.NO_DAMAGE;
            hero.playerData.isInvincible = true;
        }

        var boss = BossStateManager.CurrentBoss;
        float deadline = Time.realtimeSinceStartup + BossDeathTimeoutSeconds;
        if (BossDied)
        {
            while (boss != null && boss.gameObject.activeInHierarchy && Time.realtimeSinceStartup < deadline)
                yield return null;
            yield return new WaitForSecondsRealtime(BossDeathLingerSeconds);
        }

        deadline = Time.realtimeSinceStartup + PlayerDeathTimeoutSeconds;
        while (_playerDeathActive && Time.realtimeSinceStartup < deadline)
            yield return null;

        if (BossDied && hero != null)
        {
            // The boss is gone, so the hero is safe again. A soft reset would restore this itself,
            // but a hard reset (which follows a boss death) does not.
            hero.damageMode = GlobalEnums.DamageMode.FULL_DAMAGE;
            hero.playerData.isInvincible = false;
            hero.cState.invulnerable = false;
        }
    }

    /// <summary>Returns whether the boss died, and clears the flags for the next episode.</summary>
    public static bool ConsumeDeaths()
    {
        bool bossDied = BossDied;
        BossDied = false;
        PlayerDied = false;
        return bossDied;
    }
}
