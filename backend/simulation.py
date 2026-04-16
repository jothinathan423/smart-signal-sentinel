"""
Traffic Simulation Engine for Smart Signal Sentinel
=====================================================
Generates realistic virtual traffic at a 4-way intersection so the full
system (signal control, violation detection, emergency corridors, dashboard)
can be tested without physical cameras.

Each approach direction (N, S, E, W) has its own traffic light that cycles
through phases:
  Phase 1: North/South GREEN, East/West RED
  Phase 2: All YELLOW (transition)
  Phase 3: East/West GREEN, North/South RED
  Phase 4: All YELLOW (transition)

Vehicles carry generated Indian-style license plates and may commit
violations (red-light running, speeding, no helmet) so the downstream
violation-detection pipeline can be exercised end-to-end.
"""

import cv2
import numpy as np
import time
import threading
import random
import math
import string
from collections import deque
from datetime import datetime

# ============= VEHICLE COLORS (BGR) =============
VEHICLE_COLORS = {
    "car":        (180, 160, 60),
    "truck":      (50, 50, 180),
    "bus":        (30, 140, 220),
    "motorcycle": (200, 200, 0),
    "bicycle":    (0, 200, 0),
    "ambulance":  (60, 60, 255),
}

VEHICLE_SIZES = {
    "car":        (40, 22),
    "truck":      (65, 26),
    "bus":        (75, 26),
    "motorcycle": (28, 14),
    "bicycle":    (22, 10),
    "ambulance":  (50, 24),
}

PCE_VALUES = {
    "car": 1.0, "truck": 3.0, "bus": 3.0,
    "motorcycle": 0.5, "bicycle": 0.2, "ambulance": 1.5,
}

SPEED_LIMIT = 40  # km/h – same as main system

# Indian state codes for realistic plates
_STATE_CODES = [
    "TN", "KA", "MH", "DL", "AP", "TS", "KL", "GJ",
    "RJ", "UP", "WB", "MP", "HR", "PB", "CH", "GA",
]


def generate_license_plate():
    """Generate a realistic Indian-format license plate: XX 00 XX 0000."""
    state = random.choice(_STATE_CODES)
    dist = f"{random.randint(1, 99):02d}"
    series = random.choice(string.ascii_uppercase) + random.choice(string.ascii_uppercase)
    num = f"{random.randint(1, 9999):04d}"
    return f"{state} {dist} {series} {num}"


class SimVehicle:
    """A single simulated vehicle."""

    _next_id = 1

    def __init__(self, vehicle_type="car", lane=0, direction="north",
                 speed=40, x=0, y=0, is_violator=False, helmet_violation=False):
        self.id = f"sim-v{SimVehicle._next_id}"
        SimVehicle._next_id += 1
        self.type = vehicle_type
        self.lane = lane
        self.direction = direction
        self.speed_kmh = speed
        self.x = float(x)
        self.y = float(y)
        self.is_emergency = vehicle_type == "ambulance"
        self.stopped = False
        self.created_at = time.time()

        # License plate
        self.license_plate = generate_license_plate()

        # Violation flags
        self.is_violator = is_violator          # will ignore red lights
        self.helmet_violation = helmet_violation  # two-wheeler without helmet
        self.red_light_violation = False          # set when actually running red
        self.has_crossed_stop_line = False        # track if crossed

        w, h = VEHICLE_SIZES.get(vehicle_type, (40, 22))
        if direction in ("north", "south"):
            self.width, self.height = h, w
        else:
            self.width, self.height = w, h

    @property
    def is_speeding(self):
        return self.speed_kmh > SPEED_LIMIT

    def pixels_per_second(self):
        """Convert km/h to pixels/sec (1 metre ~ 8 pixels)."""
        return self.speed_kmh * 8.0 / 3.6

    def update(self, dt, my_signal, stop_lines):
        """Move vehicle, respecting its direction's red signal and stop line."""
        sl = stop_lines.get(self.direction, None)

        if self.stopped:
            if my_signal == "green" or self.is_emergency:
                self.stopped = False
            else:
                return

        pps = self.pixels_per_second()
        dx, dy = 0.0, 0.0
        if self.direction == "north":
            dy = -pps * dt
        elif self.direction == "south":
            dy = pps * dt
        elif self.direction == "east":
            dx = pps * dt
        elif self.direction == "west":
            dx = -pps * dt

        new_x = self.x + dx
        new_y = self.y + dy

        # Stop at red/yellow before the stop line (unless violator or emergency)
        if my_signal in ("red", "yellow") and not self.is_emergency and sl is not None:
            crossed = False
            if self.direction == "north" and self.y > sl and new_y <= sl:
                crossed = True
            elif self.direction == "south" and self.y < sl and new_y >= sl:
                crossed = True
            elif self.direction == "east" and self.x < sl and new_x >= sl:
                crossed = True
            elif self.direction == "west" and self.x > sl and new_x <= sl:
                crossed = True

            if crossed:
                if self.is_violator:
                    # Violator runs the red light
                    self.red_light_violation = True
                    self.has_crossed_stop_line = True
                else:
                    # Normal vehicle stops
                    if self.direction == "north":
                        self.y = sl + 2
                    elif self.direction == "south":
                        self.y = sl - 2
                    elif self.direction == "east":
                        self.x = sl - 2
                    elif self.direction == "west":
                        self.x = sl + 2
                    self.stopped = True
                    return

        self.x = new_x
        self.y = new_y

    def is_out_of_bounds(self, width, height, margin=100):
        return (self.x < -margin or self.x > width + margin or
                self.y < -margin or self.y > height + margin)


