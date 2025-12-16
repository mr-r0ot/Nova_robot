/*
  esp32_nova_ap.ino
  - AP mode: SSID "Nova_Robot", password "12345678"
  - TCP server on port 5000 (ESP32 AP IP: 192.168.4.1)
  - On new TCP client connect: run initial sequence (both forward 1s, both backward 1s)
  - Accept JSON lines like {"left":2,"right":-3} (positive = forward seconds, negative = backward seconds)
  - Executes left/right concurrently
*/

#include <WiFi.h>

const char* AP_SSID = "Nova_Robot";
const char* AP_PASS = "12345678";

WiFiServer server(5000);

// Relay pins (طبق توضیحات شما)
const int PIN_IN1 = 21; // relay1 - left
const int PIN_IN2 = 19; // relay2 - left
const int PIN_IN3 = 18; // relay3 - right
const int PIN_IN4 = 5;  // relay4 - right

// اگر رله‌ی شما با LOW فعال می‌شود از LOW استفاده کنید، در غیر اینصورت HIGH
const int RELAY_ACTIVE_LEVEL = LOW;
const int RELAY_INACTIVE_LEVEL = (RELAY_ACTIVE_LEVEL == LOW) ? HIGH : LOW;

const int MAX_SECONDS = 120;

String rxBuffer = "";
bool clientPreviouslyConnected = false;
bool initialDoneForClient = false;

void setRelay(int pin, int level){
  digitalWrite(pin, level);
}

void stopLeft(){
  setRelay(PIN_IN1, RELAY_INACTIVE_LEVEL);
  setRelay(PIN_IN2, RELAY_INACTIVE_LEVEL);
}
void stopRight(){
  setRelay(PIN_IN3, RELAY_INACTIVE_LEVEL);
  setRelay(PIN_IN4, RELAY_INACTIVE_LEVEL);
}
void stopAll(){
  stopLeft();
  stopRight();
}

void leftForward(){
  setRelay(PIN_IN1, RELAY_INACTIVE_LEVEL);
  setRelay(PIN_IN2, RELAY_ACTIVE_LEVEL);
}
void leftBackward(){
  setRelay(PIN_IN1, RELAY_ACTIVE_LEVEL);
  setRelay(PIN_IN2, RELAY_INACTIVE_LEVEL);
}
void rightForward(){
  setRelay(PIN_IN3, RELAY_INACTIVE_LEVEL);
  setRelay(PIN_IN4, RELAY_ACTIVE_LEVEL);
}
void rightBackward(){
  setRelay(PIN_IN3, RELAY_ACTIVE_LEVEL);
  setRelay(PIN_IN4, RELAY_INACTIVE_LEVEL);
}

bool isDigitChar(char c){ return (c >= '0' && c <= '9'); }

// استخراج مقدار عددی (ممکن است منفی) برای کلید key از رشته JSON ساده
bool extractIntValue(const String &s, const String &key, int &outValue){
  int i = s.indexOf("\"" + key + "\"");
  if(i == -1) return false;
  int colon = s.indexOf(':', i);
  if(colon == -1) return false;
  int start = colon + 1;
  while(start < (int)s.length() && isSpace(s[start])) start++;
  int end = start;
  if(end < (int)s.length() && (s[end] == '-' || s[end] == '+')) end++;
  while(end < (int)s.length() && isDigitChar(s[end])) end++;
  if(end == start) return false;
  String numStr = s.substring(start, end);
  outValue = numStr.toInt();
  return true;
}

// اجرای همزمان حرکات left و right
void executeConcurrentMovements(int leftSec, int rightSec){
  if(leftSec > MAX_SECONDS) leftSec = MAX_SECONDS;
  if(leftSec < -MAX_SECONDS) leftSec = -MAX_SECONDS;
  if(rightSec > MAX_SECONDS) rightSec = MAX_SECONDS;
  if(rightSec < -MAX_SECONDS) rightSec = -MAX_SECONDS;

  unsigned long now = millis();
  unsigned long leftEnd = now;
  unsigned long rightEnd = now;

  if(leftSec > 0){ leftForward(); leftEnd = now + (unsigned long)leftSec * 1000UL; Serial.printf("Left forward %d s\n", leftSec); }
  else if(leftSec < 0){ leftBackward(); leftEnd = now + (unsigned long)(-leftSec) * 1000UL; Serial.printf("Left backward %d s\n", -leftSec); }
  else { stopLeft(); leftEnd = now; Serial.println("Left stop (0)"); }

  if(rightSec > 0){ rightForward(); rightEnd = now + (unsigned long)rightSec * 1000UL; Serial.printf("Right forward %d s\n", rightSec); }
  else if(rightSec < 0){ rightBackward(); rightEnd = now + (unsigned long)(-rightSec) * 1000UL; Serial.printf("Right backward %d s\n", -rightSec); }
  else { stopRight(); rightEnd = now; Serial.println("Right stop (0)"); }

  unsigned long finalEnd = (leftEnd > rightEnd) ? leftEnd : rightEnd;
  while(millis() < finalEnd){
    unsigned long t = millis();
    if(t >= leftEnd){
      stopLeft();
      leftEnd = finalEnd;
    }
    if(t >= rightEnd){
      stopRight();
      rightEnd = finalEnd;
    }
    delay(10);
  }
  stopAll();
  Serial.println("Concurrent movement finished.");
}

