// Temporary boot/radio isolation; deliberately does not initialize the camera.
#include "network_config.h"

void setup() {
    Serial.begin(115200);
    // Keep OV2640 powered down while isolating WiFi startup.
    pinMode(32, OUTPUT);
    digitalWrite(32, HIGH);
    Serial.printf("SmartCap WIFI DIAGNOSTIC: camera powered down, heap=%u\n",
                  unsigned(ESP.getFreeHeap()));
    Serial.flush();
    startNetwork(IPAddress(192,168,137,111), "smartwear-cap-diag");
}

void loop() {
    int64_t epoch;
    Serial.printf("DIAG uptime=%lu WiFi=%d IP=%s NTP=%s heap=%u\n",
                  (unsigned long)millis(), int(WiFi.status()),
                  WiFi.localIP().toString().c_str(),
                  sourceEpochMs(esp_timer_get_time(), epoch) ? "ready" : "waiting",
                  unsigned(ESP.getFreeHeap()));
    delay(2000);
}
