# Roadmap

One new idea per lesson. Each daily run takes the first unchecked item. See `AGENT.md` for the rules.

## Part 1: Build the thing

- [x] **1. My First Traffic Light** (`01-traffic-light`): outputs. ESP32 switches D25/D26/D27 to light three LEDs
  through 330 Ω resistors. `Pin(…, Pin.OUT)`, `value()`, `while True:`, `time.sleep()`.
- [ ] **2. Make It Yours: Light Patterns** (`02-patterns`): no new hardware. Variables for the times, a
  `set_lights(r, y, g)` function so each phase is one line, and `print()` to see what the program is doing
  (show the Thonny console). Challenge: design your own pattern.
- [ ] **3. The Pedestrian Button** (`03-pedestrian-button`): a push button on a safe input pin.
  `Pin.IN` with `Pin.PULL_UP` (why a pin "floats" without it, why pressed reads 0), and `if`. First version: while
  the button is held, the light shows red.
- [ ] **4. A Fair Crossing** (`04-fair-crossing`): no new hardware. Remember a press in a variable, finish the
  green safely, then give pedestrians their turn. Why buttons "bounce" and a simple fix.
- [ ] **5. Beep Beep: Crossing Sound** (`05-crossing-sound`): a buzzer that beeps while pedestrians may cross.
  `PWM`: sound is switching on and off very fast; frequency changes the pitch.
- [ ] **6. Measuring Light** (`06-measuring-light`): an LDR with a 10 kΩ resistor as a voltage divider on an ADC1 pin.
  Analog vs digital, readings from 0 to 4095, printing the numbers while covering the sensor.
- [ ] **7. Night Mode** (`07-night-mode`): no new hardware. A threshold turns on flashing yellow when it's dark.

## Part 2: Connect it

- [ ] **8. Hello, Wi-Fi** (`08-hello-wifi`): what a network and an IP address are; `network.WLAN` to connect and print the IP.
  Keep Wi-Fi passwords out of shared code (a separate `secrets.py`).
- [ ] **9. Your Traffic Light's Web Page** (`09-status-page`): a tiny web server on the ESP32 that shows the current light
  on a phone on the same Wi-Fi. Read-only.
- [ ] **10. Control It From Your Phone** (`10-phone-control`): buttons on the web page send commands; the safety rules
  (never red and green together, pedestrians get their full time) still win.

## After lesson 10

When every lesson above is ticked, use each run to improve one existing lesson: clearer "Why?" answers,
an extra interactive demo, or fixes from the course owner's comments. Add any new lesson ideas here first as unchecked items.

## Log

- 2026-10-09: Course set up. Lesson 1 moved from the original prototype, with a course home page, progress saving and this roadmap.
