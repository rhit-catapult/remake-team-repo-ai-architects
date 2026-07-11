// Stepper Control Panel firmware
// Arduino Mega 2560 — 5× 28BYJ-48 via ULN2003. Direct manual control.
//
// Non-blocking: all five motors can move/run simultaneously, stepped from ONE
// micros()-based loop. No stepper libraries, no timer ISRs.
//
// PROTOCOL (host -> board)
//   "A <m> <steps> <dir> <speed>\n"  move motor m by <steps> steps in <dir> (+1/-1)
//   "R <m> <dir> <speed>\n"          run motor m continuously
//   "S <m>\n"                         stop motor m
//   "X\n"                             stop ALL motors (emergency)
//   "P\n"                             ping
// board -> host
//   "R\n" ready   "A\n" ack   "D <m>\n" done (motor m finished a move)   "O\n" pong

#include <Arduino.h>

const uint8_t NUM_MOTORS = 5;

// ULN2003 IN1..IN4 for each motor, in physical wiring order.
// M3/M4/M5 are wired to the low pins (2..13), not 30..41 — see the AccelStepper
// reference sketch (its HALF4WIRE order is IN1, IN3, IN2, IN4).
const uint8_t IN[NUM_MOTORS][4] = {
  {22, 23, 24, 25},   // M1
  {26, 27, 28, 29},   // M2
  { 2,  3,  4,  5},   // M3
  { 6,  7,  8,  9},   // M4
  {10, 11, 12, 13},   // M5
};

// Per-motor rotation correction. M1 and M5 are wired/oriented so they spin
// opposite to M2/M3/M4; flip them so a "+" command turns every motor the same
// physical way. +1 = as-is, -1 = reversed.
const int8_t DIR_SIGN[NUM_MOTORS] = { -1, 1, 1, 1, -1 };

// Half-step drive table (IN1..IN4).
const uint8_t SEQ[8][4] = {
  {1, 0, 0, 0},
  {1, 1, 0, 0},
  {0, 1, 0, 0},
  {0, 1, 1, 0},
  {0, 0, 1, 0},
  {0, 0, 1, 1},
  {0, 0, 0, 1},
  {1, 0, 0, 1},
};

// Speed limits (mirror config.py).
const uint16_t MIN_SPEED = 1;
const uint16_t MAX_SPEED = 600;

struct M {
  int8_t   phase;             // 0..7 current position in SEQ
  int8_t   dir;               // +1 / -1
  uint32_t step_interval_us;  // 1e6 / speed
  uint32_t last_step_us;      // micros() of last step
  int32_t  steps_remaining;   // >0 for A moves; -1 = run forever (R)
  bool     active;
};

M motors[NUM_MOTORS];

// Serial line buffer.
char line[48];
uint8_t line_len = 0;

uint16_t clampSpeed(long s) {
  if (s < (long)MIN_SPEED) return MIN_SPEED;
  if (s > (long)MAX_SPEED) return MAX_SPEED;
  return (uint16_t)s;
}

void applyPhase(uint8_t m) {
  for (uint8_t i = 0; i < 4; i++) {
    digitalWrite(IN[m][i], SEQ[motors[m].phase][i] ? HIGH : LOW);
  }
}

void coilsOff(uint8_t m) {
  for (uint8_t i = 0; i < 4; i++) digitalWrite(IN[m][i], LOW);
}

void stepMotor(uint8_t m) {
  motors[m].phase = (motors[m].phase + motors[m].dir + 8) % 8;
  applyPhase(m);
  if (motors[m].steps_remaining > 0) {
    motors[m].steps_remaining--;
    if (motors[m].steps_remaining == 0) {
      motors[m].active = false;
      coilsOff(m);
      Serial.print("D ");
      Serial.println(m);
    }
  }
}

void startMove(uint8_t m, int32_t steps, int8_t dir, uint16_t speed) {
  motors[m].dir = ((dir < 0) ? -1 : 1) * DIR_SIGN[m];
  motors[m].steps_remaining = steps;      // -1 == run forever
  motors[m].step_interval_us = 1000000UL / clampSpeed(speed);
  motors[m].last_step_us = micros();
  motors[m].active = true;
}

void stopMotor(uint8_t m) {
  motors[m].active = false;
  motors[m].steps_remaining = 0;
  coilsOff(m);
}

void handleLine() {
  if (line_len == 0) return;
  char cmd = line[0];

  if (cmd == 'A') {
    int m, steps, dir, speed;
    if (sscanf(line + 1, "%d %d %d %d", &m, &steps, &dir, &speed) == 4) {
      if (m >= 0 && m < NUM_MOTORS) {
        startMove(m, steps, dir, speed);
        Serial.println("A");
      }
    }
  } else if (cmd == 'R') {
    int m, dir, speed;
    if (sscanf(line + 1, "%d %d %d", &m, &dir, &speed) == 3) {
      if (m >= 0 && m < NUM_MOTORS) {
        startMove(m, -1, dir, speed);     // forever
        Serial.println("A");
      }
    }
  } else if (cmd == 'S') {
    int m;
    if (sscanf(line + 1, "%d", &m) == 1 && m >= 0 && m < NUM_MOTORS) {
      stopMotor(m);
      Serial.println("A");
    }
  } else if (cmd == 'X') {
    for (uint8_t m = 0; m < NUM_MOTORS; m++) stopMotor(m);
    Serial.println("A");
  } else if (cmd == 'P') {
    Serial.println("O");
  }
}

void readSerial() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      line[line_len] = '\0';
      handleLine();
      line_len = 0;
    } else if (line_len < sizeof(line) - 1) {
      line[line_len++] = c;
    }
  }
}

void setup() {
  for (uint8_t m = 0; m < NUM_MOTORS; m++) {
    for (uint8_t i = 0; i < 4; i++) {
      pinMode(IN[m][i], OUTPUT);
      digitalWrite(IN[m][i], LOW);
    }
    motors[m].phase = 0;
    motors[m].dir = 1;
    motors[m].step_interval_us = 1000000UL / 200;
    motors[m].last_step_us = 0;
    motors[m].steps_remaining = 0;
    motors[m].active = false;
  }
  Serial.begin(115200);
  Serial.println("R");
}

void loop() {
  uint32_t now = micros();
  for (uint8_t m = 0; m < NUM_MOTORS; m++) {
    if (motors[m].active &&
        (uint32_t)(now - motors[m].last_step_us) >= motors[m].step_interval_us) {
      motors[m].last_step_us = now;
      stepMotor(m);
    }
  }
  readSerial();
}
