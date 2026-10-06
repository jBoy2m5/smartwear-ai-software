#include "network_config.h"
#include <esp_camera.h>
#include <esp_http_server.h>

static uint32_t sequence = 0;

static esp_err_t streamCamera(httpd_req_t *request) {
    int64_t epoch;
    if (!sourceEpochMs(esp_timer_get_time(), epoch)) {
        httpd_resp_set_status(request, "503 Service Unavailable");
        return httpd_resp_send(request, "NTP not synchronized", HTTPD_RESP_USE_STRLEN);
    }
    httpd_resp_set_type(request, "multipart/x-mixed-replace; boundary=smartwear");
    httpd_resp_set_hdr(request, "Cache-Control", "no-store");
    int64_t previous = -1;
    while (WiFi.status() == WL_CONNECTED) {
        camera_fb_t *fb = esp_camera_fb_get();
        if (!fb) return ESP_FAIL;
        // Driver timestamp is first DMA buffer time since boot, not send time.
        const int64_t captured = int64_t(fb->timestamp.tv_sec) * 1000000 + fb->timestamp.tv_usec;
        sourceEpochMs(captured, epoch);
        if (epoch <= previous) {
            esp_camera_fb_return(fb);
            continue;
        }
        previous = epoch;
        char header[224];
        int length = snprintf(header, sizeof(header),
            "--smartwear\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n"
            "X-Timestamp-Ms: %lld\r\nX-Frame-Seq: %lu\r\n\r\n",
            unsigned(fb->len), (long long)epoch, (unsigned long)sequence++);
        esp_err_t result = httpd_resp_send_chunk(request, header, length);
        if (result == ESP_OK)
            result = httpd_resp_send_chunk(request, (const char *)fb->buf, fb->len);
        esp_camera_fb_return(fb);
        if (result == ESP_OK) result = httpd_resp_send_chunk(request, "\r\n", 2);
        if (result != ESP_OK) return result;
        vTaskDelay(1);
    }
    return ESP_FAIL;
}

void setup() {
    Serial.begin(115200);
    if (!psramFound()) {
        Serial.println("PSRAM required for double-buffered QVGA capture");
        while (true) delay(1000);
    }
    camera_config_t config = {};
    config.pin_pwdn = 32; config.pin_reset = -1;
    config.pin_xclk = 0; config.pin_sccb_sda = 26; config.pin_sccb_scl = 27;
    config.pin_d7 = 35; config.pin_d6 = 34; config.pin_d5 = 39; config.pin_d4 = 36;
    config.pin_d3 = 21; config.pin_d2 = 19; config.pin_d1 = 18; config.pin_d0 = 5;
    config.pin_vsync = 25; config.pin_href = 23; config.pin_pclk = 22;
    config.xclk_freq_hz = 16000000;
    config.ledc_timer = LEDC_TIMER_0; config.ledc_channel = LEDC_CHANNEL_0;
    config.pixel_format = PIXFORMAT_JPEG; config.frame_size = FRAMESIZE_QVGA;
    config.jpeg_quality = 15; config.fb_count = 3;
    config.fb_location = CAMERA_FB_IN_PSRAM; config.grab_mode = CAMERA_GRAB_LATEST;
    if (esp_camera_init(&config) != ESP_OK) {
        Serial.println("Camera initialization failed");
        while (true) delay(1000);
    }
    startNetwork(IPAddress(192,168,137,111), "smartwear-cap");
    httpd_config_t serverConfig = HTTPD_DEFAULT_CONFIG();
    serverConfig.server_port = 81;
    serverConfig.max_open_sockets = 1; // One ingestion consumer; do not open in browser.
    serverConfig.lru_purge_enable = false;
    serverConfig.send_wait_timeout = 5;
    httpd_handle_t server = nullptr;
    if (httpd_start(&server, &serverConfig) != ESP_OK) {
        Serial.println("HTTP server failed");
        return;
    }
    httpd_uri_t route = {};
    route.uri = "/stream"; route.method = HTTP_GET; route.handler = streamCamera;
    httpd_register_uri_handler(server, &route);
    Serial.println("SmartCap: http://192.168.137.111:81/stream; waiting for WiFi/NTP");
}

void loop() { delay(1000); }
