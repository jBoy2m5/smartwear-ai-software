#include "network_config.h"
#include <Wire.h>
#include <PubSubClient.h>

static uint8_t mpuAddress = 0;
constexpr uint8_t FORCE_PINS[] = {32, 33, 34, 35};
struct Sample { int64_t epoch; uint32_t seq; int16_t acc[3], gyro[3]; uint16_t force[4]; bool imuValid; uint8_t imuAddress; uint32_t imuAgeMs; };
struct ImuReading { int64_t capturedUs; int16_t acc[3], gyro[3]; uint8_t address; };
static QueueHandle_t imuReadings;
static QueueHandle_t samples;
static WiFiClient transport;
static PubSubClient mqtt(transport);

static bool writeRegister(uint8_t reg, uint8_t value) {
    Wire.beginTransmission(mpuAddress); Wire.write(reg); Wire.write(value);
    return Wire.endTransmission() == 0;
}

static bool discoverMpu() {
    // AD0 selects 0x68 or 0x69. An ACK alone is not proof of the sensor type.
    for (uint8_t address : {uint8_t(0x68), uint8_t(0x69)}) {
        Wire.beginTransmission(address);
        if (Wire.endTransmission(true) != 0) continue;
        Wire.beginTransmission(address); Wire.write(0x75); // WHO_AM_I
        if (Wire.endTransmission(false) != 0 || Wire.requestFrom(address, uint8_t(1)) != 1) continue;
        uint8_t identity = Wire.read();
        if (identity != 0x68) {
            Serial.printf("Unsupported IMU at 0x%02x: WHO_AM_I=0x%02x\n", address, identity);
            continue;
        }
        mpuAddress = address;
        bool ok = writeRegister(0x6B, 0x01);
        delay(100);
        ok = writeRegister(0x1A, 0x03) && ok;
        ok = writeRegister(0x19, 19) && ok;
        ok = writeRegister(0x1B, 0) && ok;
        ok = writeRegister(0x1C, 0) && ok;
        if (ok) {
            Serial.printf("MPU6050 ready at 0x%02x (SDA21/SCL22, 100kHz)\n", address);
            return true;
        }
    }
    mpuAddress = 0;
    Serial.println("MPU6050 unavailable at 0x68/0x69; FSR continues, IMU=null; retry in 2s. Check SDA21/SCL22/3V3/GND.");
    return false;
}

static void imuTask(void *) {
    uint32_t lastProbe = 0;
    while (true) {
        if (!mpuAddress && (lastProbe == 0 || millis() - lastProbe >= 2000)) {
            discoverMpu();
            lastProbe = millis();
        }
        if (mpuAddress) {
            ImuReading reading = {};
            reading.capturedUs = esp_timer_get_time();
            Wire.beginTransmission(mpuAddress); Wire.write(0x3B);
            if (Wire.endTransmission(false) == 0 && Wire.requestFrom(mpuAddress, uint8_t(14)) == 14) {
                int16_t values[7];
                for (auto &value : values) {
                    uint8_t high = Wire.read(), low = Wire.read();
                    value = int16_t((uint16_t(high) << 8) | low);
                }
                for (int i=0; i<3; ++i) { reading.acc[i]=values[i]; reading.gyro[i]=values[i+4]; }
                reading.address = mpuAddress;
            } else {
                Serial.println("MPU6050 read failed; retrying discovery; IMU=null");
                mpuAddress = 0;
            }
            xQueueOverwrite(imuReadings, &reading);
        }
        vTaskDelay(pdMS_TO_TICKS(20));
    }
}

static void sampleTask(void *) {
    TickType_t next = xTaskGetTickCount();
    uint32_t sequence = 0;
    while (true) {
        vTaskDelayUntil(&next, pdMS_TO_TICKS(20));
        Sample sample = {};
        sample.seq = sequence++;
        const int64_t nowUs = esp_timer_get_time();
        if (!sourceEpochMs(nowUs, sample.epoch)) continue;
        ImuReading reading;
        // A stalled/missing I2C device must never block the ADC sampling task.
        if (xQueuePeek(imuReadings, &reading, 0) == pdTRUE && reading.address
                && nowUs >= reading.capturedUs && nowUs - reading.capturedUs <= 40000) {
            sample.imuValid = true;
            sample.imuAddress = reading.address;
            sample.imuAgeMs = (nowUs - reading.capturedUs) / 1000;
            for (int i=0; i<3; ++i) { sample.acc[i]=reading.acc[i]; sample.gyro[i]=reading.gyro[i]; }
        }
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
    Wire.begin(21, 22); Wire.setClock(100000); Wire.setTimeOut(10);
    analogReadResolution(12);
    for (auto pin : FORCE_PINS) { pinMode(pin, INPUT); analogSetPinAttenuation(pin, ADC_11db); }
    samples = xQueueCreate(100, sizeof(Sample));
    imuReadings = xQueueCreate(1, sizeof(ImuReading));
    if (!samples || !imuReadings) { Serial.println("Queue allocation failed"); while(true) delay(1000); }
    startNetwork(IPAddress(192,168,137,100), "smartwear-wrist");
    mqtt.setServer(MQTT_HOST, 1883); mqtt.setBufferSize(512); mqtt.setSocketTimeout(1);
    xTaskCreatePinnedToCore(sampleTask, "sample50Hz", 4096, nullptr, 2, nullptr, 1);
    xTaskCreatePinnedToCore(imuTask, "imu", 4096, nullptr, 1, nullptr, 1);
    Serial.println("SmartWrist 192.168.137.100: acc=g, gyro=deg/s, FSR=ADC counts");
}

void loop() {
    static uint32_t lastAttempt = 0;
    static uint32_t lastReport = 0;
    static uint32_t published = 0;
    if (millis() - lastReport >= 5000) {
        int64_t epoch;
        Serial.printf("WiFi=%d IP=%s NTP=%s MQTT=%s published=%lu\n",
                      int(WiFi.status()), WiFi.localIP().toString().c_str(),
                      sourceEpochMs(esp_timer_get_time(), epoch) ? "ready" : "waiting",
                      mqtt.connected() ? "connected" : "waiting", (unsigned long)published);
        lastReport = millis();
    }
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
        if (sample.imuValid) snprintf(payload, sizeof(payload),
            "{\"t_ms\":%lld,\"seq\":%lu,\"acc\":[%.5f,%.5f,%.5f],"
            "\"gyro\":[%.4f,%.4f,%.4f],\"force\":[%u,%u,%u,%u],\"imu_status\":\"ok\",\"imu_address\":%u,\"imu_age_ms\":%lu}",
            (long long)sample.epoch, (unsigned long)sample.seq,
            sample.acc[0]/16384.0, sample.acc[1]/16384.0, sample.acc[2]/16384.0,
            sample.gyro[0]/131.0, sample.gyro[1]/131.0, sample.gyro[2]/131.0,
            sample.force[0], sample.force[1], sample.force[2], sample.force[3], sample.imuAddress, (unsigned long)sample.imuAgeMs);
        else snprintf(payload, sizeof(payload),
            "{\"t_ms\":%lld,\"seq\":%lu,\"acc\":null,\"gyro\":null,"
            "\"force\":[%u,%u,%u,%u],\"imu_status\":\"unavailable\",\"imu_address\":null,\"imu_age_ms\":null}",
            (long long)sample.epoch, (unsigned long)sample.seq,
            sample.force[0], sample.force[1], sample.force[2], sample.force[3]);
        if (mqtt.publish(WRIST_TOPIC, payload, false)) ++published;
        else Serial.println("MQTT publish dropped");
    }
    delay(1);
}
