# IoT for Young Makers

A free, interactive 3D course that teaches complete beginners aged 10–15 to build and code IoT projects
with an **ESP32 DevKit** and **MicroPython**, one new idea per lesson.

**Open the course:** https://nkiliyumwami.github.io/iot-kids-course/

## What's here

| Path | What it is |
| --- | --- |
| `index.html` | Course home page: lesson path, progress, kit list |
| `course.js` | The list of lessons (title, status, new idea), shared by every page |
| `lessons/NN-slug/index.html` | One self-contained lesson per folder |
| `AGENT.md` | The brief the daily lesson agent follows |
| `ROADMAP.md` | Planned lessons and a log of each run |
| `tools/check.sh` | Screenshots a lesson in headless Chromium and reports script errors |

No build step. Pages use three.js r128 and Google Fonts from public CDNs, so they need an internet connection.
Progress is stored only in the learner's browser.

## How new lessons arrive

A scheduled Claude agent runs every morning. It builds the next lesson in `ROADMAP.md`, tests it and opens a
pull request. Nothing reaches learners until the pull request is reviewed and merged into `main`; GitHub Pages
then republishes the site.

## Publishing (one-time setup)

Settings → Pages → Build and deployment → Source: **Deploy from a branch**, Branch: **main**, folder **/ (root)**.
