+++
title = "Building Ukodus"
date = 2026-02-23
description = "How a ThePrimeagen rant, an ADHD lightbulb, and a Rust game engine turned into a full Sudoku system spanning TUI, WASM, and iOS."
[taxonomies]
tags = ["rust", "wasm", "svelte", "d3", "kubernetes", "sudoku", "ios", "homelab"]
+++

## The Spark

In mid-2025, Anthropic engineer [Thariq Shihipar tweeted](https://x.com/trq212/status/2014051501786931427) that Claude Code should be thought of as "a small game engine" rather than just a TUI. Every frame, their pipeline constructs a React scene graph, lays out elements, rasterizes them to a 2D screen, diffs against the previous frame, and generates the minimal ANSI sequences to update the terminal — all within a ~16ms frame budget.

The developer community had opinions. [Casey Muratori responded](https://x.com/cmuratori/status/2014426615229600211): *"NARRATOR: Claude Code was not, in fact, close to a small game engine."* A [deep analysis on spader.zone](https://spader.zone/engine/) compared Claude Code's renderer head-to-head with Super Mario 64, finding it executes roughly 4.6 billion instructions over a 33ms frame — orders of magnitude more than SM64 — with 70% of the time spent on `futex` synchronization calls and ~89,000 erroneous `sched_yield` syscalls per frame. The critique wasn't that building a renderer is wrong, it's that the complexity was wildly disproportionate to the problem: you're rendering text in a terminal, not polygons in 3D space.

ThePrimeagen [weighed in](https://x.com/ThePrimeagen/status/2014764406337351994) and the whole thing blew up across [Hacker News](https://news.ycombinator.com/item?id=46755209) and dev Twitter. The consensus was pretty clear: React scene graphs and game-engine-style frame budgets for terminal text output is over-engineered when tools like Vim have been doing it efficiently for decades.

Fascinating discourse on TUI expectations and design. And it got me tinkering.

## The ADHD Lightbulb

I started with a little TUI experiment — just messing around with rendering, seeing what you could do. That got me thinking about win screens and animations. Then the lightbulb fired: I should build a Sudoku TUI. So Claude and I whipped one up with a Rust-backed game engine.

The initial version was a single monolithic repo. The engine handled generation, solving, and rendering all tangled together. It worked, but it wasn't clean.

## From TUI to Everywhere

While I was crunching on other projects — mainly trying to get my Talos cluster fully provisioned — I kept coming back to the game engine. The thought was simple: I already have this engine, I might as well do a WASM mockup too. From there it was an easy leap to just build the iOS app.

## The r/Sudoku Reckoning

I posted to [r/Sudoku](https://www.reddit.com/r/sudoku/). Man, they do not like AI. But underneath the AI skepticism was genuinely great feedback from people who live and breathe Sudoku. The community has real standards for how puzzles should be rated, what solving techniques should be supported, and how hints should teach rather than just give answers.

That feedback sent me back to the drawing board. I didn't just patch the engine — I rebuilt it. The monolithic repo got split into three:

- [**sudoku-core**](https://github.com/kcirtapfromspace/sudoku-core) — the pure Rust engine. Solving, generation, difficulty rating, variant support. No UI, no platform concerns. Just the math.
- [**sudoku**](https://github.com/kcirtapfromspace/sudoku) — cross-platform wrappers that consume the core. iOS app, TUI binary, WASM compilation. Each target gets its own interface but shares the same engine underneath.
- [**ukodus**](https://github.com/kcirtapfromspace/ukodus) — the full platform. Galaxy API, SvelteKit frontend, Neo4j graph backend, leaderboard. The product layer.

The separation forced me to think about clean boundaries. The core crate has zero platform dependencies — it compiles to WASM, ARM (iOS), and x86 without conditional compilation. The cross-platform repo owns the build targets. The platform repo owns the infrastructure. No circular dependencies, no leaky abstractions.

## The Engine: 45 Techniques Deep

With the architecture clean, I could focus on making the engine meet community standards. It now implements 45 human-style solving techniques organized into 10 families:

- **Singles** — Hidden Single, Naked Single (the basics)
- **Pairs & Triples** — Naked Pair through Hidden Quad
- **Intersections** — Pointing Pairs, Box/Line Reduction
- **Fish** — X-Wing, Swordfish, Jellyfish, plus finned and mutant variants
- **Wings** — XY-Wing, XYZ-Wing, W-Wing, WXYZ-Wing
- **Chains** — X-Chain, 3D Medusa, AIC
- **Rectangles** — Unique Rectangles (6 types), Hidden Rectangle, Empty Rectangle
- **ALS** — Almost Locked Sets: ALS-XZ, ALS-XY-Wing, ALS Chain
- **Forcing** — Nishio, Cell/Region Forcing Chains, Dynamic Forcing Chains
- **Other** — Sue de Coq, Aligned Pair Exclusion, Death Blossom, BUG+1, Backtracking

Each technique has a Sudoku Explainer (SE) difficulty rating. Hidden Single is 1.5 (beginner territory), Dynamic Forcing Chain is 9.3 (you need a PhD or a lot of patience), and Backtracking sits at 11.0 as the last resort. The engine uses these ratings to classify every puzzle into difficulty tiers: Beginner, Easy, Medium, Intermediate, Hard, Expert, Master, and Extreme.

Why does this matter? Because most Sudoku apps rate puzzles by counting givens or using some vague internal metric. SE ratings map directly to the hardest technique you'd need to solve the puzzle. A puzzle rated 3.2 means you'll need X-Wings. A 7.5 means ALS Chains or Nishio. You know exactly what you're getting into.

### How Validation Works

Validation is built on a constraint trait system. Every rule — rows, columns, boxes, and variant rules like X-Sudoku diagonals or Killer cages — implements the same `Constraint` trait with a `validate()` method. When you place a value, the grid runs it through every active constraint. This makes the engine extensible: adding a new Sudoku variant is just a new constraint, not a rewrite of the solver.

Each cell tracks its own candidates in a `BitSet` — a `u16` where each bit represents a possible value 1–9. Candidate operations (insert, remove, contains, intersection) are all constant-time bitwise ops. When a value gets placed, the grid walks the affected row, column, and box to strip that value from neighboring candidates. When a value gets cleared, candidates get restored. No full-grid recalculation on every move.

### Generating and Rating Puzzles

Generation works top-down. The generator first fills the three diagonal 3x3 boxes randomly — they're independent of each other, so no constraint checking needed. Then it solves the rest with constraint satisfaction to get a complete valid grid. From there it removes clues.

Cell removal is where things get expensive. The generator shuffles all 81 positions, removes cells in symmetry pairs (180° rotational by default, but it supports 90°, horizontal, vertical, and diagonal too), and after each removal calls `has_unique_solution()` to verify the puzzle still has exactly one answer. That uniqueness check is a full solve under the hood. If removing a cell creates multiple solutions, it stays.

Difficulty rating happens by solving the generated puzzle with the technique hierarchy — Naked Singles first, then Hidden Singles, Pairs, Fish, Wings, Chains, all the way up. The hardest technique the solver had to use becomes the puzzle's rating. A puzzle that only needs Naked Singles and Hidden Singles is Beginner. One that forces the solver into XY-Wings or X-Chains lands at Master. If the solver can't crack it without backtracking, it's Extreme.

The generation configs dial the difficulty:

| Difficulty | Givens | Max Attempts |
|---|---|---|
| Beginner | 45–55 | 30 |
| Easy | 36–45 | 50 |
| Medium | 32–38 | 100 |
| Hard | 24–30 | 200 |
| Expert | 22–26 | 500 |
| Master | 20–24 | 1,000 |
| Extreme | 17–22 | 2,000 |

Extreme puzzles can take up to 2,000 attempts to generate because the generator has to find a grid where the minimum number of clues still forces advanced techniques. This is why the WASM background mining matters — you don't want a player waiting for that.

## One Engine, Every Platform

The beauty of writing the core in Rust is that the same engine works everywhere:

- **Browser**: Compiled to WASM via `wasm-pack` — a 554KB binary and a JS glue module. Renders to `<canvas>`, Rust owns all the drawing logic.
- **iOS**: Compiled natively via Xcode, same Rust core, native UI shell.
- **Terminal**: Rust binary with a TUI interface.
- **Shared codes**: 8-character short codes and 81-character puzzle strings work across all platforms.

You can start a puzzle on iOS, share the code, and your friend can play the exact same puzzle in a browser. The engine deterministically generates the same puzzle from the same seed, so there's no server round-trip needed to decode a shared puzzle.

Loading WASM in a SvelteKit app requires some care. You can't let Vite try to bundle the WASM module at build time, so the loader uses a dynamic import with a `@vite-ignore` pragma:

```typescript
const wasmJsPath = '/wasm/sudoku_wasm.js';
const mod = await import(/* @vite-ignore */ wasmJsPath);
await mod.default({
  module_or_path: new URL('/wasm/sudoku_wasm_bg.wasm', window.location.origin)
});
```

The WASM files live in `static/wasm/` and get served as plain static assets. The `/play/` route sets `ssr = false` so SvelteKit generates a minimal HTML shell that hydrates client-side — the WASM needs a browser environment with a canvas, so server-side rendering would just blow up.

The game loop is a standard `requestAnimationFrame` cycle. Every frame calls `game.tick()` on the WASM side, which handles input processing, animation, and canvas rendering. The engine supports vim-style navigation (`hjkl`), arrow keys, and WASD — because every good application should support at least three ways to move a cursor.

## The Galaxy

At some point during testing I learned how astronomically large the number of possible Sudoku puzzles is and thought it would be fun to map out the constellations of types of Sudoku games. That's when the whole project morphed from "a game" into "a platform."

The Galaxy page uses D3's `forceSimulation` to create a force-directed graph. Each node is a puzzle, colored by difficulty tier (green for Beginner through near-black for Extreme). Node size scales with play count. Edges connect puzzles that share solving techniques, so similar puzzles cluster together.

The fun part is the convex hulls. D3 computes `polygonHull` for each technique family and draws translucent overlays around them, so you can see the Fish cluster, the Wings cluster, the Chains cluster. It looks like a star map. Which is the point.

```typescript
simulation = d3
  .forceSimulation<GalaxyNode>(nodes)
  .force('link', d3.forceLink<GalaxyNode, GalaxyEdge>(edges)
    .id(d => d.id).distance(60).strength(0.3))
  .force('charge', d3.forceManyBody().strength(-80))
  .force('center', d3.forceCenter(width / 2, height / 2))
  .force('collide', d3.forceCollide<GalaxyNode>()
    .radius(d => nodeRadius(d) + 2))
  .alphaDecay(0.02)
  .on('tick', ticked);
```

The Galaxy is live — when someone completes a puzzle, a WebSocket message pushes the new node into the simulation in real-time. You can literally watch the galaxy grow.

There's also a "secrets" system. By default, you only see 22 of the 45 techniques and 6 of the 10 families. The advanced families — Chains, ALS, Forcing, and Other — are hidden until you unlock them by completing harder puzzles. When you unlock secrets, the Galaxy reveals entire new constellations that were invisible before. It's my favorite feature and probably the most unnecessary one.

## The Full Stack

The web frontend is SvelteKit 5 with TypeScript. State management uses Svelte 5 runes — class-based stores with `$state`, `$derived`, and `$effect`:

```typescript
class PlayerStore {
  id = $state('');
  tag = $state('');
  secrets = $state(false);

  setTag(value: string) {
    this.tag = value;
    localStorage.setItem(PLAYER_TAG_KEY, value);
  }
}

export const playerStore = new PlayerStore();
```

The app uses `adapter-static` with `prerender = true`. Content pages get fully pre-rendered to static HTML at build time. Interactive pages (`/play/` and `/galaxy/`) set `ssr = false` because they need browser APIs. The build output is plain HTML, CSS, and JS — no Node.js runtime in production.

The whole thing runs on my Pi cluster with a CloudFront CDN in front. The frontend is a multi-stage Docker image — SvelteKit builds the static site in stage one, then the output drops into Nginx Alpine. SvelteKit's `adapter-static` generates pre-compressed `.br` and `.gz` files at build time, and Nginx serves them directly with `gzip_static on` — zero CPU overhead for compression at request time.

I offload compute to the WASM client: in the background, while someone is playing, it mines up to 10 of the harder difficulty puzzles. Some of these take exceedingly long to validate on iOS, so pre-mining them means play stays fast when those puzzles get served to the app. There's a leaderboard in there too.

## What It Became

Ukodus is a fully integrated game system. Three repos, three platforms, one engine. The TUI, WASM, and iOS clients all look up generated puzzles, solve them with hints, and track everything — all tied back to the galaxy graph.

It's a Sudoku app that doesn't have ads, doesn't require a subscription, and teaches you actual solving techniques instead of just filling in answers. Which is all I wanted in the first place.

---

**Play it**: [ukodus.now](https://ukodus.now)
**Source**: [github.com/kcirtapfromspace/sudoku-core](https://github.com/kcirtapfromspace/sudoku-core)
**iOS App**: [App Store](https://apps.apple.com/us/app/sudoku/id6758485043)
