#include "network_config.h"
#include <esp_camera.h>
#include <esp_http_server.h>
#include <esp_system.h>
#include <esp_heap_caps.h>
#include <memory>
#include <lwip/sockets.h>

static uint32_t sequence = 0;
static char bootId[17];
static bool cameraReady = false;
static esp_err_t cameraInitError = ESP_OK;

static const char *resetReason() {
  switch (esp_reset_reason()) {
  case ESP_RST_POWERON:
    return "power_on";
  case ESP_RST_BROWNOUT:
    return "brownout";
  case ESP_RST_PANIC:
    return "panic";
  case ESP_RST_INT_WDT:
    return "interrupt_watchdog";
  case ESP_RST_TASK_WDT:
    return "task_watchdog";
  case ESP_RST_WDT:
    return "watchdog";
  case ESP_RST_SW:
    return "software_reset";
  case ESP_RST_EXT:
    return "external_reset";
  default:
    return "other";
  }
}

static esp_err_t cameraStatus(httpd_req_t *request) {
  int64_t epoch;
  char body[512];
  snprintf(
      body, sizeof(body),
      "{\"schema\":\"smartwear.cap.status/1\",\"boot_id\":\"%s\","
      "\"reset_reason\":\"%s\",\"uptime_ms\":%lu,\"wifi_rssi\":%d,"
      "\"camera_ready\":%s,\"camera_init_error\":%d,\"ntp_ready\":%s,"
      "\"sequence\":%lu,\"heap_bytes\":%u,\"firmware\":\"cap-single-send-v5\"}",
      bootId, resetReason(), (unsigned long)millis(), WiFi.RSSI(),
      cameraReady ? "true" : "false", int(cameraInitError),
      sourceEpochMs(esp_timer_get_time(), epoch) ? "true" : "false",
      (unsigned long)sequence, unsigned(ESP.getFreeHeap()));
  httpd_resp_set_type(request, "application/json");
  httpd_resp_set_hdr(request, "Cache-Control", "no-store");
  return httpd_resp_send(request, body, HTTPD_RESP_USE_STRLEN);
}

static void startDiagnostics() {
  // A distinct server task remains responsive while port 81 streams
  // synchronously.
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = 82;
  config.ctrl_port = 32769;
  config.max_open_sockets = 2;
  config.lru_purge_enable = true;
  config.send_wait_timeout = config.recv_wait_timeout = 1;
  httpd_handle_t server = nullptr;
  if (httpd_start(&server, &config) == ESP_OK) {
    httpd_uri_t route = {};
    route.uri = "/status";
    route.method = HTTP_GET;
    route.handler = cameraStatus;
    httpd_register_uri_handler(server, &route);
  } else
    Serial.println("Diagnostic HTTP server failed");
}

static esp_err_t streamCamera(httpd_req_t *request) {
  // Multipart headers and the trailing CRLF must not wait for TCP coalescing.
  const int noDelay = 1;
  setsockopt(httpd_req_to_sockfd(request), IPPROTO_TCP, TCP_NODELAY, &noDelay,
             sizeof(noDelay));
  int64_t epoch;
  if (!sourceEpochMs(esp_timer_get_time(), epoch)) {
    httpd_resp_set_status(request, "503 Service Unavailable");
    return httpd_resp_send(request, "NTP not synchronized",
                           HTTPD_RESP_USE_STRLEN);
  }
  httpd_resp_set_type(request, "multipart/x-mixed-replace; boundary=smartwear");
  httpd_resp_set_hdr(request, "Cache-Control", "no-store");
  int64_t previous = -1;
  int64_t lastFreshFrameUs = esp_timer_get_time();
  while (WiFi.status() == WL_CONNECTED) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb)
      return ESP_FAIL;
    // Driver timestamp is first DMA buffer time since boot, not send time.
    const int64_t captured =
        int64_t(fb->timestamp.tv_sec) * 1000000 + fb->timestamp.tv_usec;
    sourceEpochMs(captured, epoch);
    if (epoch <= previous) {
      esp_camera_fb_return(fb);
      // A stale buffer must not turn this HTTP task into a busy loop.
      vTaskDelay(1);
      if (esp_timer_get_time() - lastFreshFrameUs > 2000000) {
        Serial.println(
            "Camera timestamps stalled; closing stream for reconnect");
        return ESP_ERR_TIMEOUT;
      }
      continue;
    }
    previous = epoch;
    lastFreshFrameUs = esp_timer_get_time();
    char header[320];
    int length = snprintf(
        header, sizeof(header),
        "--smartwear\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n"
        "X-Timestamp-Ms: %lld\r\nX-Frame-Seq: %lu\r\n"
        "X-Boot-Id: %s\r\nX-Reset-Reason: %s\r\n\r\n",
        unsigned(fb->len), (long long)epoch, (unsigned long)sequence++, bootId,
        resetReason());
    // Send each multipart frame in one HTTP chunk. Return the camera buffer
    // before waiting for TCP so transport cannot hold up camera acquisition.
    const size_t payloadLength = size_t(length) + fb->len + 2;
    std::unique_ptr<uint8_t, decltype(&free)> payload(
        static_cast<uint8_t *>(heap_caps_malloc(payloadLength,
                                               MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT)),
        &free);
    if (!payload) {
      esp_camera_fb_return(fb);
      return ESP_ERR_NO_MEM;
    }
    memcpy(payload.get(), header, length);
    memcpy(payload.get() + length, fb->buf, fb->len);
    memcpy(payload.get() + length + fb->len, "\r\n", 2);
    esp_camera_fb_return(fb);
    const esp_err_t result = httpd_resp_send_chunk(
        request, reinterpret_cast<const char *>(payload.get()), payloadLength);
    if (result != ESP_OK)
      return result;
    vTaskDelay(1);
  }
  return ESP_FAIL;
}

