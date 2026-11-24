# First production review — Minecraft short

**Status: prepared for owner review; not approved for rendering or publication.**

## Package

- Topic: Minecraft — five stages, one idea that never changed
- Format target: vertical 9:16, 1080 × 1920, 30 fps
- Target duration: 32 seconds
- Narration: original Spanish voiceover (Kokoro ONNX, voice `ef_dora`)
- Music: none
- Gameplay source audio: all five downloaded files were inspected; no audio stream was present
- All five originals are stored privately in Supabase Storage as `rights_status=candidate`

## Downloaded gameplay assets

All five files identify **Xbox México** as author and are extracted from the public Xbox México video “Xbox Masterclass: TIPS y consejos para ser un experto en Minecraft”. Each Commons file page lists CC BY 3.0 and CC BY 4.0; attribution, a license link, and an indication of changes are required. Commons also warns that other legal constraints may apply.

| Scene | Commons file | Source timestamp | Verified duration | Technical inspection |
|---|---|---:|---:|---|
| 1 | [Cave Game Gameplay (Minecraft Prototype)](https://commons.wikimedia.org/wiki/File:Cave_Game_Gameplay_(Minecraft_Prototype).webm) | 00:35 | 15.030 s | AV1, 1046×784, no audio |
| 2 | [Minecraft Classic Gameplay](https://commons.wikimedia.org/wiki/File:Minecraft_Classic_Gameplay.webm) | 00:48 | 10.309 s | AV1, 1374×786, no audio |
| 3 | [Minecraft Alpha Gameplay](https://commons.wikimedia.org/wiki/File:Minecraft_Alpha_Gameplay.webm) | 01:00 | 9.500 s | VP9, 1920×1016, no audio |
| 4 | [Minecraft Beta Gameplay](https://commons.wikimedia.org/wiki/File:Minecraft_Beta_Gameplay.webm) | 01:08 | 13.950 s | VP9, 1920×1080, no audio |
| 5 | [Minecraft Gameplay](https://commons.wikimedia.org/wiki/File:Minecraft_Gameplay.webm) | 01:24 | 8.908 s | VP9, 1482×784, no audio |

The automated inspection downloaded each stored object, checked SHA-256 against the registered object, and inspected the media streams using PyAV. See [GitHub Actions run 45316014585](https://github.com/pixelgameof-netizen/gaming-content-factory/actions/runs/45316014585).

## Rights context to review

1. The five Commons pages list CC BY 3.0 and CC BY 4.0 and identify Xbox México as author. Proposed attribution should use the CC BY 4.0 link: https://creativecommons.org/licenses/by/4.0/
2. The archived Wikimedia Commons deletion discussion for the Xbox México Minecraft files was closed as “Kept” on 30 July 2025. The discussion records that the CC BY option had been intentionally selected on the Xbox México YouTube source. This is supporting context, not a guarantee of every independent right.
3. The [official Minecraft Usage Guidelines](https://www.minecraft.net/en-us/usage-guidelines) permit gameplay videos and ad monetization when sufficient unique creator content/commentary is added. They prohibit implying Mojang/Microsoft endorsement and require permission for third-party music/audio.
4. The downloaded excerpts contain no audio stream. The source's visual content, game/publisher policy, third-party visual elements, and final attribution presentation still require owner review.
5. No review has been approved. Keep all five rights reviews at `candidate`; do not render or publish until the owner records approval.

## Proposed attribution

For each used clip, credit **Xbox México**, link its Commons file page, link the CC BY 4.0 license, and state the actual edits applied (for example: trimmed, reframed, transcoded, narrated, captioned). Do not suggest endorsement or affiliation with Xbox/Microsoft. Final change descriptions must be updated after the actual edit.

## Script v3 — draft only

**Title:** Minecraft: cinco etapas, una idea que no cambió

> Antes de ser el mundo que conoces, Minecraft fue apenas una idea hecha de bloques. Cave Game: terreno simple, pocas piezas y todo por descubrir. Después, Classic convirtió esa prueba en libertad para construir. Alpha y Beta fueron dando forma a la aventura. Y lo increíble es que, con millones de posibilidades, la esencia sigue igual: aparecer en un mundo nuevo y decidir qué hacer con él. ¿Qué versión elegirías?

Editorial status: `draft`. Owner approval is still required.

## Planned edit

- Order: Cave Game → Classic → Alpha → Beta → modern gameplay.
- Distribute scene durations to match the final voiceover, so all five stages appear.
- For vertical output, preserve the full gameplay frame over a softly blurred enlarged background rather than cropping important gameplay edges.
- Use short 0.25-second crossfades between scenes.
- Place subtitles in the lower safe area outside the main gameplay image.
- No third-party music. The original source audio tracks are absent.
- Any title/credit card should sit outside the gameplay area.

## Owner decisions required

- Review and explicitly approve or reject the five source rights reviews, including the attribution and third-party visual/publisher checks.
- Approve or revise script v3.
- Only after both approvals may the app create a render job. The output will remain private and unpublished pending approval of the exact MP4 version and SHA-256.
