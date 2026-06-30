"""The single Processor interface every transform implements."""


class Processor:
    """Transforms a BGR uint8 frame into a BGR uint8 frame.

    Subclasses set:
      name          - short id / display name
      category      - "filter" | "neural" | "arbitrary"
      has_strength  - whether `set_strength` does anything (drives the UI slider)
    """

    name = "identity"
    category = "filter"
    has_strength = False

    def process(self, frame_bgr):
        return frame_bgr

    def set_strength(self, value):
        """value in 0..1; no-op unless the processor exposes a strength param."""
        pass

    def get_strength(self):
        return 0.0

    def warmup(self, height, width):
        """Optional: run one dummy pass so the first live frame doesn't stutter."""
        pass
