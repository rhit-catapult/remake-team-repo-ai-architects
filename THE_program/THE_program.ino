#include <Servo.h>

Servo myServo;
String inputString = "";      // a String to hold incoming data
bool stringComplete = false;  // whether the string is complete

void setup() {
  myServo.attach(9);
  Serial.begin(115200);
  // reserve 200 bytes for the inputString:
  inputString.reserve(200);
}

void loop() {
  // print the string when a newline arrives:
  if (stringComplete) {
    Serial.println(inputString);

    int spaceIndex = inputString.indexOf(' ');
    if (spaceIndex != -1) {
      String angleString = inputString.substring(spaceIndex + 1);
      angleString.trim();
      int angle = angleString.toInt();
      myServo.write(angle);
    } else {
      myServo.write(0);
    }

    inputString = "";
    stringComplete = false;
  }
}

void serialEvent() {
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    if (inChar == '\n') {
      stringComplete = true;
    } else { 
      inputString += inChar;
    }
  }
}
