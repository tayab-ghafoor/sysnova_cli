import sys
import time


class ProgressBar:
    """
    Simple terminal progress bar.
    Usage:
        bar = ProgressBar(total=100, label="Uploading")
        bar.update(50)   # 50%
        bar.finish()
    """

    def __init__(self, total: int = 100, label: str = "Progress", width: int = 40):
        self.total = total
        self.label = label
        self.width = width
        self.current = 0

    def update(self, value: int):
        self.current = min(value, self.total)
        percent = int((self.current / self.total) * 100)
        filled = int((self.current / self.total) * self.width)
        bar = "█" * filled + "░" * (self.width - filled)
        sys.stdout.write(f"\r  {self.label}: [{bar}] {percent}%")
        sys.stdout.flush()

    def finish(self):
        self.update(self.total)
        print()  # newline after bar completes


def simulate_progress(label: str = "Uploading backup to cloud", steps: list = None):
    """
    Simulate progress display at defined checkpoints.
    steps: list of (percent, delay_seconds) tuples.
    """
    if steps is None:
        steps = [(10, 0.3), (25, 0.4), (50, 0.5), (75, 0.4), (100, 0.3)]

    bar = ProgressBar(label=label)
    for percent, delay in steps:
        bar.update(percent)
        time.sleep(delay)
    bar.finish()


def print_step(message: str):
    """Print a clearly visible step message to the terminal."""
    print(f"\n  ➤  {message}")


def print_success(message: str):
    print(f"  ✅  {message}")


def print_error(message: str):
    print(f"  ❌  {message}")


def print_warning(message: str):
    print(f"  ⚠️   {message}")


def print_info(message: str):
    print(f"  ℹ️   {message}")