# =====================================================================
#  Signal Phase Definitions
# =====================================================================
SIGNAL_PHASES = [
    {"ns": "green",  "ew": "red",    "duration": 20},
    {"ns": "yellow", "ew": "red",    "duration": 3},
    {"ns": "red",    "ew": "green",  "duration": 20},
    {"ns": "red",    "ew": "yellow", "duration": 3},
]


def phase_to_signals(phase_def):
    return {
        "north": phase_def["ns"],
        "south": phase_def["ns"],
        "east":  phase_def["ew"],
        "west":  phase_def["ew"],
    }


class IntersectionSimulation:
    """Simulates traffic at a single 4-way intersection."""

    def __init__(self, intersection_id, name="Simulated Intersection",
                 width=800, height=600):
        self.id = intersection_id
        self.name = name
        self.width = width
        self.height = height
        self.vehicles = []
        self.lock = threading.Lock()
        self.running = False
        self.thread = None

        # Road geometry
        self.road_width = 120
        self.lane_count = 2
        self.cx = width // 2
        self.cy = height // 2
        hw = self.road_width // 2

        # Stop lines per approach direction
        self.stop_lines = {
            "north": self.cy + hw + 12,
            "south": self.cy - hw - 12,
            "east":  self.cx - hw - 12,
            "west":  self.cx + hw + 12,
        }

        # Per-direction signal state
        self.signals = {"north": "red", "south": "red", "east": "red", "west": "red"}

        # Built-in signal cycling
        self._phase_index = 0
        self._phase_timer = 0.0
        self._use_internal_cycle = True

        # Auto-spawn settings
        self.auto_spawn = True
        self.spawn_rate = 2.0
        self.spawn_types = {
            "car": 0.50, "truck": 0.10, "bus": 0.08,
            "motorcycle": 0.25, "bicycle": 0.05, "ambulance": 0.02,
        }
        self.default_speed = 40
        self.speed_variance = 15

        # Violation probability for auto-spawned vehicles
        self.violation_chance = 0.12   # 12% chance a vehicle is a red-light violator
        self.helmet_viol_chance = 0.30 # 30% of motorcycles/bicycles have no helmet
        self.speeding_chance = 0.15    # 15% chance vehicle spawns above speed limit

        # Stats
        self.total_spawned = 0
        self.total_passed = 0
        self.total_violations = 0

        # Background cache
        self._bg_cache = None

    # ---- signal property for backward compat ----
    @property
    def signal(self):
        return self.signals.get("north", "red")

    def set_signal(self, signal):
        self._use_internal_cycle = False
        self.signals["north"] = signal
        self.signals["south"] = signal
        if signal == "green":
            self.signals["east"] = "red"
            self.signals["west"] = "red"
        elif signal == "yellow":
            self.signals["east"] = "yellow"
            self.signals["west"] = "yellow"
        else:
            self.signals["east"] = "green"
            self.signals["west"] = "green"

    def set_signals(self, signals_dict):
        self._use_internal_cycle = False
        for d in ("north", "south", "east", "west"):
            if d in signals_dict:
                self.signals[d] = signals_dict[d]

    # -----------------------------------------------------------------
    #  Vehicle management
    # -----------------------------------------------------------------
    def spawn_vehicle(self, vehicle_type=None, direction=None, speed=None,
                      lane=None, is_violator=None, helmet_violation=None):
        if vehicle_type is None:
            vehicle_type = random.choices(
                list(self.spawn_types.keys()),
                list(self.spawn_types.values()),
            )[0]
        if direction is None:
            direction = random.choice(["north", "south", "east", "west"])
        if speed is None:
            speed = max(10, self.default_speed + random.uniform(
                -self.speed_variance, self.speed_variance))
            # Random chance of spawning a speeder
            if random.random() < self.speeding_chance:
                speed = random.uniform(SPEED_LIMIT + 10, SPEED_LIMIT + 40)
        if lane is None:
            lane = random.randint(0, self.lane_count - 1)
        if is_violator is None:
            is_violator = random.random() < self.violation_chance
        if helmet_violation is None:
            if vehicle_type in ("motorcycle", "bicycle"):
                helmet_violation = random.random() < self.helmet_viol_chance
            else:
                helmet_violation = False

        hw = self.road_width // 2
        lane_w = hw // self.lane_count
        lane_offset = lane_w // 2 + lane * lane_w

        if direction == "north":
            x = self.cx + lane_offset
            y = self.height + 50
        elif direction == "south":
            x = self.cx - lane_offset
            y = -50
        elif direction == "east":
            x = -50
            y = self.cy + lane_offset
        elif direction == "west":
            x = self.width + 50
            y = self.cy - lane_offset

        v = SimVehicle(vehicle_type, lane, direction, speed, x, y,
                       is_violator=is_violator, helmet_violation=helmet_violation)
        with self.lock:
            self.vehicles.append(v)
            self.total_spawned += 1
        return v.id

    def remove_vehicle(self, vehicle_id):
        with self.lock:
            self.vehicles = [v for v in self.vehicles if v.id != vehicle_id]

    def clear_vehicles(self):
        with self.lock:
            self.vehicles.clear()

    # -----------------------------------------------------------------
    #  Detection (YOLO-compatible output)
    # -----------------------------------------------------------------
    def get_detection_results(self):
        with self.lock:
            vehicles_data = []
            type_counts = {}
            pce_density = 0.0
            emergency_count = 0
            violation_count = 0

            for v in self.vehicles:
                if 0 <= v.x <= self.width and 0 <= v.y <= self.height:
                    type_counts[v.type] = type_counts.get(v.type, 0) + 1
                    pce_density += PCE_VALUES.get(v.type, 1.0)
                    if v.is_emergency:
                        emergency_count += 1

                    has_violation = (v.red_light_violation or v.is_speeding
                                    or v.helmet_violation)
                    if has_violation:
                        violation_count += 1

                    x1 = int(v.x - v.width / 2)
                    y1 = int(v.y - v.height / 2)
                    x2 = int(v.x + v.width / 2)
                    y2 = int(v.y + v.height / 2)

                    vehicles_data.append({
                        "id": v.id,
                        "type": v.type,
                        "confidence": 0.95,
                        "position": (int(v.x), int(v.y)),
                        "bbox": (x1, y1, x2, y2),
                        "size": (v.width, v.height),
                        "is_emergency": v.is_emergency,
                        "license_plate": v.license_plate,
                        "helmet_violation": v.helmet_violation,
                        "passenger_violation": False,
                        "speed_kmh": round(v.speed_kmh, 1),
                        "is_speeding": v.is_speeding,
                        "red_light_violation": v.red_light_violation,
                    })

            return {
                "vehicles": vehicles_data,
                "vehicle_count": len(vehicles_data),
                "pce_density": round(pce_density, 1),
                "vehicle_type_counts": type_counts,
                "has_emergency": emergency_count > 0,
                "emergency_count": emergency_count,
                "violation_count": violation_count,
            }

    # -----------------------------------------------------------------
    #  Rendering
    # -----------------------------------------------------------------
    def _build_background(self):
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        cx, cy = self.cx, self.cy
        hw = self.road_width // 2

        # Grass / terrain
        frame[:] = (45, 80, 35)

        # Sidewalks
        sw = 16
        cv2.rectangle(frame, (cx - hw - sw, 0), (cx + hw + sw, self.height), (140, 140, 140), -1)
        cv2.rectangle(frame, (0, cy - hw - sw), (self.width, cy + hw + sw), (140, 140, 140), -1)

        # Roads (dark asphalt)
        road_color = (55, 55, 55)
        cv2.rectangle(frame, (cx - hw, 0), (cx + hw, self.height), road_color, -1)
        cv2.rectangle(frame, (0, cy - hw), (self.width, cy + hw), road_color, -1)

        # Intersection box
        cv2.rectangle(frame, (cx - hw, cy - hw), (cx + hw, cy + hw), (65, 65, 65), -1)

        # Lane dividers (dashed)
        dash_len, gap_len = 20, 15
        for seg_start in range(0, self.height, dash_len + gap_len):
            if seg_start + dash_len < cy - hw or seg_start > cy + hw:
                cv2.line(frame, (cx, seg_start), (cx, min(seg_start + dash_len, self.height)),
                         (200, 200, 200), 1)
        for seg_start in range(0, self.width, dash_len + gap_len):
            if seg_start + dash_len < cx - hw or seg_start > cx + hw:
                cv2.line(frame, (seg_start, cy), (min(seg_start + dash_len, self.width), cy),
                         (200, 200, 200), 1)

        # Road edge lines (yellow)
        edge_color = (0, 200, 255)
        for y_start, y_end in [(0, cy - hw), (cy + hw, self.height)]:
            cv2.line(frame, (cx - hw, y_start), (cx - hw, y_end), edge_color, 2)
            cv2.line(frame, (cx + hw, y_start), (cx + hw, y_end), edge_color, 2)
        for x_start, x_end in [(0, cx - hw), (cx + hw, self.width)]:
            cv2.line(frame, (x_start, cy - hw), (x_end, cy - hw), edge_color, 2)
            cv2.line(frame, (x_start, cy + hw), (x_end, cy + hw), edge_color, 2)

        # Zebra crossings
        stripe_w, stripe_gap = 8, 6
        cross_depth = 18
        for offset in range(-hw + 4, hw - 4, stripe_w + stripe_gap):
            y0 = cy - hw - cross_depth
            cv2.rectangle(frame, (cx + offset, y0), (cx + offset + stripe_w, cy - hw - 2),
                          (220, 220, 220), -1)
            y0 = cy + hw + 2
            cv2.rectangle(frame, (cx + offset, y0), (cx + offset + stripe_w, cy + hw + cross_depth),
                          (220, 220, 220), -1)
        for offset in range(-hw + 4, hw - 4, stripe_w + stripe_gap):
            x0 = cx + hw + 2
            cv2.rectangle(frame, (x0, cy + offset), (cx + hw + cross_depth, cy + offset + stripe_w),
                          (220, 220, 220), -1)
            x0 = cx - hw - cross_depth
            cv2.rectangle(frame, (x0, cy + offset), (cx - hw - 2, cy + offset + stripe_w),
                          (220, 220, 220), -1)

        return frame

    def _draw_stop_line(self, frame, direction, color):
        cx, cy = self.cx, self.cy
        hw = self.road_width // 2
        sl = self.stop_lines[direction]
        thickness = 3

        if direction == "north":
            cv2.line(frame, (cx, sl), (cx + hw, sl), color, thickness)
        elif direction == "south":
            cv2.line(frame, (cx - hw, sl), (cx, sl), color, thickness)
        elif direction == "east":
            cv2.line(frame, (sl, cy), (sl, cy + hw), color, thickness)
        elif direction == "west":
            cv2.line(frame, (sl, cy - hw), (sl, cy), color, thickness)

    def _draw_traffic_light(self, frame, direction, signal_state):
        cx, cy = self.cx, self.cy
        hw = self.road_width // 2
        r = 8
        gap = 4
        box_w = r * 2 + 8
        box_h = r * 6 + gap * 2 + 12

        if direction == "north":
            bx = cx + hw + 20
            by = cy + hw + 20
        elif direction == "south":
            bx = cx - hw - 20 - box_w
            by = cy - hw - 20 - box_h
        elif direction == "east":
            bx = cx - hw - 20 - box_h
            by = cy + hw + 20
        elif direction == "west":
            bx = cx + hw + 20
            by = cy - hw - 20 - box_h

        cv2.rectangle(frame, (bx, by), (bx + box_w, by + box_h), (30, 30, 30), -1)
        cv2.rectangle(frame, (bx, by), (bx + box_w, by + box_h), (80, 80, 80), 2)

        light_x = bx + box_w // 2

        red_y = by + r + 6
        red_color = (0, 0, 220) if signal_state == "red" else (0, 0, 60)
        cv2.circle(frame, (light_x, red_y), r, red_color, -1)
        cv2.circle(frame, (light_x, red_y), r, (60, 60, 60), 1)

        yel_y = red_y + r * 2 + gap
        yel_color = (0, 220, 220) if signal_state == "yellow" else (0, 60, 60)
        cv2.circle(frame, (light_x, yel_y), r, yel_color, -1)
        cv2.circle(frame, (light_x, yel_y), r, (60, 60, 60), 1)

        grn_y = yel_y + r * 2 + gap
        grn_color = (0, 220, 0) if signal_state == "green" else (0, 60, 0)
        cv2.circle(frame, (light_x, grn_y), r, grn_color, -1)
        cv2.circle(frame, (light_x, grn_y), r, (60, 60, 60), 1)

        label = direction[0].upper()
        cv2.putText(frame, label, (bx + 4, by + box_h + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

    def _draw_vehicle(self, frame, v):
        x1 = int(v.x - v.width / 2)
        y1 = int(v.y - v.height / 2)
        x2 = int(v.x + v.width / 2)
        y2 = int(v.y + v.height / 2)

        color = VEHICLE_COLORS.get(v.type, (180, 180, 180))

        # Determine if this vehicle has any violation for colouring
        has_violation = v.red_light_violation or v.is_speeding or v.helmet_violation

        # Bounding box colour: red for violation, orange for speeding, green normal
        if v.is_emergency:
            box_color = (0, 0, 255)
        elif v.red_light_violation or v.helmet_violation:
            box_color = (0, 0, 255)   # red
        elif v.is_speeding:
            box_color = (0, 165, 255)  # orange
        else:
            box_color = (0, 255, 0)    # green

        # Vehicle body
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, -1)

        # Windshield / cabin highlight
        if v.direction in ("north", "south"):
            cabin_h = max(2, (y2 - y1) // 4)
            cabin_y = y1 + 2 if v.direction == "south" else y2 - cabin_h - 2
            cv2.rectangle(frame, (x1 + 2, cabin_y), (x2 - 2, cabin_y + cabin_h),
                          tuple(min(255, c + 40) for c in color), -1)
        else:
            cabin_w = max(2, (x2 - x1) // 4)
            cabin_x = x1 + 2 if v.direction == "east" else x2 - cabin_w - 2
            cv2.rectangle(frame, (cabin_x, y1 + 2), (cabin_x + cabin_w, y2 - 2),
                          tuple(min(255, c + 40) for c in color), -1)

        # Border in violation colour
        cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 1)

        # Ambulance siren effect
        if v.is_emergency:
            stripe_color = (255, 50, 50) if int(time.time() * 4) % 2 == 0 else (50, 50, 255)
            mid_y = (y1 + y2) // 2
            cv2.rectangle(frame, (x1, mid_y - 2), (x2, mid_y + 2), stripe_color, -1)
            glow_r = max(v.width, v.height) + 8
            overlay = frame.copy()
            cv2.circle(overlay, (int(v.x), int(v.y)), glow_r, stripe_color, 1)
            cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

        # --- License plate label ---
        plate_text = v.license_plate
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.28
        thickness_t = 1

        # Place plate below the vehicle
        (tw, th), _ = cv2.getTextSize(plate_text, font, font_scale, thickness_t)
        plate_x = max(0, int(v.x - tw / 2))
        plate_y = y2 + th + 3

        # Plate background (white rectangle)
        cv2.rectangle(frame,
                      (plate_x - 2, plate_y - th - 2),
                      (plate_x + tw + 2, plate_y + 2),
                      (255, 255, 255), -1)
        cv2.rectangle(frame,
                      (plate_x - 2, plate_y - th - 2),
                      (plate_x + tw + 2, plate_y + 2),
                      (0, 0, 0), 1)
        cv2.putText(frame, plate_text, (plate_x, plate_y),
                    font, font_scale, (0, 0, 0), thickness_t)

        # --- Violation / speed labels above vehicle ---
        label_y = y1 - 5
        if v.red_light_violation:
            cv2.putText(frame, "RED LIGHT!", (x1, label_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)
            label_y -= 14
        if v.is_speeding:
            cv2.putText(frame, f"SPEEDING {v.speed_kmh:.0f}km/h", (x1, label_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 165, 255), 1)
            label_y -= 14
        if v.helmet_violation:
            cv2.putText(frame, "NO HELMET", (x1, label_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 255), 1)
            label_y -= 14
        if not has_violation:
            speed_color = (200, 255, 200)
            cv2.putText(frame, f"{v.speed_kmh:.0f}", (x1, label_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.3, speed_color, 1)

    def render_frame(self):
        if self._bg_cache is None:
            self._bg_cache = self._build_background()
        frame = self._bg_cache.copy()

        sig_colors_bgr = {"red": (0, 0, 255), "yellow": (0, 255, 255), "green": (0, 255, 0)}

        # Stop lines
        for d in ("north", "south", "east", "west"):
            sl_color = sig_colors_bgr.get(self.signals[d], (128, 128, 128))
            self._draw_stop_line(frame, d, sl_color)

        # Traffic lights
        for d in ("north", "south", "east", "west"):
            self._draw_traffic_light(frame, d, self.signals[d])

        # Vehicles
        with self.lock:
            for v in self.vehicles:
                if 0 <= v.x <= self.width and 0 <= v.y <= self.height:
                    self._draw_vehicle(frame, v)

        # HUD top bar
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (420, 65), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        ts = datetime.now().strftime('%H:%M:%S')
        cv2.putText(frame, f"SIM | {self.name} | {ts}", (10, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

        # Per-direction signal indicators
        y_sig = 48
        x_pos = 10
        for d in ("N", "S", "E", "W"):
            full = {"N": "north", "S": "south", "E": "east", "W": "west"}[d]
            sig = self.signals[full]
            color = sig_colors_bgr.get(sig, (128, 128, 128))
            cv2.circle(frame, (x_pos + 6, y_sig - 4), 6, color, -1)
            cv2.circle(frame, (x_pos + 6, y_sig - 4), 7, (200, 200, 200), 1)
            cv2.putText(frame, f"{d}", (x_pos + 16, y_sig),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1)
            x_pos += 55

        # Violation count in HUD
        det = self.get_detection_results()
        if det["violation_count"] > 0:
            viol_text = f"VIOLATIONS: {det['violation_count']}"
            cv2.putText(frame, viol_text, (250, 48),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        # Bottom stats bar
        overlay2 = frame.copy()
        cv2.rectangle(overlay2, (0, self.height - 35), (self.width, self.height), (0, 0, 0), -1)
        cv2.addWeighted(overlay2, 0.6, frame, 0.4, 0, frame)
        cv2.putText(frame,
                    f"Vehicles: {det['vehicle_count']}  |  PCE: {det['pce_density']}  |  Spawned: {self.total_spawned}",
                    (10, self.height - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        if det["has_emergency"]:
            flash = (0, 0, 255) if int(time.time() * 3) % 2 == 0 else (255, 255, 255)
            cv2.putText(frame, "EMERGENCY VEHICLE", (self.width - 240, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, flash, 2)

        return frame

    # -----------------------------------------------------------------
    #  Signal cycling
    # -----------------------------------------------------------------
    def _advance_signal_phase(self, dt):
        if not self._use_internal_cycle:
            return
        self._phase_timer += dt
        phase = SIGNAL_PHASES[self._phase_index]
        if self._phase_timer >= phase["duration"]:
            self._phase_timer = 0.0
            self._phase_index = (self._phase_index + 1) % len(SIGNAL_PHASES)
            new_phase = SIGNAL_PHASES[self._phase_index]
            self.signals = phase_to_signals(new_phase)

    # -----------------------------------------------------------------
    #  Simulation loop
    # -----------------------------------------------------------------
    def _simulation_loop(self):
        last_spawn = time.time()
        last_update = time.time()

        if self._use_internal_cycle:
            self.signals = phase_to_signals(SIGNAL_PHASES[self._phase_index])

        while self.running:
            now = time.time()
            dt = min(now - last_update, 0.1)
            last_update = now

            self._advance_signal_phase(dt)

            with self.lock:
                for v in self.vehicles:
                    my_signal = self.signals.get(v.direction, "red")
                    v.update(dt, my_signal, self.stop_lines)

                before = len(self.vehicles)
                self.vehicles = [v for v in self.vehicles
                                 if not v.is_out_of_bounds(self.width, self.height)]
                self.total_passed += before - len(self.vehicles)

            if self.auto_spawn and now - last_spawn > 1.0 / max(0.1, self.spawn_rate):
                self.spawn_vehicle()
                last_spawn = now

            time.sleep(0.03)

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=3)
            self.thread = None

    def get_config(self):
        det = self.get_detection_results()
        return {
            "id": self.id,
            "name": self.name,
            "running": self.running,
            "auto_spawn": self.auto_spawn,
            "spawn_rate": self.spawn_rate,
            "spawn_types": self.spawn_types,
            "default_speed": self.default_speed,
            "speed_variance": self.speed_variance,
            "signal": self.signal,
            "signals": dict(self.signals),
            "vehicle_count": len(self.vehicles),
            "total_spawned": self.total_spawned,
            "total_passed": self.total_passed,
            "violation_count": det.get("violation_count", 0),
            "width": self.width,
            "height": self.height,
        }

    def update_config(self, config):
        if "auto_spawn" in config:
            self.auto_spawn = config["auto_spawn"]
        if "spawn_rate" in config:
            self.spawn_rate = max(0.1, min(20.0, config["spawn_rate"]))
        if "default_speed" in config:
            self.default_speed = max(5, min(120, config["default_speed"]))
        if "speed_variance" in config:
            self.speed_variance = max(0, min(50, config["speed_variance"]))
        if "spawn_types" in config:
            self.spawn_types.update(config["spawn_types"])
        if "name" in config:
            self.name = config["name"]
        self._bg_cache = None


class SimulationManager:
    """Manages multiple intersection simulations and integrates with the main system."""

    def __init__(self):
        self.simulations = {}
        self.lock = threading.Lock()
        self._feed_thread = None
        self._feed_running = False

    def create_simulation(self, intersection_id, name=None):
        with self.lock:
            if intersection_id in self.simulations:
                return self.simulations[intersection_id]
            sim = IntersectionSimulation(
                intersection_id,
                name=name or f"Simulation {intersection_id}",
            )
            self.simulations[intersection_id] = sim
            return sim

    def get_simulation(self, intersection_id):
        return self.simulations.get(intersection_id)

    def remove_simulation(self, intersection_id):
        with self.lock:
            sim = self.simulations.pop(intersection_id, None)
            if sim:
                sim.stop()

    def start_all(self):
        for sim in self.simulations.values():
            sim.start()

    def stop_all(self):
        for sim in self.simulations.values():
            sim.stop()

    def list_simulations(self):
        return [sim.get_config() for sim in self.simulations.values()]

    def start_feed_to_system(self, intersection_registry, data_lock, frame_lock):
        if self._feed_running:
            return

        self._feed_running = True

        def feed_loop():
            while self._feed_running:
                for int_id, sim in list(self.simulations.items()):
                    if not sim.running:
                        continue

                    # Sync signal from main system -> simulation
                    with data_lock:
                        idata = intersection_registry.get(int_id)
                        if idata and "signal" in idata:
                            sig = idata.get("signal", "")
                            if sig in ("red", "yellow", "green"):
                                sim.set_signal(sig)

                    det = sim.get_detection_results()

                    with data_lock:
                        idata = intersection_registry.get(int_id)
                        if idata:
                            idata["vehicle_count"] = det["vehicle_count"]
                            idata["pce_density"] = det["pce_density"]
                            idata["vehicle_type_counts"] = det["vehicle_type_counts"]
                            idata["has_emergency"] = det["has_emergency"]
                            idata["emergency_count"] = det["emergency_count"]
                            idata["detected_vehicles"] = det["vehicles"]
                            idata["timestamp"] = datetime.now().isoformat()
                            idata["camera_status"] = "active"

                    rendered = sim.render_frame()
                    with frame_lock:
                        idata = intersection_registry.get(int_id)
                        if idata:
                            idata["processed_frame"] = rendered

                time.sleep(0.033)

        self._feed_thread = threading.Thread(target=feed_loop, daemon=True)
        self._feed_thread.start()

    def stop_feed(self):
        self._feed_running = False
        if self._feed_thread:
            self._feed_thread.join(timeout=3)


# Global simulation manager instance
sim_manager = SimulationManager()