void setup() {
  Serial.begin(115200);
  snprintf(bootId, sizeof(bootId), "%08lx%08lx", (unsigned long)esp_random(),
           (unsigned long)esp_random());
  Serial.printf("SmartCap boot_id=%s reset_reason=%s\n", bootId, resetReason());
  // OV2640 PWDN is active high. Bring up the radio with the sensor off.
  pinMode(32, OUTPUT);
  digitalWrite(32, HIGH);
  Serial.printf("SmartCap camera-only boot: heap=%u PSRAM=%s\n",
                unsigned(ESP.getFreeHeap()),
                psramFound() ? "ready" : "missing");
  Serial.flush();
  // Start WiFi before enabling camera DMA/VSYNC traffic during network init.
  startNetwork(IPAddress(192, 168, 137, 111), "smartwear-cap");
  const uint32_t connectionStarted = millis();
  while (WiFi.status() != WL_CONNECTED &&
         millis() - connectionStarted < 15000) {
    delay(50);
  }
  Serial.printf("Radio startup complete: WiFi=%d; powering camera via driver\n",
                int(WiFi.status()));
  Serial.flush();
  startDiagnostics();
  camera_config_t config = {};
  config.pin_pwdn = 32;
  config.pin_reset = -1;
  config.pin_xclk = 0;
  config.pin_sccb_sda = 26;
  config.pin_sccb_scl = 27;
  config.pin_d7 = 35;
  config.pin_d6 = 34;
  config.pin_d5 = 39;
  config.pin_d4 = 36;
  config.pin_d3 = 21;
  config.pin_d2 = 19;
  config.pin_d1 = 18;
  config.pin_d0 = 5;
  config.pin_vsync = 25;
  config.pin_href = 23;
  config.pin_pclk = 22;
  config.xclk_freq_hz = 16000000;
  config.ledc_timer = LEDC_TIMER_0;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_QVGA;
  config.jpeg_quality = 20;
  // Use the single internal-RAM buffer configuration verified on this board.
  config.fb_count = 1;
  config.fb_location = CAMERA_FB_IN_DRAM;
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  Serial.println("Initializing OV2640 QVGA camera: one internal-RAM buffer, batched HTTP");
  Serial.flush();
  const esp_err_t cameraResult = esp_camera_init(&config);
  cameraInitError = cameraResult;
  if (cameraResult != ESP_OK) {
    Serial.printf("Camera initialization failed: 0x%x\n",
                  unsigned(cameraResult));
    while (true)
      delay(1000);
  }
  cameraReady = true;
  Serial.println("Camera initialized; starting HTTP stream server");
  Serial.flush();
  httpd_config_t serverConfig = HTTPD_DEFAULT_CONFIG();
  serverConfig.server_port = 81;
  // One synchronous stream handler; allow a reconnect while the old socket
  // closes.
  serverConfig.max_open_sockets = 2;
  serverConfig.lru_purge_enable = true;
  serverConfig.send_wait_timeout = 2;
  serverConfig.recv_wait_timeout = 2;
  httpd_handle_t server = nullptr;
  if (httpd_start(&server, &serverConfig) != ESP_OK) {
    Serial.println("HTTP server failed");
    return;
  }
  httpd_uri_t route = {};
  route.uri = "/stream";
  route.method = HTTP_GET;
  route.handler = streamCamera;
  httpd_register_uri_handler(server, &route);
  Serial.println(
      "SmartCap: http://192.168.137.111:81/stream; waiting for WiFi/NTP");
}

void loop() {
  static uint32_t lastReport = 0;
  if (millis() - lastReport >= 5000) {
    int64_t epoch;
    Serial.printf("SmartCap WiFi=%d IP=%s NTP=%s frames=%lu heap=%u\n",
                  int(WiFi.status()), WiFi.localIP().toString().c_str(),
                  sourceEpochMs(esp_timer_get_time(), epoch) ? "ready"
                                                             : "waiting",
                  (unsigned long)sequence, unsigned(ESP.getFreeHeap()));
    lastReport = millis();
  }
  delay(1000);
}
