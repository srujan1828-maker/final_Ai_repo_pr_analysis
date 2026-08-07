import time

from e2b import Sandbox
from e2b.exceptions import TimeoutException


class SandboxManager:
    def __init__(self):
        self.sandbox = None

    async def create(self):
        if self.sandbox is None:
            print("Creating new sandbox...")
            self.sandbox = Sandbox.create()
        else:
            print("Reusing existing sandbox...")

        return self.sandbox

    async def run_code(
        self,
        sandbox,
        code: str,
        packages: list[str]
    ):
        # Install packages if provided
        if packages:
            print(f"Installing packages: {packages}")

            install_command = (
                "pip install " + " ".join(packages)
            )

            sandbox.commands.run(install_command)

        # Safely get sandbox metrics (may be empty)
        metrics = sandbox.get_metrics()

        if metrics:
            latest_metrics = metrics[-1]

            cpu_percent = latest_metrics.cpu_used_pct
            memory_used = latest_metrics.mem_used
            memory_total = latest_metrics.mem_total
            disk_used = latest_metrics.disk_used
            disk_total = latest_metrics.disk_total
        else:
            cpu_percent = None
            memory_used = None
            memory_total = None
            disk_used = None
            disk_total = None

        # Save the Python code
        sandbox.files.write(
            "/tmp/main.py",
            code
        )

        # Start timer
        start_time = time.perf_counter()

        try:
            # Execute code
            result = sandbox.commands.run(
                "python /tmp/main.py",
                timeout=30
            )

        except TimeoutException:
            return {
                "stdout": "",
                "stderr": "Execution timed out after 30 seconds.",
                "exit_code": -1,
                "execution_time": round(
                    time.perf_counter() - start_time,
                    4
                ),
                "cpu_percent": cpu_percent,
                "memory_used": memory_used,
                "memory_total": memory_total,
                "disk_used": disk_used,
                "disk_total": disk_total,
            }

        execution_time = round(
            time.perf_counter() - start_time,
            4
        )

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "execution_time": execution_time,
            "cpu_percent": cpu_percent,
            "memory_used": memory_used,
            "memory_total": memory_total,
            "disk_used": disk_used,
            "disk_total": disk_total,
        }

    async def run_tests(
        self,
        sandbox,
        code: str,
        tests: str,
        packages: list[str]
    ):
        # Install packages if provided
        if packages:
            sandbox.commands.run(
                "pip install " + " ".join(packages)
            )

        # Save the user's solution
        sandbox.files.write(
            "/tmp/solution.py",
            code
        )

        # Save the test file
        sandbox.files.write(
            "/tmp/test_solution.py",
            tests
        )

        # Execute the tests
        result = sandbox.commands.run(
            "python /tmp/test_solution.py",
            timeout=30
        )

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "status": "PASSED" if result.exit_code == 0 else "FAILED",
        }

    async def cleanup(self):
        if self.sandbox is not None:
            print("Deleting sandbox...")

            self.sandbox.kill()

            self.sandbox = None


manager = SandboxManager()