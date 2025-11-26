import subprocess
import re
import json
import argparse
import os
import time
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d import Axes3D

def run_test(concurrency, payload_size, num_requests=15):
    """
    Runs the pressure test and returns a tuple: (mean_response_time, failed_requests_count).
    Negative response times are error codes.
    """
    print(f"  - Testing: C={concurrency}, P={payload_size}KB...", end='', flush=True)
    command = [
        'python', 'Platform/manage.py', 'pressure_test',
        '-n', str(num_requests),
        '-c', str(concurrency),
        '--payload-size', str(payload_size)
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=600  # Increased timeout for larger scale
        )
        output = result.stdout
        failed_count = 0
        failed_match = re.search(r"Failed requests:\s+(\d+)", output)
        if failed_match:
            failed_count = int(failed_match.group(1))

        time_match = re.search(r"Time per request:\s+([\d.]+)\s+\[ms\] \(mean\)", output)
        if time_match:
            response_time = float(time_match.group(1))
            if failed_count > 0:
                print(f" PARTIAL FAIL ({failed_count}/{num_requests} failed), Avg Time: {response_time:.2f} ms")
            else:
                print(f" {response_time:.2f} ms")
            return response_time, failed_count
        else:
            print(" UNEXPECTED OUTPUT")
            return -4.0, num_requests

    except subprocess.TimeoutExpired:
        print(" TIMEOUT")
        return -1.0, num_requests
    except subprocess.CalledProcessError:
        print(" ABORTED")
        return -2.0, num_requests
    except Exception as e:
        print(f" FAILED (script error: {e})")
        return None, None

def setup_test_data(populate_count):
    """Creates the test user and populates the DB with dummy data."""
    print(f"\n--- Setting up DB with {populate_count} records ---")
    subprocess.run(['python', 'Platform/manage.py', 'pressure_test', '--user-only'], capture_output=True, text=True)
    populate_process = subprocess.run(['python', 'Platform/manage.py', 'pressure_test', '--populate', str(populate_count)])
    if populate_process.returncode != 0:
        print("Error: Failed to populate the database. Aborting.")
        exit(1)
    print("Setup complete.")

def cleanup_test_data():
    """Cleans up the test user and data."""
    print("\n--- Cleaning up all test data ---")
    subprocess.run(['python', 'Platform/manage.py', 'pressure_test', '--cleanup'])

def draw_graphs(all_results, db_sizes, concurrency_levels, payload_sizes, num_requests, output_dir=None):
    """Draws and saves insightful 2D and 3D graphs for performance and error rates."""
    print("\n\n====== Generating Visual Graphs ======")
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    plt.style.use('seaborn-v0_8-whitegrid')

    for db_size in db_sizes:
        print(f"\n--- Generating graphs for DB size: {db_size} records ---")
        
        db_results = [r for r in all_results if r['db_size'] == db_size]
        if not db_results:
            print(f"No data to plot for DB size {db_size}.")
            continue

        # Performance Graphs
        perf_results = [r for r in db_results if r.get('avg_response_time_ms', -1) > 0]
        if perf_results:
            # 2D Performance Curve
            fig2d_perf, ax2d_perf = plt.subplots(figsize=(12, 8))
            for payload in sorted(payload_sizes):
                xs = sorted(concurrency_levels)
                ys = [next((r['avg_response_time_ms'] for r in perf_results if r['concurrency'] == c and r['payload_size_kb'] == payload), np.nan) for c in xs]
                if not all(np.isnan(ys)):
                    ax2d_perf.plot(xs, ys, marker='o', linestyle='-', label=f'Payload {payload // 1024}MB')
            ax2d_perf.set_xlabel('Concurrency'); ax2d_perf.set_ylabel('Avg. Response Time (ms)'); ax2d_perf.set_title(f'Performance Profile\nDB Size: {db_size}'); ax2d_perf.legend()
            if output_dir: plt.savefig(os.path.join(output_dir, f'perf_2d_db_{db_size}.png'))
            plt.close(fig2d_perf)

            # 3D Performance Surface
            fig3d_perf = plt.figure(figsize=(14, 10)); ax3d_perf = fig3d_perf.add_subplot(111, projection='3d')
            X, Y = np.meshgrid(sorted(concurrency_levels), sorted(payload_sizes))
            Z = np.array([[next((r['avg_response_time_ms'] for r in perf_results if r['concurrency'] == c and r['payload_size_kb'] == p), np.nan) for c in sorted(concurrency_levels)] for p in sorted(payload_sizes)])
            if not np.all(np.isnan(Z)):
                ax3d_perf.plot_surface(X, Y / 1024, Z, cmap='viridis'); ax3d_perf.set_xlabel('Concurrency'); ax3d_perf.set_ylabel('Payload (MB)'); ax3d_perf.set_zlabel('Response Time (ms)'); ax3d_perf.set_title(f'3D Performance Surface\nDB Size: {db_size}')
                if output_dir: plt.savefig(os.path.join(output_dir, f'perf_3d_db_{db_size}.png'))
            plt.close(fig3d_perf)

        # Error Rate Graphs
        error_results = [r for r in db_results if 'error_rate' in r]
        if error_results:
            # 2D Error Rate Curve
            fig2d_err, ax2d_err = plt.subplots(figsize=(12, 8))
            for payload in sorted(payload_sizes):
                xs = sorted(concurrency_levels)
                ys = [next((r['error_rate'] * 100 for r in error_results if r['concurrency'] == c and r['payload_size_kb'] == payload), np.nan) for c in xs]
                if not all(np.isnan(ys)):
                    ax2d_err.plot(xs, ys, marker='x', linestyle='--', label=f'Payload {payload // 1024}MB')
            ax2d_err.set_xlabel('Concurrency'); ax2d_err.set_ylabel('Error Rate (%)'); ax2d_err.set_title(f'Error Rate Profile\nDB Size: {db_size}'); ax2d_err.legend()
            if output_dir: plt.savefig(os.path.join(output_dir, f'error_2d_db_{db_size}.png'))
            plt.close(fig2d_err)

            # 3D Error Rate Surface
            fig3d_err = plt.figure(figsize=(14, 10)); ax3d_err = fig3d_err.add_subplot(111, projection='3d')
            X, Y = np.meshgrid(sorted(concurrency_levels), sorted(payload_sizes))
            Z_err = np.array([[next((r['error_rate'] * 100 for r in error_results if r['concurrency'] == c and r['payload_size_kb'] == p), np.nan) for c in sorted(concurrency_levels)] for p in sorted(payload_sizes)])
            if not np.all(np.isnan(Z_err)):
                ax3d_err.plot_surface(X, Y / 1024, Z_err, cmap='plasma'); ax3d_err.set_xlabel('Concurrency'); ax3d_err.set_ylabel('Payload (MB)'); ax3d_err.set_zlabel('Error Rate (%)'); ax3d_err.set_title(f'3D Error Rate Surface\nDB Size: {db_size}')
                if output_dir: plt.savefig(os.path.join(output_dir, f'error_3d_db_{db_size}.png'))
            plt.close(fig3d_err)

