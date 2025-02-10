/*
  Microstation main sketch
  https://github.com/TheCheese42/microstation/tree/main/microstation/arduino/arduino.ino
  From https://github.com/TheCheese42/microstation
  Microstation is licensed under GPLv3
*/

// Includes
{includes}

// Constants are set at compile time by the Microstation client
const String COMPILE_CORE = "{core}";
const String COMPILE_BOARD = "{board}";
const String VERSION = "{microstation_version}";
const String COMPILE_ARDUINO_CLI_VERSION = "{arduino_cli_version}";
const String COMPILE_ARDUINO_CLI_COMMIT = "{arduino_cli_commit}";
const String COMPILE_ARDUINO_CLI_DATE = "{arduino_cli_date}";
const int BAUDRATE = {baudrate};

uint8_t MAX_DIGITAL_INPUT_PINS = {max_digital_input_pins};
uint8_t digital_input_pins[{max_digital_input_pins}] = {};
uint8_t digital_input_states[{max_digital_input_pins}] = {};
uint8_t digital_input_start_times[{max_digital_input_pins}] = {};  // Digital input devices may jitter and need a small delay
uint8_t digital_input_debounce_times[{max_digital_input_pins}] = {};
uint8_t digital_input_count = 0;

uint8_t MAX_ANALOG_INPUT_PINS = {max_analog_input_pins};
uint8_t analog_input_pins[{max_analog_input_pins}] = {};
uint8_t analog_input_states[{max_analog_input_pins}] = {};
uint8_t analog_input_tolerances[{max_analog_input_pins}] = {};
uint8_t analog_input_count = 0;

// Other constants
{constants}


void exec_task(String task);
void poll_digital_input();
void poll_analog_input();


template <typename T>
void serialPrint(const T& data) {
  {print_hook}
  Serial.print(data);
}
template <typename T>
void serialPrintln(const T& data) {
  {println_hook}
  Serial.println(data);
}


void print_debug() {
  serialPrintln("DEBUG [INFO] Microstation - Version " + VERSION);
  serialPrint("DEBUG [INFO] Compiled at ");
  serialPrint(__DATE__);
  serialPrint(" ");
  serialPrintln(__TIME__);
  serialPrint("DEBUG [INFO] Compiled from file ");
  serialPrintln(__FILE__);
  serialPrintln("DEBUG [INFO] Compiled for core " + COMPILE_CORE + " and board " + COMPILE_BOARD);
  serialPrintln("DEBUG [INFO] Compiled by Microstation v" + VERSION);
  serialPrintln("DEBUG [INFO] Using arduino-cli v" + COMPILE_ARDUINO_CLI_VERSION + " (Commit: " + COMPILE_ARDUINO_CLI_COMMIT + "; Date: " + COMPILE_ARDUINO_CLI_DATE + ")");
}


void reset_data() {
  digital_input_count = 0;
  analog_input_count = 0;
  for (int i = 0; i < MAX_DIGITAL_INPUT_PINS; i++) {
    digital_input_debounce_times[i] = 0;
  }
  for (int i = 0; i < MAX_ANALOG_INPUT_PINS; i++) {
    analog_input_tolerances[i] = 0;
  }
}


void report_version() {
  serialPrint("VERSION ");
  serialPrintln(VERSION);
}


void setup() {
  Serial.begin(BAUDRATE);
  delay(1000);  // Prevent first bytes to be lost
  print_debug();
  report_version();

  // Additional setup code
  {setup}

  serialPrintln("PINS_REQUESTED");
}


void loop() {
  // Additional loop code
  {loop}

  if (Serial.available() > 0) {
    String receivedData = Serial.readStringUntil('\n');
    exec_task(receivedData);
  }
  poll_digital_input();
  poll_analog_input();
}


void exec_task(String task) {
  if (task == "") {
    return;
  } else if (task.startsWith("RESET_PINS")) {
    reset_data();
  } else if (task.startsWith("GET_VERSION")) {
    report_version();
  } else if (task.startsWith("PINMODE")) {
    String mode = task.substring(8, 11);
    String io_mode = task.substring(12, 15);
    int pin = task.substring(16, 19).toInt();
    if (io_mode == "INP") {
      pinMode(pin, INPUT_PULLUP);
      if (mode == "DIG") {
        if (digital_input_count >= MAX_DIGITAL_INPUT_PINS) {
          serialPrintln("DEBUG [CRITICAL] [TMDIP] Too many digital input pins");
        }
        digital_input_pins[digital_input_count] = pin;
        digital_input_count++;
      } else if (mode == "ANA") {
        if (analog_input_count >= MAX_ANALOG_INPUT_PINS) {
          serialPrintln("DEBUG [CRITICAL] [TMAIP] Too many analog input pins");
        }
        analog_input_pins[analog_input_count] = pin;
        analog_input_count++;
      } else {
        serialPrint("DEBUG [ERROR] Invalid mode: ");
        serialPrintln(mode);
      }
    } else if (io_mode == "OUT") {
      pinMode(pin, OUTPUT);
    } else {
      serialPrint("DEBUG [ERROR] Invalid IO mode: ");
      serialPrintln(io_mode);
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
      serialPrint("DEBUG [ERROR] Invalid mode: ");
      serialPrintln(mode);
    }
  } else if (task.startsWith("DIGITAL_DEBOUNCE")) {
    int pin = task.substring(17, 20).toInt();
    int time = task.substring(21, 25).toInt();
    digital_input_debounce_times[pin] = time;
  } else if (task.startsWith("ANALOG_TOLERANCE")) {
    int pin = task.substring(17, 20).toInt();
    int tolerance = task.substring(21, 27).toInt();
    analog_input_tolerances[pin] = tolerance;
  } else {
    serialPrint("DEBUG [ERROR] Invalid task: ");
    serialPrintln(task);
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
      unsigned int jitter_delay = digital_input_debounce_times[pin];
      if (millis() - digital_input_start_times[i] <= jitter_delay) {
        return;
      }
      digital_input_start_times[i] = 0;
      digital_input_states[i] = current_state;
      serialPrint("EVENT DIGITAL ");
      serialPrint(pin);
      serialPrint(" ");
      serialPrintln(current_state);
    }
  }
}


void poll_analog_input() {
  for (int i = 0; i < analog_input_count; i++) {
    int pin = analog_input_pins[i];
    int prev_state = analog_input_states[i];
    int current_state = analogRead(pin);
    int jitter_tolerance = analog_input_tolerances[pin];
    if (
      (current_state <= prev_state && current_state >= prev_state - jitter_tolerance)
      || (current_state >= prev_state && current_state <= prev_state + jitter_tolerance)
    ) {
      return;
    }
    analog_input_states[i] = current_state;
    serialPrint("EVENT ANALOG ");
    serialPrint(pin);
    serialPrint(" ");
    serialPrintln(current_state);
  }
}
