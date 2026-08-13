# AI layout generation

This page explains the optional AI feature: you describe a home in plain English, and the app drafts a floor plan. It covers how the pipeline works, how to configure it, what it costs, and what can go wrong.

## The most important thing to understand

**The AI never draws your plan.** It only writes a *wish list* — rooms, rough sizes, relationships ("kitchen near dining"). The app's own code then draws the real geometry, fixes it, and checks it. The AI's answer is treated as an untrusted suggestion until every local check passes.

This is deliberate: AI models sometimes produce impossible geometry or misunderstand instructions. Because the app validates everything, a bad AI answer gets rejected — it cannot sneak into your project.

## The pipeline, step by step

```text
1. You type a brief         "3-bedroom house, kitchen south-east, plot 40x60, facing east"
        │
2. AI interprets it  ─────► returns a structured wish list (rooms + relationships)
        │
3. Normalizer        ─────► cleans the wish list, checks it makes sense
        │
4. Planner           ─────► the app's own code draws candidate room rectangles
        │                   (two planner styles exist: "comb" and "multi")
5. Auto-fixer        ─────► repairs overlapping walls, broken polygons, etc.
        │
6. Strict checker    ─────► rejects anything invalid
        │                     ├─ small problem list? → the AI gets a LIMITED
        │                     │   chance to fix its own mistakes, back to step 5
        │                     └─ valid? → continue
        ▼
7. The plan becomes an official v2 project and appears on your canvas,
   exactly like something you drew by hand — fully editable.
```

While all this happens, the app stays responsive: AI work runs in the background, you can watch progress or cancel, and results are applied on the main screen only when complete. Each generation gets an increasing ID, so a slow answer to a request you already cancelled is recognized and discarded.

## Setting it up

1. Copy `.env.example` to `.env` (repository root).
2. Set `GOOGLE_CLOUD_PROJECT` to your Google Cloud project.
3. Run `gcloud auth application-default login` and sign in.

Settings (environment variables you already have set in your terminal win over `.env` values):

| Setting | Meaning | Default |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | Your Google Cloud project. **Always set this yourself.** | *(none — a leftover fallback exists in code, do not rely on it)* |
| `GOOGLE_CLOUD_LOCATION` | Google region | `global` |
| `AI_LAYOUT_MODEL` | Which Gemini model answers | `gemini-3.1-pro-preview` (a preview model — availability can change) |
| `AI_LAYOUT_THINKING_LEVEL` | How hard Gemini 3 "thinks" | `HIGH` |
| `AI_LAYOUT_THINKING_BUDGET` | Numeric thinking budget for older 2.5 models | `6144` (kept between 0–8192) |
| `AI_LAYOUT_MAX_TOKENS` | Maximum size of one AI answer | `32000` (kept between 256–65536) |
| `AI_LAYOUT_TIMEOUT_MS` | Wait limit for one AI reply | `120000` ms (kept between 10–180 s) |
| `AI_LAYOUT_OPERATION_TIMEOUT_MS` | Wait limit for a whole generation | `300000` ms (kept between 30–600 s, never below the reply limit) |
| `AI_LAYOUT_PLANNER` | `comb` or `multi`; an unknown value safely refuses to run | `comb` |
| `AI_LAYOUT_SEED` | Makes results more repeatable | `0` (non-negative 32-bit integer) |

## Built-in safety limits

The pipeline refuses to run away with your quota or produce monsters. Hard caps include:

- **AI calls per action:** up to 3 room-program + 2 furnishing calls for a new plan; 2 calls per refinement; 1 routing + 2 surgical calls for chat-style edits.
- **Repair input:** the problem description sent back to the AI is capped at 120,000 characters; assistant messages at 1,200 characters; reported errors at 40.
- **Plan size:** 100 rooms, 500 furniture items, 200 shapes, 200 text items, 1,000 entities total, 4,000 shape points.
- **Floors:** at most 4 floors in one AI request.

## Known limitation: multi-floor plans

When the AI makes a multi-storey design, each floor is planned **independently** and then stacked. The official format *can* represent stairs and cross-floor links, but the generator does not yet guarantee that stairs line up between floors or that you can actually walk from floor to floor. **Review multi-floor results and fix vertical circulation by hand.**

## Cost and safety

- Real generation makes real network calls against **your** Google account: quota, billing, and availability are Google's side of the deal.
- Never paste secrets into a brief. Never commit `.env` or credential files.
- The default model is a *preview* — Google may change or withdraw it. If generation suddenly stops working, model availability is one of the first things to check.
- Cancelling or timing out stops the app from waiting, but work already started on Google's side may still consume quota.

## When generation keeps failing

1. Check the boring things first: signed in (`gcloud auth application-default login`), correct project, Vertex AI enabled, billing/quota OK, model available in your location.
2. Check `.env`: planner spelled `comb` or `multi`, timeouts not absurdly small.
3. Simplify the brief: remove contradictions, state plot size and facing clearly, ask for fewer rooms.
4. Read the validation messages the app shows — they say *what* was rejected and *why*. Fix the brief; never disable the checkers to force a bad plan through.

More fixes: [Operations and troubleshooting](operations-and-troubleshooting.md).
