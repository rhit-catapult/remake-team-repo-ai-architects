#include <Servo.h>

Servo myServo;

void setup() {
  pinMode(13, OUTPUT);
  myServo.attach(9);
  myServo.write(90);
  delay(3000);
}

void loop() {
  myServo.write(0);
  digitalWrite(13, HIGH);
  delay(500);

  myServo.write(180);
  delay(500);
  digitalWrite(13, LOW);
}