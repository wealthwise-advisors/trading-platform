<div align="center">

# 🛠 Diagram Generators

**The scripts that draw the SVGs. Edit these, not the output.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| ▶️ **Run** | `py -3.12 docs/assets/tools/<name>.py` |
| 📤 **Writes to** | [`docs/assets/`](..) |
| 🎯 **Why scripts** | A diagram that must stay in step with the code has to be rebuildable |
| 📁 **Path** | `docs/assets/tools/` |
| 📦 **Holds** | `8` generators · `1` render harness |


---

## 🔄 How it fits together

```
   py -3.12 make_<name>_svg.py
        │
        ▼
   ../<name>.svg   ──►  referenced by the README and the docs

   why scripts and not drawings: a diagram that must stay in step
   with the code has to be rebuildable when the code moves.
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`make_live_tape_svg.py`](make_live_tape_svg.py) | 📡 The live tape diagram. | 884 |
| [`make_flow_svgs.py`](make_flow_svgs.py) | 🔄 `architecture` · `workflow` · `execution`. | 564 |
| [`make_one_clock_svg.py`](make_one_clock_svg.py) | 🕐 The shared-clock diagram. | 264 |
| [`make_pipeline_svg.py`](make_pipeline_svg.py) | ⚙️ The pipeline diagram. | 261 |
| [`make_deploy_svg.py`](make_deploy_svg.py) | 🚀 The deployment diagram. | 249 |
| [`make_divergence_svg.py`](make_divergence_svg.py) | 📉 The divergence illustration. | 243 |
| [`make_ecosystem_svg.py`](make_ecosystem_svg.py) | 🌍 The repository ecosystem map. | 226 |
| [`make_test_topology_svg.py`](make_test_topology_svg.py) | 🧪 The test topology. | 208 |

> ⚠️ **`elliott-wave.svg` has no generator.** It is hand-maintained SVG and is
> edited in place at [`../elliott-wave.svg`](../elliott-wave.svg). Looking for
> `make_elliott_wave_svg.py` and concluding the file is stale is the mistake
> this line exists to prevent.


---

## 💡 Worth knowing

- ➜ **A diagram that must stay in step with the code has to be rebuildable.** That is why these are scripts rather than drawings.

- ➜ **A diagram carries labels, not sentences.** Every one of these used to end
  with a line of prose explaining what it had just shown — and several set a
  second explanatory line inside the boxes. That is README text drawn as an
  image: it cannot be skimmed, searched, translated or read by a screen reader,
  and it forces the canvas taller so the type gets smaller. The picture states
  the relationship; the prose goes in the README **as a bullet**, next to it.

- ➜ **Style every peer identically unless the difference means something.**
  `execution.svg` gave two of its six boxes an amber accent and a heavier
  border, and a subtitle to two of six. Read literally that says "these two
  matter more" — a claim the diagram was not making. Uniform boxes, or an
  accent that earns itself.

- ➜ **Size the type for 830px, not for the canvas.** GitHub renders a README at
  roughly 830px wide, so a `1280`-wide drawing is shown at **0.65 scale** and its
  16px label arrives as **10px**. Multiply every font size by `830 / viewBox_width`
  before deciding whether it is readable. Where a diagram does not need the width,
  narrowing the canvas to `980` is the better lever — it raises the scale to 0.85
  without enlarging, and therefore without crowding, anything. `deploy.svg` and
  `elliott-wave.svg` are drawn that way.

- ➜ **Fit text to its box; never trust a font size by eye.** SVG `<text>` does not
  wrap and is not clipped to its parent — an overlong label is simply drawn
  through the border and off the edge, and nothing warns you. The generators use a
  `_fits()`/`fits()` helper that returns the largest size which still fits, and
  captions that cannot fit are split across two lines rather than shrunk.

- ➜ **Check a change by rendering it, not by reasoning about it.** Every overflow
  fixed in this directory was invisible in the numbers and obvious in a screenshot
  at 830px.

- ➜ **Render at a time OTHER than zero, with [`seek.html`](seek.html).** A browser
  holds an active SMIL animation at its `t=0` value, so a plain screenshot shows
  only what is on screen *before* anything animates in. Most of these diagrams
  build themselves — callout lists, annotations, decision branches — and none of
  that exists at `t=0`. A whole column of clipped labels in `divergence.svg` was
  signed off as clean because the screenshot that "proved" it could not show them.

  ```
  chrome --headless --allow-file-access-from-files --window-size=880,1200      --screenshot=out.png --virtual-time-budget=6000      "file:///<abs path>/tools/seek.html?t=8&f=divergence.svg,ecosystem.svg"
  ```

  `f` is a comma-separated list relative to the harness, `t` the moment in each
  file's own loop. It inlines the SVG so `setCurrentTime()` reaches it, renders at
  830px, and does **not** clip overflow — overflow is the thing being looked for.


---

<div align="center">

<sub>⬅ <a href="../../../README.md">Project README</a> · <a href="..">docs/assets/</a></sub>

</div>
