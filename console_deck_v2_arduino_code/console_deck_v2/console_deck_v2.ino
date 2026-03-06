#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// --- Pin definitions ---
#define CLK 5       // Rotary encoder CLK
#define DT 4        // Rotary encoder DT
#define SW 3        // Rotary encoder push button
// I2C for SSD1306: A4 (SDA), A5 (SCL) — hardware I2C

// BUTTON_1..BUTTON_9 in desired order
const int buttonPins[] = {6, 7, 8, 9, 10, 11, 12, A0, A1};
const int NUM_BUTTONS = 9;

// --- OLED display ---
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
#define SCREEN_ADDRESS 0x3C

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
bool displayReady = false;

// --- Mode state (fixed-size char arrays to avoid heap fragmentation) ---
#define MAX_MODES 10
#define MAX_NAME_LEN 12
char modeNames[MAX_MODES][MAX_NAME_LEN + 1];
int numModes = 0;
int currentMode = 0;
int virtualMode = 0;       // unbounded position for endless scroll illusion
bool modesReceived = false;

// Encoder quadrature lookup: maps 4-bit (prevAB << 2 | newAB) to direction
// +1 = CW, -1 = CCW, 0 = bounce/invalid
static const int8_t ENC_STATES[] = {0,-1,1,0, 1,0,0,-1, -1,0,0,1, 0,1,-1,0};

// --- Wheel animation ---
float displayOffset = 0.0;
unsigned long lastKnobTime = 0;
bool wheelActive = false;
#define WHEEL_TIMEOUT 1500   // ms to settle after last knob turn
#define ITEM_HEIGHT 20       // pixels per mode entry in picker

// --- Display refresh ---
unsigned long lastDisplayUpdate = 0;
#define DISPLAY_INTERVAL 50  // ms between display refreshes

void setup() {
  Serial.begin(9600);

  // Encoder pins
  pinMode(CLK, INPUT);
  pinMode(DT, INPUT);
  pinMode(SW, INPUT_PULLUP);

  // Button pins
  for (int i = 0; i < NUM_BUTTONS; i++) {
    pinMode(buttonPins[i], INPUT_PULLUP);
  }

  // OLED init
  if (display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
    displayReady = true;
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(1);
    display.setCursor(16, 24);
    display.println("Waiting for");
    display.setCursor(28, 36);
    display.println("config...");
    display.display();
  }

  // Tell Python we're ready to receive config
  Serial.println("READY");
}

void loop() {
  handleSerialInput();
  handleEncoder();
  handleEncoderPress();
  handleButtons();

  // Throttle display updates
  unsigned long now = millis();
  if (displayReady && now - lastDisplayUpdate >= DISPLAY_INTERVAL) {
    updateDisplay();
    lastDisplayUpdate = now;
  }
}

// --- Serial input: parse MODES: and SET_MODE: from Python ---
// Uses a static char buffer to avoid any heap allocation (String class)
static char serialBuf[80];
static uint8_t serialPos = 0;

void processLine(const char* line) {
  if (strncmp(line, "MODES:", 6) == 0) {
    const char* payload = line + 6;
    numModes = 0;
    const char* start = payload;
    for (const char* p = payload; ; p++) {
      if (*p == ',' || *p == '\0') {
        if (numModes < MAX_MODES) {
          int len = p - start;
          if (len > MAX_NAME_LEN) len = MAX_NAME_LEN;
          memcpy(modeNames[numModes], start, len);
          modeNames[numModes][len] = '\0';
          numModes++;
        }
        if (*p == '\0') break;
        start = p + 1;
      }
    }
    modesReceived = true;
    if (currentMode >= numModes) currentMode = 0;
    virtualMode = currentMode;
    displayOffset = (float)virtualMode;
  }
  else if (strncmp(line, "SET_MODE:", 9) == 0) {
    int idx = atoi(line + 9);
    if (idx >= 0 && idx < numModes) {
      currentMode = idx;
      virtualMode = idx;
      displayOffset = (float)idx;
      wheelActive = false;
    }
  }
}

void handleSerialInput() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      if (serialPos > 0) {
        // Trim trailing \r
        if (serialBuf[serialPos - 1] == '\r') serialPos--;
        serialBuf[serialPos] = '\0';
        processLine(serialBuf);
      }
      serialPos = 0;
    } else if (serialPos < sizeof(serialBuf) - 1) {
      serialBuf[serialPos++] = c;
    }
  }
}