void processCommandString(const String &s){
  int left = 0, right = 0;
  bool hasLeft = extractIntValue(s, "left", left);
  bool hasRight = extractIntValue(s, "right", right);
  Serial.printf("Received: %s\n", s.c_str());
  if(!hasLeft && !hasRight){
    Serial.println("No left/right found.");
    return;
  }
  if(!hasLeft) left = 0;
  if(!hasRight) right = 0;
  executeConcurrentMovements(left, right);
}

void tryProcessRxBuffer(){
  // JSON بین { } را استخراج کن
  int sIdx = rxBuffer.indexOf('{');
  int eIdx = rxBuffer.indexOf('}', sIdx);
  if(sIdx != -1 && eIdx != -1){
    String msg = rxBuffer.substring(sIdx, eIdx+1);
    processCommandString(msg);
    rxBuffer = rxBuffer.substring(eIdx+1);
    return;
  }
  // یا خطی تا newline
  int nl = rxBuffer.indexOf('\n');
  if(nl != -1){
    String line = rxBuffer.substring(0, nl);
    line.trim();
    if(line.length() > 0){
      if(line.charAt(0) == '{'){
        int e = line.indexOf('}');
        if(e != -1){
          String msg = line.substring(0, e+1);
          processCommandString(msg);
        }
      } else {
        // سعی در پارس "left 2 right -3"
        int l=0, r=0; bool got=false;
        int li = line.indexOf("left");
        if(li != -1){
          int p = li+4;
          while(p < (int)line.length() && !isDigit(line[p]) && line[p] != '-') p++;
          if(p < (int)line.length()){
            int q=p+1; while(q < (int)line.length() && (isDigit(line[q]) || line[q]=='-')) q++;
            String num = line.substring(p,q); l = num.toInt(); got=true;
          }
        }
        int ri = line.indexOf("right");
        if(ri != -1){
          int p = ri+5;
          while(p < (int)line.length() && !isDigit(line[p]) && line[p] != '-') p++;
          if(p < (int)line.length()){
            int q=p+1; while(q < (int)line.length() && (isDigit(line[q]) || line[q]=='-')) q++;
            String num = line.substring(p,q); r = num.toInt(); got=true;
          }
        }
        if(got) executeConcurrentMovements(l, r);
      }
    }
    rxBuffer = rxBuffer.substring(nl+1);
  }
}

void setup(){
  pinMode(PIN_IN1, OUTPUT);
  pinMode(PIN_IN2, OUTPUT);
  pinMode(PIN_IN3, OUTPUT);
  pinMode(PIN_IN4, OUTPUT);
  stopAll();

  Serial.begin(115200);
  delay(100);
  Serial.println("\n=== ESP32 Nova AP Robot starting ===");

  WiFi.softAP(AP_SSID, AP_PASS);
  IPAddress ip = WiFi.softAPIP();
  Serial.print("AP started. IP: ");
  Serial.println(ip);
  server.begin();
  Serial.println("TCP server started on port 5000");
}

void loop(){
  WiFiClient client = server.available();
  bool clientConnected = client && client.connected();

  // اگر مشتری متصل شد و قبلاً متصل نبود -> اجرای توالی اولیه
  if(clientConnected && !clientPreviouslyConnected){
    Serial.println("Client connected. Running initial sequence (both forward 1s, both backward 1s).");
    leftForward(); rightForward();
    delay(1000);
    leftBackward(); rightBackward();
    delay(1000);
    stopAll();
    initialDoneForClient = true;
  }

  // اگر قطع شد -> ریست flag
  if(!clientConnected && clientPreviouslyConnected){
    Serial.println("Client disconnected.");
    initialDoneForClient = false;
  }
  clientPreviouslyConnected = clientConnected;

  if(clientConnected){
    // خواندن از socket
    while(client.available()){
      char c = (char)client.read();
      rxBuffer += c;
      // کوچک تاخیر
      delay(1);
    }
    // پردازش بافر
    tryProcessRxBuffer();

    // اگر لازم باشه می‌تونیم پاسخ هم به کلاینت بفرستیم؛ در حال حاضر صرفاً لاگ می‌کنیم
  }

  delay(10);
}
