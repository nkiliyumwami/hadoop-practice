# My First Traffic Light

An interactive 3D lesson for children aged 10–15 and complete electronics beginners.
Learners watch a finished traffic light run, meet each part, build the circuit one
connection at a time, see the Arduino code control the LEDs, then experiment and take a short quiz.

Open `index.html` in a modern browser. It needs an internet connection to load three.js
(r128) and the fonts from public CDNs. There is no build step.

## Lesson stages

| Stage | Steps | What happens |
| --- | --- | --- |
| A · See it | 1 | The finished light runs red 5 s → green 5 s → yellow 2 s, one LED at a time, with a countdown. |
| B · Meet the parts | 2 | Click the controller, LED, resistor, breadboard and jumper wire to learn each job. An enlarged LED shows the anode, the cathode and the flat edge. |
| C · Build it | 7 | Breadboard connections, then the wiring plan one connection per step, then the complete loop with current-flow dots. |
| D · Code it | 2 | `setup()` and `loop()` with the active lines highlighted in sync with the lit LED, plus a **Step through** control. |
| E · Experiment | 2 | A 2–10 s green-time slider updates the animation, countdown and code together, followed by a multiple-choice quiz. |

## Wiring plan (as built in the lesson)

- D8 → 330 Ω resistor → red LED anode (rows 7 / cathode in row 8)
- D9 → 330 Ω resistor → yellow LED anode (rows 15 / cathode in row 16)
- D10 → 330 Ω resistor → green LED anode (rows 23 / cathode in row 24)
- All three LED cathodes → breadboard ground rail (−)
- Ground rail → Arduino GND

Each resistor bridges the breadboard's centre gap. Each LED's two legs sit in separate rows.

## Controls

- Drag to rotate, scroll or pinch to zoom, right-drag to pan. **Reset view** returns to the step's camera.
- **Previous / Next**, **Replay this step**, **Pause**, **Show labels**, **Reset lesson** (click twice to confirm).
  Reset restores the 5-second green time, the quiz and the lesson position.
- Left and right arrow keys also move between steps.

This is an educational visualization, not an electrical safety test.
