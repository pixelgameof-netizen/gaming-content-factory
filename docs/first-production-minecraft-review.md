# First production review — Minecraft short

**Status: script v3 and all five source rights reviews approved by owner. Ready for the first private render after renderer CI passes. Not approved for publication.**

## Package

- Topic: Minecraft — five stages, one idea that never changed
- Format target: vertical 9:16, 1080 × 1920, 30 fps
- Target duration: 32 seconds
- Narration: original Spanish voiceover (Kokoro ONNX, voice `ef_dora`)
- Music: none
- Gameplay source audio: all five downloaded files were inspected; no audio stream was present
- All five originals are stored privately in Supabase Storage; all five media assets and rights reviews are now owner-approved

## Downloaded gameplay assets

All five files identify **Xbox México** as author and are extracted from the public Xbox México video “Xbox Masterclass: TIPS y consejos para ser un experto en Minecraft”. Each Commons file page lists CC BY 3.0 and CC BY 4.0; attribution, a license link, and an indication of changes are required. Commons also warns that other legal constraints may apply.

| Scene | Commons file | Source timestamp | Verified duration | Technical inspection |
|---|---|---:|---:|---|
| 1 | [Cave Game Gameplay (Minecraft Prototype)](https://commons.wikimedia.org/wiki/File:Cave_Game_Gameplay_(Minecraft_Prototype).webm) | 00:35 | 15.030 s | AV1, 1046×784, no audio |
| 2 | [Minecraft Classic Gameplay](https://commons.wikimedia.org/wiki/File:Minecraft_Classic_Gameplay.webm) | 00:48 | 10.309 s | AV1, 1374×786, no audio |
| 3 | [Minecraft Alpha Gameplay](https://commons.wikimedia.org/wiki/File:Minecraft_Alpha_Gameplay.webm) | 01:00 | 9.500 s | VP9, 1920×1016, no audio |
| 4 | [Minecraft Beta Gameplay](https://commons.wikimedia.org/wiki/File:Minecraft_Beta_Gameplay.webm) | 01:08 | 13.950 s | VP9, 1920×1080, no audio |
| 5 | [Minecraft Gameplay](https://commons.wikimedia.org/wiki/File:Minecraft_Gameplay.webm) | 01:24 | 8.908 s | VP9, 1482×784, no audio |

The automated inspection downloaded each stored object, checked SHA-256 against the registered object, and inspected the media streams using PyAV. See [technical QC and visual review workflow run 45328386210](https://github.com/pixelgameof-netizen/gaming-content-factory/actions/runs/45328386210).

## Rights context and owner approval

1. The five Commons pages list CC BY 3.0 and CC BY 4.0 and identify Xbox México as author. Attribution will use the CC BY 4.0 link: https://creativecommons.org/licenses/by/4.0/
2. The archived Wikimedia Commons deletion discussion for the Xbox México Minecraft files was closed as “Kept” on 30 July 2025. The discussion records that the CC BY option had been intentionally selected on the Xbox México YouTube source. This is supporting context, not a guarantee of every independent right.
3. The [official Minecraft Usage Guidelines](https://www.minecraft.net/en-us/usage-guidelines) permit gameplay videos and ad monetization when sufficient unique creator content/commentary is added. They prohibit implying Mojang/Microsoft endorsement and require permission for third-party music/audio.
4. The downloaded excerpts contain no audio stream. No third-party music will be used. The plan adds original Spanish narration and an original edit.
5. A visual review artifact was generated with two sampled frames (at 2s and 6s) from each clip. The inspected samples show Minecraft gameplay/HUD, with no third-party brand overlays, advertisements, or separate third-party visual inserts.
6. The owner approved script v3 and all five rights reviews on 24 November 2026 UTC. The five `rights_reviews` are `approved_by_owner`; the five `media_assets` are `rights_status=approved`. This records the owner's approval based on the evidence above; it is not a legal guarantee for any independent rights not represented in the reviewed sources.

## Required attribution

For each used clip, credit **Xbox México**, link its Commons file page, link the CC BY 4.0 license, and state the actual edits applied (for example: trimmed, reframed, transcoded, narrated, captioned). Do not suggest endorsement or affiliation with Xbox/Microsoft. Final change descriptions must be updated after the actual edit.

## Script v3 — approved

**Title:** Minecraft: cinco etapas, una idea que no cambió

> Antes de ser el mundo que conoces, Minecraft fue apenas una idea hecha de bloques. Cave Game: terreno simple, pocas piezas y todo por descubrir. Después, Classic convirtió esa prueba en libertad para construir. Alpha y Beta fueron dando forma a la aventura. Y lo increíble es que, con millones de posibilidades, la esencia sigue igual: aparecer en un mundo nuevo y decidir qué hacer con él. ¿Qué versión elegirías?

Editorial status: `approved` by owner. Target duration: 32 seconds.

## Planned edit

- Order: Cave Game → Classic → Alpha → Beta → modern gameplay.
- Distribute scene durations to match the final voiceover, so all five stages appear.
- For vertical output, preserve the full gameplay frame over a softly blurred enlarged background rather than cropping important gameplay edges.
- Use short 0.25-second crossfades between scenes.
- Place subtitles in the lower safe area outside the main gameplay image.
- No third-party music. The original source audio tracks are absent.
- Any title/credit card should sit outside the gameplay area.

## Render and publication gate

- The first render may be queued only after the synthetic renderer CI passes.
- The rendered MP4 will be stored privately.
- Publication remains disabled until the owner approves the exact MP4 version and its SHA-256. Any file change invalidates that approval.
