/*
  Microstation main sketch
  https://github.com/TheCheese42/microstation/tree/main/microstation/arduino/arduino.ino
  From https://github.com/TheCheese42/microstation
  Microstation is licensed under GPLv3
*/

const String VERSION = "0.1.0";

// Constants are set at compile time by the Microstation client
const String COMPILE_CORE = "{core}";
const String COMPILE_BOARD = "{board}";
const String COMPILE_MICROSTATION_VERSION = "{microstation_version}";
const String COMPILE_ARDUINO_CLI_VERSION = "{arduino_cli_version}";
const String COMPILE_ARDUINO_CLI_COMMIT = "{arduino_cli_commit}";
const String COMPILE_ARDUINO_CLI_DATE = "{arduino_cli_date}";
const int DIGITAL_JITTER_DELAY = {digital_jitter_delay};

int digital_input_pins[200] = {};
int digital_input_states[200] = {};
int digital_input_start_times[200] = {};  // Digital input devices may jitter and need a small delay
int digital_input_count = 0;

int analog_input_pins[200] = {};
int analog_input_states[200] = {};
int analog_input_count = 0;

int digital_output_pins[200] = {};
int digital_output_count = 0;

int analog_output_pins[200] = {};
int analog_output_count = 0;


void exec_task(String task);
void poll_digital_input();
void poll_analog_input();


void print_debug() {
  Serial.println("DEBUG [INFO] Microstation - Version " + VERSION);
  Serial.print("DEBUG [INFO] Compiled at ");
  Serial.print(__DATE__);
  Serial.print(" ");
  Serial.println(__TIME__);
  Serial.print("DEBUG [INFO] Compiled from file ");
  Serial.println(__FILE__);
  Serial.println("DEBUG [INFO] Compiled for core " + COMPILE_CORE + " and board " + COMPILE_BOARD);
  Serial.println("DEBUG [INFO] Compiled by Microstation v" + COMPILE_MICROSTATION_VERSION);
  Serial.println("DEBUG [INFO] Using arduino-cli v" + COMPILE_ARDUINO_CLI_VERSION + " (Commit: " + COMPILE_ARDUINO_CLI_COMMIT + "; Date: " + COMPILE_ARDUINO_CLI_DATE + ")");
}


void setup() {
  Serial.begin(9600);
  delay(1000);  // Prevent first bytes to be lost
  print_debug();
  Serial.println("PINS_REQUESTED");
}


void loop() {
  if (Serial.available() > 0) {
    String receivedData = Serial.readStringUntil('\n');
    exec_task(receivedData);
  }
  poll_digital_input();
  poll_analog_input();
}


void exec_task(String task) {
  if (task.startsWith("RESET_PINS")) {
    digital_input_count = 0;
    analog_input_count = 0;
    digital_output_count = 0;
    digital_input_count = 0;
  } else if (task.startsWith("PINMODE")) {
    String mode = task.substring(8, 11);
    String io_mode = task.substring(12, 15);
    int pin = task.substring(16, 19).toInt();
    if (io_mode == "INP") {
      pinMode(pin, INPUT);
      if (mode == "DIG") {
        digital_input_pins[digital_input_count] = pin;
        digital_input_count++;
      } else if (mode == "ANA") {
        analog_input_pins[analog_input_count] = pin;
        analog_input_count++;
      } else {
        Serial.print("DEBUG [ERROR] Invalid mode: ");
        Serial.println(mode);
      }
    } else if (io_mode == "OUT") {
      pinMode(pin, OUTPUT);
      if (mode == "DIG") {
        digital_output_pins[digital_output_count] = pin;
        digital_output_count++;
      } else if (mode == "ANA") {
        analog_output_pins[analog_output_count] = pin;
        analog_output_count++;
      } else {
        Serial.print("DEBUG [ERROR] Invalid mode: ");
        Serial.println(mode);
      }
    } else {
      Serial.print("DEBUG [ERROR] Invalid IO mode: ");
      Serial.println(io_mode);
    }
  } else if (task.startsWith("WRITE")) {
    String mode = task.substring(6, 9);
    int pin = task.substring(10, 13).toInt();
    if (mode == "DIG") {
      int state = task.substring(14).toInt();
      digitalWrite(pin, state);
    } else if (mode == "ANA") {
      int state = task.substring(14, 21).toInt();
      analogWrite(pin, state);
    } else {
      Serial.print("DEBUG [ERROR] Invalid mode: ");
      Serial.println(mode);
    }
  } else {
    Serial.print("DEBUG [ERROR] Invalid task: ");
    Serial.println(task);
  }
}


void poll_digital_input() {
  for (int i = 0; i < digital_input_count; i++) {
    int pin = digital_input_pins[i];
    int prev_state = digital_input_states[i];
    int current_state = digitalRead(pin);
    if (current_state != prev_state) {
      if (!digital_input_start_times[i]) {
        digital_input_start_times[i] = millis();
        return;
      }
      if (millis() - digital_input_start_times[i] <= DIGITAL_JITTER_DELAY) {
        return;
      }
      digital_input_start_times[i] = 0;
      digital_input_states[i] = current_state;
      Serial.print("EVENT DIGITAL ");
      Serial.print(pin);
      Serial.print(" ");
      Serial.println(current_state);
    }
  }
}


void poll_analog_input() {
  for (int i = 0; i < analog_input_count; i++) {
    int pin = analog_input_pins[i];
    int prev_state = analog_input_states[i];
    int current_state = analogRead(pin);
    if (current_state != prev_state) {
      analog_input_states[i] = current_state;
      Serial.print("EVENT ANALOG ");
      Serial.print(pin);
      Serial.print(" ");
      Serial.println(current_state);
    }
  }
}
