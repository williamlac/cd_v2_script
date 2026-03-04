#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// --- Pin definitions ---
#define CLK 5       // Rotary encoder CLK
#define DT 4        // Rotary encoder DT
#define SW 3        // Rotary encoder push button
// I2C for SSD1306: A4 (SDA), A5 (SCL) — hardware I2C

// Pin order matches BUTTON_1..BUTTON_10 for the Python side
// Schematic: SW8=A1, SW9=A0, SW5=D11, SW6=D10, SW7=D9, SW11=D2, SW2=D6, SW3=D7, SW4=D8, SW10=D12
const int buttonPins[] = {A1, A0, 11, 10, 9, 2, 6, 7, 8, 12};
const int NUM_BUTTONS = 10;

// --- OLED display ---
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
#define SCREEN_ADDRESS 0x3C

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
bool displayReady = false;

// --- Mode state ---
#define MAX_MODES 10
String modeNames[MAX_MODES];
int numModes = 0;
int currentMode = 0;
bool modesReceived = false;

// --- Encoder state ---
int lastStateCLK;

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
  lastStateCLK = digitalRead(CLK);

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
void handleSerialInput() {
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();

    if (line.startsWith("MODES:")) {
      String payload = line.substring(6);
      numModes = 0;
      int start = 0;
      for (int i = 0; i <= (int)payload.length(); i++) {
        if (i == (int)payload.length() || payload[i] == ',') {
          if (numModes < MAX_MODES) {
            modeNames[numModes] = payload.substring(start, i);
            numModes++;
          }
          start = i + 1;
        }
      }
      modesReceived = true;
      if (currentMode >= numModes) currentMode = 0;
      displayOffset = (float)currentMode;
    }
    else if (line.startsWith("SET_MODE:")) {
      int idx = line.substring(9).toInt();
      if (idx >= 0 && idx < numModes) {
        currentMode = idx;
        displayOffset = (float)idx;
        wheelActive = false;
      }
    }
  }
}

// --- Encoder rotation: cycle through modes ---
void handleEncoder() {
  if (!modesReceived || numModes == 0) return;

  int currentStateCLK = digitalRead(CLK);
  if (currentStateCLK != lastStateCLK) {
    if (digitalRead(DT) != currentStateCLK) {
      currentMode++;
      if (currentMode >= numModes) currentMode = 0;
    } else {
      currentMode--;
      if (currentMode < 0) currentMode = numModes - 1;
    }

    Serial.print("MODE:");
    Serial.println(currentMode);

    lastKnobTime = millis();
    wheelActive = true;
  }
  lastStateCLK = currentStateCLK;
}

// --- Encoder button press ---
void handleEncoderPress() {
  if (digitalRead(SW) == LOW) {
    Serial.println("MODE_PRESS");
    delay(200);  // debounce
  }
}

// --- Button presses: BUTTON_1 through BUTTON_10 ---
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
    // Animate offset toward current mode
    float diff = (float)currentMode - displayOffset;

    // Handle wrapping for smooth animation
    if (diff > numModes / 2.0) diff -= numModes;
    if (diff < -numModes / 2.0) diff += numModes;

    displayOffset += diff * 0.3;

    // Wrap displayOffset into valid range
    if (displayOffset < 0) displayOffset += numModes;
    if (displayOffset >= numModes) displayOffset -= numModes;

    if (abs(diff) < 0.05) displayOffset = (float)currentMode;

    // Check timeout
    if (millis() - lastKnobTime > WHEEL_TIMEOUT) {
      wheelActive = false;
      displayOffset = (float)currentMode;
    }

    // Draw picker
    int centerY = (SCREEN_HEIGHT - ITEM_HEIGHT) / 2;

    // Draw highlight rectangle for center slot
    display.drawRoundRect(0, centerY - 2, SCREEN_WIDTH, ITEM_HEIGHT + 4, 4, SSD1306_WHITE);

    // Draw visible items
    for (int offset = -2; offset <= 2; offset++) {
      int modeIdx = currentMode + offset;
      // Handle wrapping
      while (modeIdx < 0) modeIdx += numModes;
      while (modeIdx >= numModes) modeIdx -= numModes;

      float yFloat = (float)centerY + (float)offset * ITEM_HEIGHT
                      - (displayOffset - (float)currentMode) * ITEM_HEIGHT;
      int y = (int)yFloat;

      if (y > -ITEM_HEIGHT && y < SCREEN_HEIGHT) {
        String name = modeNames[modeIdx];

        if (offset == 0) {
          // Center item: larger text
          display.setTextSize(2);
          if (name.length() > 10) name = name.substring(0, 10);
        } else {
          // Adjacent items: smaller text
          display.setTextSize(1);
          if (name.length() > 21) name = name.substring(0, 21);
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
    String name = modeNames[currentMode];
    if (name.length() > 10) name = name.substring(0, 10);

    int16_t x1, y1;
    uint16_t w, h;
    display.getTextBounds(name, 0, 0, &x1, &y1, &w, &h);
    display.setCursor((SCREEN_WIDTH - w) / 2, (SCREEN_HEIGHT - h) / 2);
    display.print(name);
  }

  display.display();
}
