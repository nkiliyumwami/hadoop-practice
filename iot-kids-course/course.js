/* IoT for Young Makers: the list of lessons, shared by the home page and every lesson.
   To add a lesson: add its folder under lessons/, then set its status here to 'ready'. */
(function () {
  'use strict';
  const lessons = [
    { n: 1, slug: '01-traffic-light', title: 'My First Traffic Light', unit: 1, status: 'ready', minutes: 45,
      idea: 'Outputs: the ESP32 switches pins on and off to light three LEDs.',
      hardware: 'ESP32 DevKit, breadboard, 3 LEDs, 3 × 330 Ω resistors, jumper wires',
      code: 'Pin(…, Pin.OUT), value(1) / value(0), while True:, time.sleep()' },
    { n: 2, slug: '02-patterns', title: 'Make It Yours: Light Patterns', unit: 1, status: 'planned', minutes: 40,
      idea: 'Same circuit, smarter code: name things and reuse them.',
      hardware: 'Nothing new',
      code: 'variables, a set_lights() function, print()' },
    { n: 3, slug: '03-pedestrian-button', title: 'The Pedestrian Button', unit: 1, status: 'planned', minutes: 45,
      idea: 'Inputs: the ESP32 listens to a button.',
      hardware: 'Push button',
      code: 'Pin.IN with a pull-up, if' },
    { n: 4, slug: '04-fair-crossing', title: 'A Fair Crossing', unit: 1, status: 'planned', minutes: 40,
      idea: 'Remember a button press and wait for a safe moment.',
      hardware: 'Nothing new',
      code: 'a "button was pressed" variable, why buttons bounce' },
    { n: 5, slug: '05-crossing-sound', title: 'Beep Beep: Crossing Sound', unit: 1, status: 'planned', minutes: 40,
      idea: 'Sound is just switching very fast.',
      hardware: 'Buzzer',
      code: 'PWM: frequency and on/off time' },
    { n: 6, slug: '06-measuring-light', title: 'Measuring Light', unit: 1, status: 'planned', minutes: 45,
      idea: 'Analog inputs: reading "how much", not just on or off.',
      hardware: 'Light sensor (LDR) + 10 kΩ resistor',
      code: 'ADC readings from 0 to 4095' },
    { n: 7, slug: '07-night-mode', title: 'Night Mode', unit: 1, status: 'planned', minutes: 40,
      idea: 'Make a decision from a sensor reading.',
      hardware: 'Nothing new',
      code: 'thresholds, a flashing-yellow mode' },
    { n: 8, slug: '08-hello-wifi', title: 'Hello, Wi-Fi', unit: 2, status: 'planned', minutes: 45,
      idea: 'What a network and an IP address are.',
      hardware: 'Nothing new (the ESP32 has Wi-Fi built in)',
      code: 'network.WLAN, connecting and printing the IP address' },
    { n: 9, slug: '09-status-page', title: 'Your Traffic Light’s Web Page', unit: 2, status: 'planned', minutes: 45,
      idea: 'The ESP32 serves a web page your phone can open.',
      hardware: 'Nothing new',
      code: 'a tiny web server, showing the current light' },
    { n: 10, slug: '10-phone-control', title: 'Control It From Your Phone', unit: 2, status: 'planned', minutes: 50,
      idea: 'Your phone sends commands, but safety rules still win.',
      hardware: 'Nothing new',
      code: 'handling requests, keeping the crossing safe' },
  ];
  const units = {
    1: { name: 'Build the thing', blurb: 'Lights, buttons, sound and sensors: a traffic light that works on its own.' },
    2: { name: 'Connect it', blurb: 'Put your traffic light on Wi-Fi and talk to it from a phone. This is the “Internet” in Internet of Things.' },
  };
  const KEY = 'iotkids.progress';
  function readProgress() {
    try { return JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (e) { return {}; }
  }
  function saveProgress(slug, patch) {
    try {
      const all = readProgress();
      all[slug] = Object.assign({}, all[slug], patch, { at: Date.now() });
      localStorage.setItem(KEY, JSON.stringify(all));
    } catch (e) { /* storage unavailable: progress simply isn't remembered */ }
  }
  function nextLesson(slug) {
    const i = lessons.findIndex((l) => l.slug === slug);
    return i >= 0 ? lessons[i + 1] || null : null;
  }
  window.COURSE = { title: 'IoT for Young Makers', lessons, units, readProgress, saveProgress, nextLesson };
})();
