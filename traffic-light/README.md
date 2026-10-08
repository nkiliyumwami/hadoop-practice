# My First Traffic Light

An interactive 3D lesson for children aged 10–15 and complete electronics beginners.
Learners watch a finished traffic light run, meet each part, build the circuit one
connection at a time, see a MicroPython program on an ESP32 DevKit control the LEDs, then experiment and take a short quiz.

Open `index.html` in a modern browser. It needs an internet connection to load three.js
(r128) and the fonts from public CDNs. There is no build step.

## Lesson stages

| Stage | Steps | What happens |
| --- | --- | --- |
| A · See it | 1 | The finished light runs red 5 s → green 5 s → yellow 2 s, one LED at a time, with a countdown. |
| B · Meet the parts | 4 | Click the controller, LED, resistor, breadboard and jumper wire to learn each job. An enlarged LED shows the anode, the cathode and the flat edge. "How electricity flows" explains the loop with a water-pipe analogy and lets learners unplug the ground wire. "Why do we need a resistor?" shows a current meter (4 mA vs. far too much) with a pretend no-resistor demo. |
| C · Build it | 7 | Breadboard connections, then the wiring plan one connection per step, then the complete loop with current-flow dots. Every build step has a "Why is it built this way?" card (why this pin, why this row and hole, why the resistor crosses the gap, why the legs are in separate rows, why ground…). Answers open as the animation reaches them, and "Show me on the board" lights up the relevant holes. |
| D · Code it | 2 | MicroPython (`main.py`): pin setup with `Pin(…, Pin.OUT)`, then the `while True:` loop with the active lines highlighted in sync with the lit LED, plus a **Step through** control. |
| E · Experiment | 2 | A 2–10 s green-time slider updates the animation, countdown and code together, followed by a three-question quiz with hints. |

## Wiring plan (as built in the lesson)

- D25 (GPIO 25) → 330 Ω resistor → red LED anode (row 7; cathode in row 8)
- D26 (GPIO 26) → 330 Ω resistor → yellow LED anode (row 15; cathode in row 16)
- D27 (GPIO 27) → 330 Ω resistor → green LED anode (row 23; cathode in row 24)
- All three LED cathodes → breadboard ground rail (−)
- Ground rail → ESP32 GND (the GND pin next to D13)

The board is a 30-pin ESP32 DevKit V1 (3.3 V pins). Female-to-male jumper wires connect its pins to the breadboard.
Each resistor bridges the breadboard's centre gap. Each LED's two legs sit in separate rows.

## Controls

- Drag to rotate, scroll or pinch to zoom, right-drag to pan. **Reset view** returns to the step's camera.
- **Previous / Next**, **Replay this step**, **Pause**, **Show labels**, **Reset lesson** (click twice to confirm).
  Reset restores the 5-second green time, the quiz and the lesson position.
- Left and right arrow keys also move between steps.

This is an educational visualization, not an electrical safety test.
