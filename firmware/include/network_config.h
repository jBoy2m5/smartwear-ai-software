#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <esp_timer.h>
#include <esp_sntp.h>
#include <sys/time.h>
#include "secrets.h"

constexpr char GATEWAY_HOST[] = "192.168.137.1";
constexpr const char *NTP_HOST = GATEWAY_HOST;
constexpr const char *MQTT_HOST = GATEWAY_HOST;
constexpr char WRIST_TOPIC[] = "wearable/user01/wrist/data";
// Windows Mobile Hotspot host also runs the MQTT and NTP services.
const IPAddress ROUTER(192, 168, 137, 1);
const IPAddress NETMASK(255, 255, 255, 0);
static portMUX_TYPE clockMux = portMUX_INITIALIZER_UNLOCKED;
static bool clockReady = false;
static int64_t epochOffsetUs = 0;

static void timeSynced(struct timeval *) {
    timeval now;
    gettimeofday(&now, nullptr);
    const int64_t epoch = int64_t(now.tv_sec) * 1000000 + now.tv_usec;
    const int64_t monotonic = esp_timer_get_time();
    portENTER_CRITICAL(&clockMux);
    // Freeze first NTP anchor to avoid wall-clock steps mid-session.
    if (!clockReady && now.tv_sec >= 1577836800) {
        epochOffsetUs = epoch - monotonic;
        clockReady = true;
    }
    portEXIT_CRITICAL(&clockMux);
}

static bool sourceEpochMs(int64_t monotonicUs, int64_t &epochMs) {
    portENTER_CRITICAL(&clockMux);
    bool ready = clockReady;
    int64_t offset = epochOffsetUs;
    portEXIT_CRITICAL(&clockMux);
    epochMs = (monotonicUs + offset) / 1000;
    return ready;
}

static void startNetwork(const IPAddress &address, const char *hostname) {
    Serial.println("Network: initializing WiFi station"); Serial.flush();
    WiFi.mode(WIFI_STA);
    Serial.println("Network: configuring station"); Serial.flush();
    WiFi.setHostname(hostname);
    WiFi.setSleep(false);
    WiFi.setAutoReconnect(true);
    if (!WiFi.config(address, ROUTER, NETMASK, ROUTER)) {
        Serial.println("Static IP configuration failed");
    }
    Serial.println("Network: connecting to configured hotspot"); Serial.flush();
    WiFi.begin(SMARTWEAR_WIFI_SSID, SMARTWEAR_WIFI_PASSWORD);
    Serial.println("Network: starting NTP"); Serial.flush();
    sntp_set_time_sync_notification_cb(timeSynced);
    configTime(0, 0, NTP_HOST);
    Serial.println("Network: initialization returned"); Serial.flush();
}
