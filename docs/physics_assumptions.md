# Phase 3 physics default audit

Scope: active Claude/manual upload pipeline, browser response handling, animation adapter and renderer constructors. Legacy OCR/LLM services are retained unchanged for the later architecture phase. No motion types were added.

## Physics defaults found

| Location | Original hidden value or behavior | Phase 3 treatment |
| --- | --- | --- |
| Claude prompt/response normalizer | Gravity 9.8; absent type treated as projectile; speed 10, angle 45, height 0 | Model extracts only evidence; backend validates and rebuilds animation. Unknown type blocks animation. Gravity/ground launch are explicit assumptions |
| Duration/scale helpers | Missing speed 10, angle 45, gravity 9.8 (also for invalid g), height 0; fixed 2 seconds on invalid/absent flight inputs; minimum flight time 0.5 seconds; fake range 10 when speed is zero | No physics fallback or minimum duration. Flight time and extents derive from validated inputs; invalid g is rejected. Scale remains visual |
| Manual extraction/steps | Gravity 9.8; unknown type becomes projectile; absent height treated as 0 in steps; zero height omitted from known inputs; generic speed could mean final speed or acceleration | Missing values stay null; final speed/acceleration is not initial speed; steps distinguish supplied parameters, assumptions and blocked animation |
| Manual numeric/unit parsing | Unit suffixes ignored (e.g. 20 km/h could become 20 m/s); fractions/scientific numbers could be partially read as a different value | Common unsupported units block animation; partial numeric matches are rejected rather than silently assuming SI magnitude |
| Manual motion generation | Horizontal speed 10 and height 8 (including explicit height 0); free-fall speed 0, angle 90 and height 10 (including zero); vertical speed 15, angle 90, height 0; uniform speed 5, forced angle 0, duration 5; inclined-plane speed 0/angle 30 and projectile fallback; general speed 20/angle 45/height 0 | Essential speed/angle/height must be supplied as described in the contract. Type-derived direction/rest and reasonable ground launch are recorded. Uniform window 5 is labeled. Inclined plane is blocked |
| `static/main.js` and adapter array handling | Arrays produce projectile sample speed 18, angle 55, gravity 9.8, height 0, duration 4 (adapter mass 1) | Removed; malformed arrays cannot become animation |
| `static/animation.js` | Missing type becomes projectile; speed 20, angle 45, gravity 9.8, height 0, mass 1, duration 10; free-fall height 10 even for explicit 0 | Removed. Validated object required; aliases preserve zero; unknown mass remains null |
| Adapter uniform | Missing direction interpreted as 0; gravity forced 0 | Direction assumption belongs to backend; unknown gravity remains unavailable, not zero |
| Adapter acceleration | Force 10 N, friction 0.2, mass 1, speed 20, gravity 9.8, duration 10 | Removed; explicit renderer inputs required |
| Adapter circular | Radius 5, angular speed 1, friction 0.5, mass 1, gravity 9.8, duration 10 | Removed; explicit renderer inputs required |
| Projectile constructor | `v0 || 20` overwrites explicit zero; height 0, gravity 9.8, mass 1 | Removed; required values checked; optional mass null |
| Free-fall constructor | Height 10, gravity 9.8, mass 1; rebound coefficient 0.8 (also overwrites zero) | Removed; explicit height/gravity; rebound requires coefficient; unknown mass null |
| Uniform constructor | Missing gravity displayed as 0; zero duration means unlimited playback | Unknown gravity stays null; zero-duration playback ends immediately |
| Acceleration constructor | Gravity 9.8, initial speed 0, duration 10, initial x 0 | Physics fallbacks removed; explicit values required. Adapter may choose coordinate origin 0 |
| Circular constructor | Friction 0.5 (overwrites zero), gravity 9.8, initial phase 0, duration 10; assumes available friction is enough | Removed; explicit phase/parameters; impossible friction capacity is rejected. Zero layout coordinates are preserved |
| Legacy browser `VerticalThrow` helper | Height 0, gravity 9.8, mass 1 | Removed; validates required inputs and handles null instructions |
| `PhysicsVisualizer` | Unknown type becomes projectile; nonexistent renderer classes accepted by name | Removed; unsupported types throw a readable error |
| Base force display | Missing gravity/mass multiplied as 0, showing a false zero weight | Unknown weight is `N/A`; force diagrams skip unknown inputs |

## Assumptions remaining in the active API

These are visible in both API and browser, only when applicable:

- Standard Earth gravity 9.8 m/s² if absent.
- Ground reference height 0 for general/vertical launch and uniform motion if absent. Horizontal launch/free fall require height.
- Horizontal angle 0 and vertical angle 90 inferred from the named motion.
- Free fall means release from rest (speed 0); contradictory nonzero speed blocks animation.
- If launch speed is explicitly zero, missing angle may use 0 since it cannot affect the trajectory.
- Uniform motion uses direction 0 and a 5-second demonstration window if absent. The window is not the real total travel time.
- Ideal ballistic motion ignores air resistance and ends at reference ground y=0; this assumption is shown unless neglect of air resistance is explicitly given. Resistance/friction/rebound requests block the active animation.

Flight time is derived, never guessed. Mass is not assumed. No speed 5/10/15/20, angle 30/45/55, or height 8/10 is invented in the active flow.

## Display/system defaults retained

Canvas dimensions, coordinate origin, free-fall horizontal placement, circular center layout, drawing size/colors, grid, vector magnification, pixel scale limits and 60 fps are visual or numerical settings. Object drawing radius is not used as the physical circular orbit radius. Backend display scale now reaches the visualizer, so supplied heights can fit without replacing their values. Zero extents no longer disable projectile scaling.

Stopping at canvas boundaries and frame stepping remain renderer limitations. The legacy acceleration renderer models horizontal ground friction; the circular renderer models horizontal motion sustained by friction. These are explicit fixture model choices, not new capabilities of the active parser.

## Legacy services and fixtures

`services/llm_service.py` remains outside `/upload`. It still has gravity 9.8, speeds 5/10/15/20, angles 0/45/90, heights 0/8/10, a 5-second uniform window, 2-second fallback, minimum 0.5-second flight time, default projectile classification and a fabricated range of 10 used for scale. Its old explanation labels zero speed/angle as “default”. `services/ocr_service.py` still contains mock sample text for its legacy mock path. Neither service was edited or removed. Their remaining defaults prevent claiming that every legacy helper in the repository is safe for production.

Explicit sample values in test pages and console fixtures are intentional examples, not values extracted from a user's problem. Fixtures that depended on hidden initial height/x/phase now provide them explicitly; the impossible circular fixture expects rejection. Vendored Matter.js defaults are library behavior used by a standalone test canvas, not the main upload animation engine; vendor files were not edited.

## Verification

Run without an API key:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q --cov=app --cov=routes.upload --cov=services.claude_pipeline --cov-report=term-missing
node --test tests/browser/*.test.js
# Optional live-server diagnostic: start python app.py in a separate terminal, then:
python scripts/self_check.py                # Live Claude test skips without a key
```

The supported suite is described in [testing.md](testing.md). `scripts/quick_test.py` and `scripts/test_dynamic_response.py` cover legacy OCR/LLM behavior and are not CI gates. `tools/test_ocr.py` has a pre-existing import failure (`get_ocr_provider`); it remains unchanged for the later legacy cleanup phase. Live Claude image recognition requires a key and is not part of no-key verification.
