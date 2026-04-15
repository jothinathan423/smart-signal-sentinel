"""
Traffic Simulation Engine for Smart Signal Sentinel
=====================================================
Generates realistic virtual traffic at intersections so the full system
(signal control, violation detection, emergency corridors, dashboard)
can be tested without physical cameras.

Vehicles are rendered as colored rectangles on a top-down road image
and fed into the existing MJPEG stream + detection pipeline.
"""

import cv2
import numpy as np
import time
import threading
import random
import math
from collections import deque
from datetime import datetime

# ============= VEHICLE COLORS (BGR) =============
VEHICLE_COLORS = {
    "car": (180, 180, 60),       # steel blue
    "truck": (50, 50, 180),      # dark red
    "bus": (30, 140, 220),       # orange
    "motorcycle": (200, 200, 0), # cyan
    "bicycle": (0, 200, 0),      # green
    "ambulance": (0, 0, 255),    # red with blue stripe
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


class SimVehicle:
    """A single simulated vehicle."""

    _next_id = 1

    def __init__(self, vehicle_type="car", lane=0, direction="north",
                 speed=40, x=0, y=0):
        self.id = f"sim-v{SimVehicle._next_id}"
        SimVehicle._next_id += 1
        self.type = vehicle_type
        self.lane = lane
        self.direction = direction  # north, south, east, west
        self.speed_kmh = speed      # km/h
        self.x = float(x)
        self.y = float(y)
        self.is_emergency = vehicle_type == "ambulance"
        self.stopped = False
        self.created_at = time.time()

        w, h = VEHICLE_SIZES.get(vehicle_type, (40, 22))
        if direction in ("north", "south"):
            self.width, self.height = h, w
        else:
            self.width, self.height = w, h

    def pixels_per_second(self):
        """Convert km/h to pixels/sec (1 meter ≈ 8 pixels in sim)."""
        return self.speed_kmh * 8.0 / 3.6

    def update(self, dt, signal, stop_line_y, road_bounds):
        """Move vehicle, respecting red signals and stop lines."""
        if self.stopped:
            # Check if signal turned green
            if signal == "green" or self.is_emergency:
                self.stopped = False
            else:
                return

        pps = self.pixels_per_second()
        # Movement direction
        dx, dy = 0, 0
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

        # Stop at red/yellow signal before stop line
        if signal in ("red", "yellow") and not self.is_emergency:
            if self.direction == "north" and self.y > stop_line_y and new_y <= stop_line_y:
                self.y = stop_line_y + 2
                self.stopped = True
                return
            elif self.direction == "south" and self.y < stop_line_y and new_y >= stop_line_y:
                self.y = stop_line_y - 2
                self.stopped = True
                return
            elif self.direction == "east" and self.x < stop_line_y and new_x >= stop_line_y:
                self.x = stop_line_y - 2
                self.stopped = True
                return
            elif self.direction == "west" and self.x > stop_line_y and new_x <= stop_line_y:
                self.x = stop_line_y + 2
                self.stopped = True
                return

        self.x = new_x
        self.y = new_y

    def is_out_of_bounds(self, width, height, margin=100):
        return (self.x < -margin or self.x > width + margin or
                self.y < -margin or self.y > height + margin)


class IntersectionSimulation:
    """Simulates traffic at a single intersection with 4-way roads."""

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

        # Road configuration
        self.road_width = 120
        self.center_x = width // 2
        self.center_y = height // 2
        self.stop_line_y = self.center_y - self.road_width // 2 - 10

        # Signal state (managed externally by the main system)
        self.signal = "red"

        # Auto-spawn settings
        self.auto_spawn = True
        self.spawn_rate = 2.0       # vehicles per second
        self.spawn_types = {
            "car": 0.50,
            "truck": 0.10,
            "bus": 0.08,
            "motorcycle": 0.25,
            "bicycle": 0.05,
            "ambulance": 0.02,
        }
        self.default_speed = 40     # km/h
        self.speed_variance = 15    # ±km/h

        # Stats
        self.total_spawned = 0
        self.total_passed = 0

    def spawn_vehicle(self, vehicle_type=None, direction=None, speed=None, lane=None):
        """Spawn a vehicle at the edge of the intersection."""
        if vehicle_type is None:
            vehicle_type = random.choices(
                list(self.spawn_types.keys()),
                list(self.spawn_types.values())
            )[0]

        if direction is None:
            direction = random.choice(["north", "south", "east", "west"])

        if speed is None:
            speed = max(10, self.default_speed + random.uniform(
                -self.speed_variance, self.speed_variance))

        if lane is None:
            lane = random.randint(0, 1)

        # Starting positions at road edges
        lane_offset = 15 + lane * 30
        if direction == "north":
            x = self.center_x + lane_offset
            y = self.height + 50
        elif direction == "south":
            x = self.center_x - lane_offset
            y = -50
        elif direction == "east":
            x = -50
            y = self.center_y + lane_offset
        elif direction == "west":
            x = self.width + 50
            y = self.center_y - lane_offset

        v = SimVehicle(vehicle_type, lane, direction, speed, x, y)
        with self.lock:
            self.vehicles.append(v)
            self.total_spawned += 1
        return v.id

    def remove_vehicle(self, vehicle_id):
        """Remove a specific vehicle."""
        with self.lock:
            self.vehicles = [v for v in self.vehicles if v.id != vehicle_id]

    def clear_vehicles(self):
        """Remove all vehicles."""
        with self.lock:
            self.vehicles.clear()

    def set_signal(self, signal):
        """Update signal state."""
        self.signal = signal

    def get_detection_results(self):
        """Return detection data in the same format as YOLO detection."""
        with self.lock:
            vehicles_data = []
            type_counts = {}
            pce_density = 0.0
            has_emergency = False
            emergency_count = 0

            for v in self.vehicles:
                # Only count vehicles inside the visible frame
                if 0 <= v.x <= self.width and 0 <= v.y <= self.height:
                    type_counts[v.type] = type_counts.get(v.type, 0) + 1
                    pce_density += PCE_VALUES.get(v.type, 1.0)

                    if v.is_emergency:
                        has_emergency = True
                        emergency_count += 1

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
                        "license_plate": "N/A",
                        "helmet_violation": False,
                        "passenger_violation": False,
                        "speed_kmh": round(v.speed_kmh, 1),
                        "is_speeding": v.speed_kmh > 40,
                        "red_light_violation": False,
                    })

            return {
                "vehicles": vehicles_data,
                "vehicle_count": len(vehicles_data),
                "pce_density": round(pce_density, 1),
                "vehicle_type_counts": type_counts,
                "has_emergency": has_emergency,
                "emergency_count": emergency_count,
            }

    def render_frame(self):
        """Render the intersection as a top-down view image."""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # Background (dark gray)
        frame[:] = (40, 40, 40)

        cx, cy = self.center_x, self.center_y
        rw = self.road_width

        # Draw roads (dark asphalt)
        cv2.rectangle(frame, (cx - rw // 2, 0), (cx + rw // 2, self.height), (60, 60, 60), -1)
        cv2.rectangle(frame, (0, cy - rw // 2), (self.width, cy + rw // 2), (60, 60, 60), -1)

        # Road markings - center dashed lines
        for i in range(0, self.height, 30):
            cv2.line(frame, (cx, i), (cx, i + 15), (80, 80, 80), 1)
        for i in range(0, self.width, 30):
            cv2.line(frame, (i, cy), (i + 15, cy), (80, 80, 80), 1)

        # Road edge lines (white)
        cv2.line(frame, (cx - rw // 2, 0), (cx - rw // 2, cy - rw // 2), (150, 150, 150), 2)
        cv2.line(frame, (cx + rw // 2, 0), (cx + rw // 2, cy - rw // 2), (150, 150, 150), 2)
        cv2.line(frame, (cx - rw // 2, cy + rw // 2), (cx - rw // 2, self.height), (150, 150, 150), 2)
        cv2.line(frame, (cx + rw // 2, cy + rw // 2), (cx + rw // 2, self.height), (150, 150, 150), 2)

        cv2.line(frame, (0, cy - rw // 2), (cx - rw // 2, cy - rw // 2), (150, 150, 150), 2)
        cv2.line(frame, (0, cy + rw // 2), (cx - rw // 2, cy + rw // 2), (150, 150, 150), 2)
        cv2.line(frame, (cx + rw // 2, cy - rw // 2), (self.width, cy - rw // 2), (150, 150, 150), 2)
        cv2.line(frame, (cx + rw // 2, cy + rw // 2), (self.width, cy + rw // 2), (150, 150, 150), 2)

        # Crosswalk stripes
        for offset in range(-rw // 2, rw // 2, 12):
            y_top = cy - rw // 2 - 15
            cv2.rectangle(frame, (cx + offset, y_top), (cx + offset + 6, y_top + 10), (200, 200, 200), -1)
            y_bot = cy + rw // 2 + 5
            cv2.rectangle(frame, (cx + offset, y_bot), (cx + offset + 6, y_bot + 10), (200, 200, 200), -1)

        # Stop line
        sl_y = self.stop_line_y
        sig_colors = {"red": (0, 0, 255), "yellow": (0, 255, 255), "green": (0, 255, 0)}
        sl_color = sig_colors.get(self.signal, (0, 255, 255))
        cv2.line(frame, (cx, sl_y), (cx + rw // 2, sl_y), sl_color, 3)

        # Draw signal indicator circle
        sig_color = sig_colors.get(self.signal, (128, 128, 128))
        cv2.circle(frame, (cx - rw // 2 - 25, cy - rw // 2 - 25), 15, sig_color, -1)
        cv2.circle(frame, (cx - rw // 2 - 25, cy - rw // 2 - 25), 16, (255, 255, 255), 2)

        # Draw vehicles
        with self.lock:
            for v in self.vehicles:
                if not (0 <= v.x <= self.width and 0 <= v.y <= self.height):
                    continue

                x1 = int(v.x - v.width / 2)
                y1 = int(v.y - v.height / 2)
                x2 = int(v.x + v.width / 2)
                y2 = int(v.y + v.height / 2)

                color = VEHICLE_COLORS.get(v.type, (180, 180, 180))

                # Vehicle body
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, -1)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), 1)

                # Ambulance siren stripes
                if v.is_emergency:
                    stripe_color = (255, 0, 0) if int(time.time() * 4) % 2 == 0 else (0, 0, 255)
                    mid_y = (y1 + y2) // 2
                    cv2.rectangle(frame, (x1, mid_y - 2), (x2, mid_y + 2), stripe_color, -1)

                # Speed label
                speed_color = (0, 0, 255) if v.speed_kmh > 40 else (0, 255, 0)
                cv2.putText(frame, f"{v.speed_kmh:.0f}", (x1, y1 - 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.3, speed_color, 1)

        # HUD overlay
        ts = datetime.now().strftime('%H:%M:%S')
        cv2.putText(frame, f"SIM | {self.name} | {ts}", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        sig_text_color = sig_colors.get(self.signal, (128, 128, 128))
        cv2.putText(frame, f"Signal: {self.signal.upper()}", (10, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, sig_text_color, 2)

        det = self.get_detection_results()
        cv2.putText(frame, f"Vehicles: {det['vehicle_count']} | PCE: {det['pce_density']}", (10, self.height - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        if det["has_emergency"]:
            cv2.putText(frame, "EMERGENCY VEHICLE", (self.width - 250, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        return frame

    def _simulation_loop(self):
        """Background thread: moves vehicles, auto-spawns, removes out-of-bounds."""
        last_spawn = time.time()
        last_update = time.time()

        while self.running:
            now = time.time()
            dt = now - last_update
            last_update = now

            # Update vehicle positions
            with self.lock:
                for v in self.vehicles:
                    v.update(dt, self.signal, self.stop_line_y,
                             (self.width, self.height))

                # Remove out-of-bounds vehicles
                before = len(self.vehicles)
                self.vehicles = [v for v in self.vehicles
                                 if not v.is_out_of_bounds(self.width, self.height)]
                self.total_passed += before - len(self.vehicles)

            # Auto-spawn
            if self.auto_spawn and now - last_spawn > 1.0 / max(0.1, self.spawn_rate):
                self.spawn_vehicle()
                last_spawn = now

            time.sleep(0.03)  # ~30 FPS simulation tick

    def start(self):
        """Start the simulation loop."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the simulation loop."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=3)
            self.thread = None

    def get_config(self):
        """Return current simulation config."""
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
            "vehicle_count": len(self.vehicles),
            "total_spawned": self.total_spawned,
            "total_passed": self.total_passed,
            "width": self.width,
            "height": self.height,
        }

    def update_config(self, config):
        """Update simulation parameters."""
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


class SimulationManager:
    """Manages multiple intersection simulations and integrates with the main system."""

    def __init__(self):
        self.simulations = {}  # {intersection_id: IntersectionSimulation}
        self.lock = threading.Lock()
        self._feed_thread = None
        self._feed_running = False

    def create_simulation(self, intersection_id, name=None):
        """Create a simulation for an intersection."""
        with self.lock:
            if intersection_id in self.simulations:
                return self.simulations[intersection_id]
            sim = IntersectionSimulation(
                intersection_id,
                name=name or f"Simulation {intersection_id}"
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
        """Background thread that feeds simulation data into the main system."""
        if self._feed_running:
            return

        self._feed_running = True

        def feed_loop():
            while self._feed_running:
                for int_id, sim in list(self.simulations.items()):
                    if not sim.running:
                        continue

                    # Sync signal from main system → simulation
                    with data_lock:
                        idata = intersection_registry.get(int_id)
                        if idata:
                            sim.set_signal(idata.get("signal", "red"))

                    # Get detection results from simulation
                    det = sim.get_detection_results()

                    # Feed into main system's intersection registry
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

                    # Render frame and feed to stream
                    rendered = sim.render_frame()
                    with frame_lock:
                        idata = intersection_registry.get(int_id)
                        if idata:
                            idata["processed_frame"] = rendered

                time.sleep(0.033)  # ~30 FPS

        self._feed_thread = threading.Thread(target=feed_loop, daemon=True)
        self._feed_thread.start()

    def stop_feed(self):
        self._feed_running = False
        if self._feed_thread:
            self._feed_thread.join(timeout=3)


# Global simulation manager instance
sim_manager = SimulationManager()
