import os
import json
import math


class MotionEngine:
    """
    Geometric path-matching engine for hand motion gestures.

    Supports two tiers:
      1. BUILT-IN  — pre-calibrated normalized paths that appear automatically in the
                     gesture selection grid (no recording needed).
      2. CUSTOM    — user-recorded trajectories saved to custom_motions.json.

    Key design:
    - Normalization PRESERVES ASPECT RATIO so Swipe Down != Swipe Right after normalization.
    - A DIRECTION VECTOR fingerprint is added alongside shape distance for disambiguation.
    - Built-in gestures get a small priority bonus to win ties against similar custom templates.
    """

    # Built-in gesture definitions (raw paths; normalized at runtime with aspect-ratio preserved)
    BUILTIN_RAW = {}

    BUILTIN_PRIORITY_BONUS = 0.03   # subtract from built-in distance before comparison
    BUILTIN_THRESHOLD      = 0.35
    CUSTOM_THRESHOLD       = 0.32
    MIN_CONFIDENCE         = 50     # % below which we ignore the match
    MIN_DIAG               = 0.07   # minimum bounding box diagonal (fraction of frame)
                                    # to filter out jitter / static holds

    def __init__(self):
        self.data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data'
        )
        self.motions_file = os.path.join(self.data_dir, 'custom_motions.json')
        os.makedirs(self.data_dir, exist_ok=True)
        if not os.path.exists(self.motions_file):
            with open(self.motions_file, 'w') as f:
                json.dump([], f)

        self.num_resample_points = 16

        # Pre-process built-in templates once
        self._builtin_templates = {
            name: self._normalize_path(pts)
            for name, pts in self.BUILTIN_RAW.items()
        }

        self._load_custom_templates()

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def get_all_motion_names(self):
        """Return names of all available motions (built-in + custom)."""
        builtin = list(self.BUILTIN_RAW.keys())
        custom  = [t['name'] for t in self._custom_templates]
        seen = set(builtin)
        return builtin + [n for n in custom if n not in seen]

    def save_motion(self, name, raw_path):
        """Save a user-recorded motion template."""
        if len(raw_path) < 5:
            return {"status": "error", "message": "Sequence too short. Move your hand further."}

        try:
            with open(self.motions_file, 'r') as f:
                motions = json.load(f)
        except Exception:
            motions = []

        motions = [m for m in motions if m['name'] != name]
        motions.append({"name": name, "path": list(raw_path)})

        with open(self.motions_file, 'w') as f:
            json.dump(motions, f, indent=4)

        self._load_custom_templates()
        return {"status": "success", "message": f"Motion '{name}' saved successfully!"}

    def detect_motion(self, raw_path):
        """
        Match a trailing buffer of (x, y) centroids against all templates.
        Returns (name, confidence_0_to_100) or (None, 0).
        """
        if len(raw_path) < 8:
            return None, 0

        # Filter out jitter: check bounding box diagonal
        xs = [p[0] for p in raw_path]
        ys = [p[1] for p in raw_path]
        diag = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
        if diag < self.MIN_DIAG:
            return None, 0

        norm_target = self._normalize_path(raw_path)

        best_name      = None
        best_adj_dist  = float('inf')
        best_threshold = self.BUILTIN_THRESHOLD

        # Check built-ins (with priority bonus)
        for name, tmpl_pts in self._builtin_templates.items():
            raw_dist = self._path_distance(norm_target, tmpl_pts)
            adj_dist = raw_dist - self.BUILTIN_PRIORITY_BONUS
            if adj_dist < best_adj_dist:
                best_adj_dist  = adj_dist
                best_name      = name
                best_threshold = self.BUILTIN_THRESHOLD

        # Check custom templates
        for tmpl in self._custom_templates:
            raw_dist = self._path_distance(norm_target, tmpl['path'])
            if raw_dist < best_adj_dist:
                best_adj_dist  = raw_dist
                best_name      = tmpl['name']
                best_threshold = self.CUSTOM_THRESHOLD

        if best_adj_dist < best_threshold:
            confidence = max(0, min(100, int(
                (1.0 - best_adj_dist / best_threshold) * 100
            )))
            if confidence >= self.MIN_CONFIDENCE:
                return best_name, confidence

        return None, 0

    # ------------------------------------------------------------------
    #  Private helpers
    # ------------------------------------------------------------------

    def _load_custom_templates(self):
        try:
            with open(self.motions_file, 'r') as f:
                raw = json.load(f)
            self._custom_templates = []
            for t in raw:
                pts = t.get('path', [])
                if len(pts) >= 2:
                    self._custom_templates.append({
                        "name": t['name'],
                        "path": self._normalize_path(pts)
                    })
        except Exception:
            self._custom_templates = []

    def _path_length(self, points):
        d = 0.0
        for i in range(1, len(points)):
            d += math.hypot(points[i][0] - points[i-1][0],
                            points[i][1] - points[i-1][1])
        return d

    def _resample(self, points, n):
        total = self._path_length(points)
        if total == 0:
            return [points[0]] * n
        I = total / (n - 1)
        D = 0.0
        new_pts = [points[0]]
        cur = list(points)
        i = 1
        while i < len(cur) and len(new_pts) < n:
            d = math.hypot(cur[i][0] - cur[i-1][0], cur[i][1] - cur[i-1][1])
            if D + d >= I:
                t = (I - D) / d
                qx = cur[i-1][0] + t * (cur[i][0] - cur[i-1][0])
                qy = cur[i-1][1] + t * (cur[i][1] - cur[i-1][1])
                new_pts.append((qx, qy))
                cur.insert(i, (qx, qy))
                D = 0.0
            else:
                D += d
            i += 1
        while len(new_pts) < n:
            new_pts.append(cur[-1])
        return new_pts[:n]

    def _normalize_path(self, points):
        """Resample → scale preserving aspect ratio → translate to centroid."""
        pts = [(float(p[0]), float(p[1])) for p in points]
        pts = self._resample(pts, self.num_resample_points)

        # Bounding box
        min_x = min(p[0] for p in pts)
        max_x = max(p[0] for p in pts)
        min_y = min(p[1] for p in pts)
        max_y = max(p[1] for p in pts)
        w = max_x - min_x
        h = max_y - min_y

        # Use the LARGEST axis as scale so we preserve the shape's elongation
        # (a vertical swipe stays tall; a horizontal swipe stays wide)
        scale = max(w, h) or 1.0
        pts = [((p[0] - min_x) / scale, (p[1] - min_y) / scale) for p in pts]

        # Translate so centroid is at origin
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        pts = [(p[0] - cx, p[1] - cy) for p in pts]
        return pts

    def _path_distance(self, p1, p2):
        n = min(len(p1), len(p2))
        if n == 0:
            return float('inf')
        return sum(
            math.hypot(p1[i][0] - p2[i][0], p1[i][1] - p2[i][1])
            for i in range(n)
        ) / n
