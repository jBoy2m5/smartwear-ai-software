# Camera stream recovery — 10/10/2026

## Latest state: recovered after user changed USB ports

The user moved both devices to different USB ports. Windows now enumerates SmartCap CH340 as COM5 and SmartWrist CP210x as COM7; PlatformIO upload/monitor settings match. No additional flash/reset was needed.

- AI check `hardware_20261010_161915_126217_hw46owbl`: complete, 60.031 recording seconds, 496 JPEG and 496 inferred frames (8.262 FPS), 3,004 wrist samples (50.041 Hz); no camera stream error, dropped-for-inference or wrist sequence gap recorded.
- Subsequent stream reopen `hardware_raw_20261010_162027_692021_hbb3cmx3`: raw_complete, 10.141 seconds, 75 JPEG and 525 wrist samples; no stream error or sequence gap recorded. Same camera boot ID `e70cb1be3f1ddcef` in both runs; no observed reset between them.
- Final device API: camera ready, MQTT/NTP ok, capture_active=false, can_start=true. Backend ready. CLI checks have released the camera for dashboard capture.
- The old failed job can remain visible in the user's browser; it is historical. Click device refresh, enter the participant alias/required metadata, and start a new recording.

These two checks confirm recovery for the tested interval, not long-term stability or the exact physical cause. Existing first-buffer/transport timestamp age is retained in raw metadata. Historical failures and raw files below remain unchanged.

The reported `Camera reader failed: IncompleteRead(0 bytes read)` has a confirmed software cause: `CameraReceiver` did not catch `http.client.HTTPException`. A truncated chunked HTTP response bypassed its retry handler and terminated acquisition. The failed session `hardware_20261010_160644_341380_jst9z8gq` contains that error after three camera frames; its raw data remains intact.

## Changes and validation

- `ai/hardware/camera_receiver.py`: handle HTTP framing/disconnect exceptions in the existing retry loop. Partial multipart/JPEG input is discarded; only complete validated JPEGs are appended to raw files. Boot ID, sequence and clock reset checks still stop a session across device restarts.
- `ai/hardware/record_hardware.py`: fail with an explicit message after 15 seconds without a new JPEG even after the first frame. Previously a camera that stopped midway could reach the requested duration and be marked complete. Retain observations/video and failed marker for audit.
- `firmware/src/smartcap.cpp`: restore the camera changes present in the local Denso2 source: send header/JPEG/separator in a single HTTP chunk and use one internal-RAM camera buffer at QVGA, quality 20, XCLK 16 MHz. Version reported by the board: `cap-single-send-v5`. The preceding Denso3 upload had used the older three-PSRAM-buffer/three-write configuration.
- Firmware build/upload to COM4 succeeded; flash hash verified. No SmartWrist firmware changes in this fix.
- Targeted checks: **33 passed, 14 subtests passed** (`ai/hardware/test_hardware.py`, `ai/hardware/test_deployment.py`, `backend/tests/test_capture_manager.py`). `git diff --check` passed.
- The recovery regression uses actual Python `HTTPResponse` chunk decoding, truncates boundary/header/JPEG, and checks reconnect, raw hashes and rejection of a changed boot ID. The capture regression verifies a stalled camera after one processed frame is failed while retaining that observation.
- Dashboard launches a new AI subprocess for each capture, which reads the updated receiver/recorder modules. Backend `/ready` remains ready; backend restart is unnecessary for these changes.

## Historical hardware issue before changing USB ports

The live 60-second check `hardware_20261010_161201_483124_g81syge7` did not establish uninterrupted streaming: 181 JPEG/inferred frames, 3,093 wrist samples, five camera stream errors, then camera HTTP ports became unreachable after approximately 26 seconds. This check ran before the additional post-first-frame 15-second timeout was added; its original complete marker is preserved and does not prove a complete healthy capture.

Boot logs also show `LoadProhibited`, `TG1WDT_SYS_RESET` and `IllegalInstruction` during Wi-Fi startup. Decoding the first backtrace points to `ram_phy_get_vdd33`, `txpwr_offset`, `bb_init`, `register_chipv7_phy`, `esp_phy_load_cal_and_init`, `wifi_hw_start`, and `ppTask`. This is evidence of a radio/boot failure, not a diagnosis of which physical component is responsible. No new brownout event was observed in this check.

After a reset, a boot reached camera/Wi-Fi/NTP ready; the following raw test `hardware_raw_20261010_161417_780099_koky174b` received zero JPEG and 1,502 wrist samples in 30 seconds. Software retry alone cannot restore a board whose HTTP services remain unreachable.

At that point, asked the user to identify the SmartCap power connection and try another USB cable/direct USB port. The user subsequently changed both USB ports; the new verification results are recorded at the top of this document.

Logs are local in `backend/data/camera-fix-20261010-*.log`; raw sessions remain unchanged. Do not open serial or reset/flash during recording.