def main():
    parser = argparse.ArgumentParser(description="Run server performance benchmarks.")
    parser.add_argument("--output-dir", type=str, default="benchmark_graphs", help="Directory to save graph output files.")
    parser.add_argument("--scale", type=str, choices=['small', 'large'], default='small', help="Scale of the benchmark to run.")
    parser.add_argument("--requests", type=int, help="Override the total number of requests for each test run.")
    args = parser.parse_args()

    scales = {
        'small': {
            "db_sizes": [2**13, 2**14, 2**15, 2**16],      # 8K to 65K
            "concurrency": [2**2, 2**3, 2**4, 2**5],          # 4 to 32
            "payloads_kb": [2**10, 2**11, 2**12, 2**13],        # 1k to 8k
            "requests": 64,
        },
        'large': {
            "db_sizes":    [2**13, 2**14, 2**15, 2**16, 2**17, 2**18], # 8k to 256k (6 points)
            "concurrency": [2**2, 2**3, 2**4, 2**5, 2**6, 2**7],      # 4 to 128 (6 points)
            "payloads_kb": [2**10, 2**11, 2**12, 2**13, 2**14, 2**15],# 1k to 32k (8 points)
            "requests":    128,
        }
    }
    
    config = scales[args.scale]
    db_sizes = config['db_sizes']
    concurrency_levels = config['concurrency']
    payload_sizes_kb = config['payloads_kb']
    
    # Override requests if provided, otherwise use the default from the scale
    num_requests_per_test = args.requests if args.requests is not None else config['requests']

    # Ensure requests are always greater than the max concurrency
    max_concurrency = max(concurrency_levels)
    if num_requests_per_test < max_concurrency:
        print(f"Warning: Number of requests ({num_requests_per_test}) is less than max concurrency ({max_concurrency}). Adjusting to {max_concurrency}.")
        num_requests_per_test = max_concurrency
    
    all_results = []

    print(f"====== Starting Benchmark (Scale: {args.scale.upper()}, Requests per run: {num_requests_per_test}) ======")
    
    for db_size in db_sizes:
        cleanup_test_data()
        setup_test_data(db_size)
        print(f"\n--- Running tests for DB size: {db_size} ---")
        for payload in payload_sizes_kb:
            for concurrency in concurrency_levels:
                response_time, failed_requests = run_test(concurrency, payload, num_requests_per_test)
                if response_time is not None:
                    error_rate = failed_requests / num_requests_per_test if failed_requests is not None else 1.0
                    all_results.append({
                        "db_size": db_size, "concurrency": concurrency,
                        "payload_size_kb": payload, "avg_response_time_ms": response_time,
                        "failed_requests": failed_requests, "error_rate": error_rate
                    })
                time.sleep(2)

    def format_time(res):
        if res is None: return "N/A"
        time, failed = res.get('avg_response_time_ms'), res.get('failed_requests')
        if time < 0: return { -1.0: "TIMEOUT", -2.0: "ABORTED", -4.0: "UNEXPECTED"}.get(time, "ERROR")
        return f"{time:,.2f}{' *' if failed > 0 else ''}"

    print("\n\n====== Benchmark Results Summary ======")
    print("* next to a value indicates that some requests failed.")
    header = f"| {'DB Size':<10} | {'Payload(KB)':<12} |" + "".join([f" C={c:<8} | Err Rate |" for c in concurrency_levels])
    print(header)
    print(f"|------------|--------------|" + "|".join(["-"*20 for _ in concurrency_levels]) + "|")

    for db_size in db_sizes:
        for i, payload in enumerate(payload_sizes_kb):
            row = f"| {db_size if i == 0 else '':<10} | {payload:<12} |"
            for con in concurrency_levels:
                res = next((r for r in all_results if r['db_size']==db_size and r['payload_size_kb']==payload and r['concurrency']==con), None)
                time_str = format_time(res)
                err_str = f"{res['error_rate']:.1%}" if res and res.get('error_rate') is not None else "N/A"
                row += f" {time_str:<8} | {err_str:<8} |"
            print(row)
        if db_size != db_sizes[-1]: print(f"|------------|--------------|" + "|".join(["-"*20 for _ in concurrency_levels]) + "|")

    draw_graphs(all_results, db_sizes, concurrency_levels, payload_sizes_kb, num_requests_per_test, args.output_dir)

    print("\n====== Benchmark Finished ======")
    cleanup_test_data()

if __name__ == "__main__":
    main()
