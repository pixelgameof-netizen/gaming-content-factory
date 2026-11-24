# Gaming Gameplay Hunter (Phase 1)

This module discovers video-file candidates on Wikimedia Commons for a flexible list of games.

## Safety and rights gates

- Only explicit **CC0**, **CC BY 3.0**, and **CC BY 4.0** file metadata pass the discovery filter.
- NC, ND, ShareAlike, unknown, and missing licenses are excluded in this first phase.
- A Commons file license is **not** proof that the underlying game footage, trademarks, embedded music, or third-party assets may be reused. Every result therefore remains `rights_status: candidate`.
- The scanner does not download media, create render jobs, or approve rights. It creates a JSON artifact for review.
- Do not use a candidate until publisher/gameplay policy and soundtrack rights are independently cleared and attribution requirements are satisfied.

## Run

GitHub Actions → **Discover licensed gameplay candidates** → Run workflow. Optionally provide comma-separated game titles. The workflow also runs daily and stores a 14-day artifact.

The search is intentionally conservative. A small or empty result is preferable to presenting unlicensed gameplay as reusable footage.
