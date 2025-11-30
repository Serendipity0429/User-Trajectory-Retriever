from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connection
import subprocess
import re
import os
import time
import io
from contextlib import redirect_stdout, redirect_stderr
import matplotlib.pyplot as plt
import numpy as np


class Command(BaseCommand):
    help = "Runs an end-to-end performance benchmark on the server."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            type=str,
            default="benchmark_graphs",
            help="Directory to save graph output files.",
        )
        parser.add_argument(
            "--scale",
            type=str,
            choices=["small", "large"],
            default="small",
            help="Scale of the benchmark to run.",
        )
        parser.add_argument(
            "--requests",
            type=int,
            help="Override the total number of requests for each test run.",
        )
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Clean up all test data without running benchmarks.",
        )

    def handle(self, *args, **options):
        if options["clean"]:
            self._cleanup_test_data()
            self.stdout.write(
                self.style.SUCCESS("Benchmark data cleaned successfully.")
            )
            return
        self._main_benchmark_logic(options)

    def _run_test(
        self,
        concurrency,
        payload_size,
        num_requests=15,
        description="Testing",
        suppress_result_print=False,
    ):
        self.stdout.write(
            f"  - {description}: C={concurrency}, P={payload_size}KB...", ending=""
        )
        self.stdout.flush()

        f_stdout = io.StringIO()
        f_stderr = io.StringIO()

        try:
            with redirect_stdout(f_stdout), redirect_stderr(f_stderr):
                call_command(
                    "pressure_test",
                    "--requests",
                    str(num_requests),
                    "--concurrency",
                    str(concurrency),
                    "--payload-size",
                    str(payload_size),
                    "--no-cleanup",
                )
            output = f_stdout.getvalue()

            failed_count = (
                int(re.search(r"Failed requests:\s+(\d+)", output).group(1))
                if re.search(r"Failed requests:\s+(\d+)", output)
                else 0
            )
            time_match = re.search(
                r"Time per request:\s+([\d.]+)\s+\[ms\] \(mean\)", output
            )

            if time_match:
                response_time = float(time_match.group(1))
                if not suppress_result_print:
                    msg = f" {response_time:.2f} ms"
                    if failed_count > 0:
                        msg = f" PARTIAL FAIL ({failed_count}/{num_requests} failed), Avg Time:{msg}"
                    self.stdout.write(msg)
                else:
                    self.stdout.write(" OK")
                return response_time, failed_count
            else:
                self.stdout.write(
                    " UNEXPECTED OUTPUT" if not suppress_result_print else " FAIL"
                )
                return -4.0, num_requests

        except Exception as e:
            self.stdout.write(
                f" FAILED (error: {e})" if not suppress_result_print else " FAIL"
            )
            return None, None

    def _setup_test_data(self, populate_count):
        self.stdout.write(f"--- Setting up DB with {populate_count} records ---")
        with open(os.devnull, "w") as f, redirect_stdout(f), redirect_stderr(f):
            call_command("pressure_test", "--user-only")
            call_command("pressure_test", "--populate", str(populate_count))
        self.stdout.write("Setup complete.")

    def _cleanup_test_data(self):
        self.stdout.write("--- Cleaning up test data & compacting database ---")
        with open(os.devnull, "w") as f, redirect_stdout(f), redirect_stderr(f):
            call_command("pressure_test", "--cleanup")

        engine = settings.DATABASES["default"]["ENGINE"]

        if "sqlite3" in engine:
            db_path = settings.DATABASES["default"]["NAME"]
            if os.path.exists(db_path):
                self.stdout.write("Compacting SQLite database file...")
                subprocess.run(
                    ["sqlite3", db_path, "VACUUM;"], capture_output=True, text=True
                )

        elif "postgresql" in engine:
            self.stdout.write("Compacting PostgreSQL database...")
            with connection.cursor() as cursor:
                cursor.execute("VACUUM FULL;")

        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Warning: Automatic database compaction is not supported for the '{engine}' engine. "
                    "Results may be affected by data fragmentation."
                )
            )

    def _draw_graphs(
        self,
        all_results,
        db_sizes,
        concurrency_levels,
        payload_sizes,
        num_requests,
        output_dir,
    ):
        self.stdout.write(
            self.style.SUCCESS("\n\n====== Generating Visual Graphs ======")
        )
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        plt.style.use("seaborn-v0_8-whitegrid")

        for db_size in db_sizes:
            self.stdout.write(
                f"\n--- Generating graphs for DB size: {db_size} records ---"
            )
            db_results = [r for r in all_results if r["db_size"] == db_size]
            if not db_results:
                self.stdout.write(f"No data to plot for DB size {db_size}.")
                continue

            # Performance Graphs
            perf_results = [
                r for r in db_results if r.get("avg_response_time_ms", -1) > 0
            ]
            if perf_results:
                fig2d_perf, ax2d_perf = plt.subplots(figsize=(12, 8))
                for payload in sorted(payload_sizes):
                    xs = sorted(concurrency_levels)
                    ys = [
                        next(
                            (
                                r["avg_response_time_ms"]
                                for r in perf_results
                                if r["concurrency"] == c
                                and r["payload_size_kb"] == payload
                            ),
                            np.nan,
                        )
                        for c in xs
                    ]
                    if not all(np.isnan(ys)):
                        ax2d_perf.plot(
                            xs,
                            ys,
                            marker="o",
                            linestyle="-",
                            label=f"Payload {payload / 1024:.2f}MB",
                        )

                ax2d_perf.set_xscale("log", base=2)
                ax2d_perf.set_yscale("log")
                ax2d_perf.set_xlabel("Concurrency (log scale)")
                ax2d_perf.set_ylabel("Avg. Response Time (ms, log scale)")
                ax2d_perf.set_title(
                    f"Performance Profile (Log-Log)\nDB Size: {db_size} records"
                )
                ax2d_perf.legend()
                ax2d_perf.grid(True, which="both", ls="--")
                fig2d_perf.tight_layout()
                plt.savefig(os.path.join(output_dir, f"perf_2d_db_{db_size}.png"))
                plt.close(fig2d_perf)

                fig3d_perf = plt.figure(figsize=(14, 10))
                ax3d_perf = fig3d_perf.add_subplot(111, projection="3d")
                X, Y = np.meshgrid(sorted(concurrency_levels), sorted(payload_sizes))
                Z = np.array(
                    [
                        [
                            next(
                                (
                                    r["avg_response_time_ms"]
                                    for r in perf_results
                                    if r["concurrency"] == c
                                    and r["payload_size_kb"] == p
                                ),
                                np.nan,
                            )
                            for c in sorted(concurrency_levels)
                        ]
                        for p in sorted(payload_sizes)
                    ]
                )

                if not np.all(np.isnan(Z)):
                    ax3d_perf.plot_surface(
                        np.log2(X),
                        np.log2(Y),
                        np.log10(Z),
                        cmap="magma",
                        edgecolor="k",
                        linewidth=0.5,
                        alpha=0.9,
                    )
                    ax3d_perf.set_xlabel("Concurrency (log2 scale)")
                    ax3d_perf.set_ylabel("Payload Size (KB, log2 scale)")
                    ax3d_perf.set_zlabel("Response Time (ms, log10 scale)")
                    ax3d_perf.set_title(
                        f"3D Performance Surface (Log-Log-Log)\nDB Size: {db_size} records"
                    )
                    ax3d_perf.invert_xaxis()
                    ax3d_perf.view_init(elev=20, azim=-65)
                    plt.savefig(os.path.join(output_dir, f"perf_3d_db_{db_size}.png"))
                plt.close(fig3d_perf)

            error_results = [r for r in db_results if "error_rate" in r]
            if error_results:
                fig2d_err, ax2d_err = plt.subplots(figsize=(12, 8))
                for payload in sorted(payload_sizes):
                    xs = sorted(concurrency_levels)
                    ys = [
                        next(
                            (
                                r["error_rate"] * 100
                                for r in error_results
                                if r["concurrency"] == c
                                and r["payload_size_kb"] == payload
                            ),
                            np.nan,
                        )
                        for c in xs
                    ]
                    if not all(np.isnan(ys)):
                        ax2d_err.plot(
                            xs,
                            ys,
                            marker="x",
                            linestyle="--",
                            label=f"Payload {payload / 1024:.2f}MB",
                        )

                ax2d_err.set_xscale("log", base=2)
                ax2d_err.set_yscale("symlog", linthresh=1)
                ax2d_err.set_xlabel("Concurrency (log scale)")
                ax2d_err.set_ylabel("Error Rate (%, symlog scale)")
                ax2d_err.set_title(
                    f"Error Rate Profile (Log-Symlog)\nDB Size: {db_size} records"
                )
                ax2d_err.legend()
                ax2d_err.grid(True, which="both", ls="--")
                fig2d_err.tight_layout()
                plt.savefig(os.path.join(output_dir, f"error_2d_db_{db_size}.png"))
                plt.close(fig2d_err)

                fig3d_err = plt.figure(figsize=(14, 10))
                ax3d_err = fig3d_err.add_subplot(111, projection="3d")
                X, Y = np.meshgrid(sorted(concurrency_levels), sorted(payload_sizes))
                Z_err = np.array(
                    [
                        [
                            next(
                                (
                                    r["error_rate"] * 100
                                    for r in error_results
                                    if r["concurrency"] == c
                                    and r["payload_size_kb"] == p
                                ),
                                np.nan,
                            )
                            for c in sorted(concurrency_levels)
                        ]
                        for p in sorted(payload_sizes)
                    ]
                )

                if not np.all(np.isnan(Z_err)):
                    ax3d_err.plot_surface(
                        np.log2(X),
                        np.log2(Y),
                        Z_err,
                        cmap="cividis",
                        edgecolor="k",
                        linewidth=0.5,
                        alpha=0.9,
                    )
                    ax3d_err.set_xlabel("Concurrency (log2 scale)")
                    ax3d_err.set_ylabel("Payload Size (KB, log2 scale)")
                    ax3d_err.set_zlabel("Error Rate (%)")
                    ax3d_err.set_title(
                        f"3D Error Rate Surface (Log-Log-Linear)\nDB Size: {db_size} records"
                    )
                    ax3d_err.invert_xaxis()
                    ax3d_err.view_init(elev=20, azim=-65)
                    plt.savefig(os.path.join(output_dir, f"error_3d_db_{db_size}.png"))
                plt.close(fig3d_err)

    def _main_benchmark_logic(self, options):
        scales = {
            "small": {
                "db_sizes": np.logspace(
                    6, 10, num=2, base=2, dtype=int
                ).tolist(),  # 64, 1k
                "concurrency": np.logspace(
                    2, 4, num=3, base=2, dtype=int
                ).tolist(),  # 4, 8, 16
                "payloads_kb": np.logspace(
                    3, 9, num=3, base=2, dtype=int
                ).tolist(),  # 8k, 64k, 512k
                "requests": 32,
            },
            "large": {
                "db_sizes": np.logspace(
                    6, 18, num=4, base=2, dtype=int
                ).tolist(),  # 4 points from 64 to 256k
                "concurrency": np.logspace(
                    1, 6, num=8, base=2, dtype=int
                ).tolist(),  # 8 points from 2 to 64
                "payloads_kb": np.logspace(
                    1, 14, num=8, base=2, dtype=int
                ).tolist(),  # 8 points from 2KB to 16MB
                "requests": 64,
            },
        }

        config = scales[options["scale"]]
        db_sizes = config["db_sizes"]
        concurrency_levels = config["concurrency"]
        payload_sizes_kb = config["payloads_kb"]
        num_requests_per_test = (
            options["requests"]
            if options["requests"] is not None
            else config["requests"]
        )

        max_concurrency = max(concurrency_levels)
        if num_requests_per_test < max_concurrency:
            self.stdout.write(
                f"Warning: Requests ({num_requests_per_test}) < max concurrency ({max_concurrency}). Adjusting to {max_concurrency}."
            )
            num_requests_per_test = max_concurrency

        all_results = []
        self.stdout.write(
            self.style.SUCCESS(
                f"====== Starting Benchmark (Scale: {options['scale'].upper()}) ======"
            )
        )

        for db_size in db_sizes:
            self.stdout.write(f"\n--- Preparing for DB size: {db_size} records ---")
            for payload in payload_sizes_kb:
                for concurrency in concurrency_levels:
                    self._cleanup_test_data()
                    self._setup_test_data(db_size)

                    warmup_concurrency = min(concurrency_levels)
                    warmup_payload = min(payload_sizes_kb)
                    warmup_requests = max(16, warmup_concurrency)
                    self._run_test(
                        warmup_concurrency,
                        warmup_payload,
                        warmup_requests,
                        description="Warming up",
                        suppress_result_print=True,
                    )

                    response_time, failed_requests = self._run_test(
                        concurrency, payload, num_requests_per_test
                    )
                    if response_time is not None:
                        error_rate = (
                            failed_requests / num_requests_per_test
                            if failed_requests is not None
                            else 1.0
                        )
                        all_results.append(
                            {
                                "db_size": db_size,
                                "concurrency": concurrency,
                                "payload_size_kb": payload,
                                "avg_response_time_ms": response_time,
                                "failed_requests": failed_requests,
                                "error_rate": error_rate,
                            }
                        )
                    time.sleep(2)

            # Draw graphs for the completed db_size
            self._draw_graphs(
                all_results,
                [db_size],
                concurrency_levels,
                payload_sizes_kb,
                num_requests_per_test,
                options["output_dir"],
            )

        self._print_summary_table(
            all_results, db_sizes, concurrency_levels, payload_sizes_kb
        )

        self.stdout.write(self.style.SUCCESS("\n====== Benchmark Finished ======"))
        self._cleanup_test_data()

    def _print_summary_table(
        self, all_results, db_sizes, concurrency_levels, payload_sizes_kb
    ):
        def format_time(res):
            if res is None:
                return "N/A"
            time, failed = res.get("avg_response_time_ms"), res.get("failed_requests")
            if time < 0:
                return {-1.0: "TIMEOUT", -2.0: "ABORTED", -4.0: "UNEXPECTED"}.get(
                    time, "ERROR"
                )
            return f"{time:,.2f}{' *' if failed > 0 else ''}"

        self.stdout.write(
            self.style.SUCCESS("\n\n====== Benchmark Results Summary ======")
        )
        self.stdout.write("* next to a value indicates that some requests failed.")
        header = f"| {'DB Size':<10} | {'Payload(KB)':<12} |" + "".join(
            [f" C={c:<8} | Err Rate |" for c in concurrency_levels]
        )
        self.stdout.write(header)
        self.stdout.write(
            "|------------|--------------|"
            + "|".join(["-" * 20 for _ in concurrency_levels])
            + "|"
        )

        for db_size in db_sizes:
            for i, payload in enumerate(payload_sizes_kb):
                row = "| {db_size:<10} | {payload:<12} |".format(
                    db_size=db_size if i == 0 else "", payload=payload
                )
                for con in concurrency_levels:
                    res = next(
                        (
                            r
                            for r in all_results
                            if r["db_size"] == db_size
                            and r["payload_size_kb"] == payload
                            and r["concurrency"] == con
                        ),
                        None,
                    )
                    time_str = format_time(res)
                    err_str = (
                        f"{res['error_rate']:.1%}"
                        if res and res.get("error_rate") is not None
                        else "N/A"
                    )
                    row += f" {time_str:<8} | {err_str:<8} |"
                self.stdout.write(row)
            if db_size != db_sizes[-1]:
                self.stdout.write(
                    "|------------|--------------|"
                    + "|".join(["-" * 20 for _ in concurrency_levels])
                    + "|"
                )