// --- Encoder rotation: cycle through modes ---
void handleEncoder() {
  // Track both CLK and DT as a 2-bit state; accumulate valid steps
  static uint8_t oldAB = 0b11;
  static int8_t  accumulator = 0;

  uint8_t clkVal = digitalRead(CLK);
  uint8_t dtVal  = digitalRead(DT);
  uint8_t newAB  = (clkVal << 1) | dtVal;
  uint8_t prevAB = oldAB & 0x03;
  oldAB = ((oldAB << 2) | newAB) & 0x0f;
  int8_t step = ENC_STATES[oldAB];
  accumulator += step;

  // One detent = 2 raw quadrature steps on this encoder
  if (accumulator >= 2) {
    accumulator = 0;
    if (!modesReceived || numModes == 0) return;
    virtualMode++;
    currentMode = ((virtualMode % numModes) + numModes) % numModes;
    Serial.print("MODE:"); Serial.println(currentMode);
    lastKnobTime = millis(); wheelActive = true;
  } else if (accumulator <= -2) {
    accumulator = 0;
    if (!modesReceived || numModes == 0) return;
    virtualMode--;
    currentMode = ((virtualMode % numModes) + numModes) % numModes;
    Serial.print("MODE:"); Serial.println(currentMode);
    lastKnobTime = millis(); wheelActive = true;
  }
}

// --- Encoder button press ---
void handleEncoderPress() {
  if (digitalRead(SW) == LOW) {
    Serial.println("MODE_PRESS");
    delay(200);  // debounce
  }
}

// --- Button presses: BUTTON_1 through BUTTON_9 ---
void handleButtons() {
  for (int i = 0; i < NUM_BUTTONS; i++) {
    if (digitalRead(buttonPins[i]) == LOW) {
      Serial.print("BUTTON_");
      Serial.println(i + 1);
      delay(200);  // debounce
    }
  }
}

// --- OLED display: wheel picker or static mode name ---
void updateDisplay() {
  if (!modesReceived || numModes == 0) return;

  display.clearDisplay();

  if (wheelActive) {
    // Animate offset toward virtualMode (unbounded, no wrapping)
    float target = (float)virtualMode;
    float diff = target - displayOffset;
    displayOffset += diff * 0.3;
    if (abs(diff) < 0.05) displayOffset = target;

    // Check timeout
    if (millis() - lastKnobTime > WHEEL_TIMEOUT) {
      wheelActive = false;
      displayOffset = target;
    }

    // Draw picker
    int centerY = (SCREEN_HEIGHT - ITEM_HEIGHT) / 2;

    // Draw highlight rectangle for center slot
    display.drawRoundRect(0, centerY - 2, SCREEN_WIDTH, ITEM_HEIGHT + 4, 4, SSD1306_WHITE);

    // Draw visible items — use virtualMode for positions, modulo for names
    for (int offset = -2; offset <= 2; offset++) {
      int virtualIdx = virtualMode + offset;
      int modeIdx = ((virtualIdx % numModes) + numModes) % numModes;

      float yFloat = (float)centerY + (float)offset * ITEM_HEIGHT
                      - (displayOffset - (float)virtualMode) * ITEM_HEIGHT;
      int y = (int)yFloat;

      if (y > -ITEM_HEIGHT && y < SCREEN_HEIGHT) {
        // Use a stack buffer — no heap allocation
        char name[MAX_NAME_LEN + 1];
        strncpy(name, modeNames[modeIdx], MAX_NAME_LEN);
        name[MAX_NAME_LEN] = '\0';

        if (offset == 0) {
          // Center item: larger text
          display.setTextSize(2);
          if (strlen(name) > 10) name[10] = '\0';
        } else {
          // Adjacent items: smaller text
          display.setTextSize(1);
        }

        int16_t x1, y1;
        uint16_t w, h;
        display.getTextBounds(name, 0, 0, &x1, &y1, &w, &h);
        display.setCursor((SCREEN_WIDTH - w) / 2, y + (ITEM_HEIGHT - h) / 2);
        display.print(name);
      }
    }
  } else {
    // Static display: show current mode name large and centered
    display.setTextSize(2);
    char name[MAX_NAME_LEN + 1];
    strncpy(name, modeNames[currentMode], MAX_NAME_LEN);
    name[MAX_NAME_LEN] = '\0';
    if (strlen(name) > 10) name[10] = '\0';

    int16_t x1, y1;
    uint16_t w, h;
    display.getTextBounds(name, 0, 0, &x1, &y1, &w, &h);
    display.setCursor((SCREEN_WIDTH - w) / 2, (SCREEN_HEIGHT - h) / 2);
    display.print(name);
  }

  display.display();
}
