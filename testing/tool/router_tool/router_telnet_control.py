import time
from testing.tool.dut_tool.transports.telnet_tool import TelnetSession


class TelnetVerifier:
    """A simple, dedicated class for verifying router state via Telnet."""

    def __init__(self, host: str, password: str):
        self.host = host
        self.password = password
        self.session = None
        self.prompt = b":/tmp/home/root#"

    def __enter__(self):
        self.session = TelnetSession(host=self.host, port=23, timeout=10)
        self.session.open()

        # Login sequence
        self.session.read_until(b"login:", timeout=5)
        self.session.write(b"admin\n")
        self.session.read_until(b"Password:", timeout=5)
        self.session.write(self.password.encode("ascii") + b"\n")
        self.session.read_until(self.prompt, timeout=5)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            self.session.close()

    def run_command(self, cmd: str, sleep_time: float = 0.5) -> str:
        """
        Execute a command and return the stripped output.
        :param cmd: The command to execute.
        :param sleep_time: Time to wait for the command to complete.
        """
        self.session.write((cmd + "\n").encode("ascii"))
        time.sleep(sleep_time)  # Allow command to execute
        raw_output = self.session.read_until(self.prompt, timeout=5)
        output_str = raw_output.decode('utf-8', errors='ignore')
        # Parse the output: find the last non-empty line that is not the prompt
        lines = [line.strip() for line in output_str.splitlines() if line.strip()]
        for line in reversed(lines):
            if not line.endswith("#"):
                return line
        return ""
