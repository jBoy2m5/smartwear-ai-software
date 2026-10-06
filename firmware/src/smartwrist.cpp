#include "network_config.h"
#include <Wire.h>
#include <PubSubClient.h>

constexpr uint8_t MPU = 0x68;
constexpr uint8_t FORCE_PINS[] = {32, 33, 34, 35};
struct Sample { int64_t epoch; uint32_t seq; int16_t acc[3], gyro[3]; uint16_t force[4]; };
static QueueHandle_t samples;
static WiFiClient transport;
static PubSubClient mqtt(transport);

static bool writeRegister(uint8_t reg, uint8_t value) {
    Wire.beginTransmission(MPU); Wire.write(reg); Wire.write(value);
    return Wire.endTransmission() == 0;
}

static void sampleTask(void *) {
    TickType_t next = xTaskGetTickCount();
    uint32_t sequence = 0;
    while (true) {
        vTaskDelayUntil(&next, pdMS_TO_TICKS(20));
        Sample sample = {};
        sample.seq = sequence++;
        if (!sourceEpochMs(esp_timer_get_time(), sample.epoch)) continue;
        Wire.beginTransmission(MPU); Wire.write(0x3B);
        if (Wire.endTransmission(false) != 0 || Wire.requestFrom(MPU, uint8_t(14)) != 14) continue;
        int16_t values[7];
        for (auto &value : values) {
            uint8_t high = Wire.read(), low = Wire.read();
            value = int16_t((uint16_t(high) << 8) | low);
        }
        for (int i=0; i<3; ++i) { sample.acc[i]=values[i]; sample.gyro[i]=values[i+4]; }
        for (int i=0; i<4; ++i) sample.force[i] = analogRead(FORCE_PINS[i]);
        if (xQueueSend(samples, &sample, 0) != pdTRUE) {
            Sample discarded;
            xQueueReceive(samples, &discarded, 0);
            xQueueSend(samples, &sample, 0); // Bounded memory, gaps visible in seq.
        }
    }
}

void setup() {
    Serial.begin(115200);
    Wire.begin(21, 22); Wire.setClock(400000); Wire.setTimeOut(10);
    // Wake, +/-2g, +/-250 deg/s, 44-Hz DLPF, 1kHz/(19+1) = 50Hz.
    bool ok = writeRegister(0x6B, 0x01);
    delay(100);
    ok = writeRegister(0x1A, 0x03) && ok;
    ok = writeRegister(0x19, 19) && ok;
    ok = writeRegister(0x1B, 0) && ok;
    ok = writeRegister(0x1C, 0) && ok;
    if (!ok) { Serial.println("MPU6050 missing at 0x68"); while(true) delay(1000); }
    analogReadResolution(12);
    for (auto pin : FORCE_PINS) { pinMode(pin, INPUT); analogSetPinAttenuation(pin, ADC_11db); }
    samples = xQueueCreate(100, sizeof(Sample));
    if (!samples) { Serial.println("Queue allocation failed"); while(true) delay(1000); }
    startNetwork(IPAddress(192,168,137,100), "smartwear-wrist");
    mqtt.setServer(MQTT_HOST, 1883); mqtt.setBufferSize(512); mqtt.setSocketTimeout(1);
    xTaskCreatePinnedToCore(sampleTask, "sample50Hz", 4096, nullptr, 2, nullptr, 1);
    Serial.println("SmartWrist 192.168.137.100: acc=g, gyro=deg/s, FSR=ADC counts");
}

void loop() {
    static uint32_t lastAttempt = 0;
    if (WiFi.status() != WL_CONNECTED) { delay(10); return; }
    if (!mqtt.connected()) {
        if (millis() - lastAttempt >= 2000) {
            lastAttempt = millis();
            mqtt.connect("smartwear_user01_wrist");
        }
        delay(1); return;
    }
    mqtt.loop();
    Sample sample;
    if (xQueueReceive(samples, &sample, 0) == pdTRUE) {
        int64_t now;
        sourceEpochMs(esp_timer_get_time(), now);
        if (now - sample.epoch > 200) return; // Drop stale backlog after reconnect.
        char payload[384];
        snprintf(payload, sizeof(payload),
            "{\"t_ms\":%lld,\"seq\":%lu,\"acc\":[%.5f,%.5f,%.5f],"
            "\"gyro\":[%.4f,%.4f,%.4f],\"force\":[%u,%u,%u,%u]}",
            (long long)sample.epoch, (unsigned long)sample.seq,
            sample.acc[0]/16384.0, sample.acc[1]/16384.0, sample.acc[2]/16384.0,
            sample.gyro[0]/131.0, sample.gyro[1]/131.0, sample.gyro[2]/131.0,
            sample.force[0], sample.force[1], sample.force[2], sample.force[3]);
        if (!mqtt.publish(WRIST_TOPIC, payload, false)) Serial.println("MQTT publish dropped");
    }
    delay(1);
}
