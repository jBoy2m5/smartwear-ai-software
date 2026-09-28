export interface HandLandmark {
  point: number;
  x: number;
  y: number;
  z: number;
}

export interface TelemetryData {
  timestamp: number;
  session_id: string;
  worker: {
    id: string;
    name: string;
    level: string;
  };
  step_analysis: {
    current_step_id: number;
    step_name: string;
    elapsed_time_sec: number;
    baseline_target_sec: number;
    muda_detected: boolean;
    muda_type: string;
  };
  sensor_telemetry: {
    force_total_N: number;
    force_fingers_N: {
      thumb: number;
      index: number;
      middle: number;
      palm: number;
    };
    wrist_velocity_mps: number;
    head_stability_score: number;
    battery_cap: number;
    battery_wrist: number;
    ping_ms: number;
  };
  hand_landmarks_3d: HandLandmark[];
}

export type Subscriber = (data: TelemetryData) => void;

class MockDataEngine {
  private subscribers: Subscriber[] = [];
  private intervalId: number | null = null;
  private startTime: number = Date.now();

  private generateMockLandmarks(): HandLandmark[] {
    const landmarks: HandLandmark[] = [];
    const t = Date.now() / 1000;
    
    // Simulate some movement
    const base_x = 0.5 + Math.sin(t) * 0.1;
    const base_y = 0.5 + Math.cos(t) * 0.1;
    
    for (let i = 0; i < 21; i++) {
      landmarks.push({
        point: i,
        x: base_x + (Math.random() - 0.5) * 0.2,
        y: base_y + (Math.random() - 0.5) * 0.2,
        z: Math.random() * 0.3
      });
    }
    return landmarks;
  }

  public subscribe(callback: Subscriber) {
    this.subscribers.push(callback);
    return () => {
      this.subscribers = this.subscribers.filter(sub => sub !== callback);
    };
  }

  public start() {
    if (this.intervalId) return;
    
    this.startTime = Date.now();
    // 60 FPS update ~ 16ms
    this.intervalId = window.setInterval(() => {
      const t = Date.now();
      const elapsed = (t - this.startTime) / 1000;
      
      const baseline = 15.0; // 15 seconds target
      const cycleElapsed = elapsed % 20; // 20s cycle
      const isMuda = cycleElapsed > baseline;
      
      const thumb = Math.max(0, 3 + Math.sin(t / 200) * 3 + (Math.random() - 0.5));
      const index = Math.max(0, 3 + Math.sin(t / 250) * 3 + (Math.random() - 0.5));
      const middle = Math.max(0, 2 + Math.sin(t / 300) * 2 + (Math.random() - 0.5));
      const palm = Math.max(0, 2 + Math.cos(t / 400) * 2 + (Math.random() - 0.5));
      const forceTotal = thumb + index + middle + palm;
      
      const wristVel = Math.abs(Math.cos(t / 500) * 1.5 + (Math.random() - 0.5) * 0.2);

      const data: TelemetryData = {
        timestamp: t,
        session_id: "SESS_DENSO_2026_01",
        worker: { id: "W_042", name: "Nguyễn Văn A", level: "Senior (Expert)" },
        step_analysis: {
          current_step_id: 2,
          step_name: "Lắp ráp & Siết ốc cụm van tiết lưu (10mm)",
          elapsed_time_sec: Number(cycleElapsed.toFixed(1)),
          baseline_target_sec: baseline,
          muda_detected: isMuda,
          muda_type: isMuda ? "Thao tác tay chệch hướng / Tốn thời gian tìm vị trí ốc" : ""
        },
        sensor_telemetry: {
          force_total_N: Number(forceTotal.toFixed(2)),
          force_fingers_N: {
            thumb: Number(thumb.toFixed(2)),
            index: Number(index.toFixed(2)),
            middle: Number(middle.toFixed(2)),
            palm: Number(palm.toFixed(2))
          },
          wrist_velocity_mps: Number(wristVel.toFixed(2)),
          head_stability_score: 95.0 - (Math.random() * 5),
          battery_cap: 85,
          battery_wrist: 78,
          ping_ms: 10 + Math.floor(Math.random() * 5)
        },
        hand_landmarks_3d: this.generateMockLandmarks()
      };

      this.subscribers.forEach(sub => sub(data));
    }, 16);
  }

  public stop() {
    if (this.intervalId) {
      window.clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }
}

export const mockEngine = new MockDataEngine();
