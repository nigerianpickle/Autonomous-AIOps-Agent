import random


class ApplicationSimulator:
    """
    Simulates a running application's telemetry.

    Improvements over v1:
    - Natural recovery: fault effects decay over time even without agent action
    - Fault duration tracking: faults don't linger forever unrealistically
    - Memory pressure can cause latency degradation (metric correlation)
    - Configurable base values for easier experimentation
    """

    def __init__(self):
        # Starting (healthy) values
        self.cpu = 40.0
        self.memory = 50.0
        self.latency = 100.0
        self.error_rate = 0.01
        self.traffic = 300.0

        self.active_fault = None
        self._fault_duration = 0          # steps remaining for current fault
        self._fault_decay_rate = 0.85     # how fast fault effects naturally decay

    # ------------------------------------------------------------------ #
    #  Step                                                                #
    # ------------------------------------------------------------------ #

    def step(self):
        """Advance simulation by one time step."""

        # Normal random fluctuations (Gaussian noise around current value)
        self.cpu        += random.gauss(0, 1.5)
        self.memory     += random.gauss(0, 1.0)
        self.latency    += random.gauss(0, 4.0)
        self.traffic    += random.gauss(0, 15.0)
        self.error_rate += random.gauss(0, 0.001)

        # Correlated pressure: high memory can degrade latency
        if self.memory > 80:
            self.latency += (self.memory - 80) * 0.5

        # Natural fault recovery — even without agent action, faults decay
        if self.active_fault and self._fault_duration > 0:
            self._fault_duration -= 1
            self._apply_decay()
            if self._fault_duration == 0:
                self.active_fault = None

        # Enforce realistic bounds
        self.cpu        = max(0.0,  min(100.0, self.cpu))
        self.memory     = max(0.0,  min(100.0, self.memory))
        self.latency    = max(50.0, self.latency)
        self.error_rate = max(0.0,  min(1.0,   self.error_rate))
        self.traffic    = max(0.0,  self.traffic)

    def _apply_decay(self):
        """Gradually return fault-affected metrics toward normal."""
        # Pull error rate toward baseline
        self.error_rate = self.error_rate * self._fault_decay_rate + 0.01 * (1 - self._fault_decay_rate)
        # Latency decays toward 100ms baseline
        self.latency    = self.latency    * self._fault_decay_rate + 100.0 * (1 - self._fault_decay_rate)
        # CPU decays toward 40% baseline
        self.cpu        = self.cpu        * self._fault_decay_rate + 40.0  * (1 - self._fault_decay_rate)

    # ------------------------------------------------------------------ #
    #  State                                                               #
    # ------------------------------------------------------------------ #

    def get_state(self):
        return {
            "cpu":        round(self.cpu, 2),
            "memory":     round(self.memory, 2),
            "latency":    round(self.latency, 2),
            "error_rate": round(self.error_rate, 4),
            "traffic":    round(self.traffic, 2),
            "fault":      self.active_fault,
        }

    # ------------------------------------------------------------------ #
    #  Actions                                                             #
    # ------------------------------------------------------------------ #

    def apply_action(self, action):
        """
        Apply a remediation action. Actions provide faster recovery than
        natural decay alone.
        """
        if action == "restart_service":
            # Hard reset of error state; latency improves significantly
            self.error_rate  = self.error_rate * 0.2 + 0.01 * 0.8
            self.latency    *= 0.5
            self.cpu         = self.cpu * 0.8 + 40.0 * 0.2
            self.active_fault = None
            self._fault_duration = 0

        elif action == "scale_up":
            # Distribute load: cpu and latency improve
            self.cpu     *= 0.75
            self.latency *= 0.80
            self.traffic  = self.traffic * 0.7 + 300.0 * 0.3
            self.active_fault = None
            self._fault_duration = 0

        elif action == "do_nothing":
            pass

    # ------------------------------------------------------------------ #
    #  Fault injection (called by faults.py)                              #
    # ------------------------------------------------------------------ #

    def inject(self, fault_type, duration=5):
        """Apply a fault with a set duration (steps)."""
        self.active_fault = fault_type
        self._fault_duration = duration

        if fault_type == "traffic_spike":
            self.traffic    += random.uniform(400, 700)
            self.cpu        += random.uniform(20, 40)
            self.latency    += random.uniform(80, 150)

        elif fault_type == "service_crash":
            self.error_rate += random.uniform(0.15, 0.35)
            self.latency    += random.uniform(150, 300)

        elif fault_type == "memory_leak":
            self.memory     += random.uniform(20, 35)