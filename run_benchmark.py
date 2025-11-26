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
            timeout=400
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
            print("\n----- UNEXPECTED AB OUTPUT START -----")
            print(output)
            print("----- UNEXPECTED AB OUTPUT END -----\n")
            return -4.0, num_requests

    except subprocess.TimeoutExpired:
        print(" TIMEOUT")
        return -1.0, num_requests
    except subprocess.CalledProcessError as e:
        print(" ABORTED")
        print("\n----- ABORTED RUN (STDOUT) -----")
        print(e.stdout)
        print("----- ABORTED RUN (STDERR) -----")
        print(e.stderr)
        print("----- END ABORTED RUN LOG -----\n")
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

def draw_graphs(all_results, db_sizes, concurrency_levels, payload_sizes, output_dir=None):
    """Draws and saves insightful 2D and 3D graphs from the benchmark results."""
    print("\n\n====== Generating Visual Graphs ======")
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    plt.style.use('seaborn-v0_8-whitegrid')

    for db_size in db_sizes:
        print(f"\n--- Generating graphs for DB size: {db_size} records ---")
        
        db_results = [r for r in all_results if r['db_size'] == db_size and r['avg_response_time_ms'] > 0]
        if not db_results:
            print(f"No valid data to plot for DB size {db_size}.")
            continue

        print("  - Generating 2D curve: Concurrency vs. Response Time")
        fig2d, ax2d = plt.subplots(figsize=(12, 8))
        
        for payload in sorted(payload_sizes):
            xs = sorted(concurrency_levels)
            ys = []
            for concurrency in xs:
                res = next((r['avg_response_time_ms'] for r in db_results if r['concurrency'] == concurrency and r['payload_size_kb'] == payload), None)
                ys.append(res if res is not None else np.nan)
            
            if not all(np.isnan(ys)):
                 ax2d.plot(xs, ys, marker='o', linestyle='-', label=f'Payload {payload // 1024}MB')

        ax2d.set_xlabel('Concurrency Level', fontsize=12)
        ax2d.set_ylabel('Average Response Time (ms)', fontsize=12)
        ax2d.set_title(f'Performance Profile\nDB Size: {db_size} records', fontsize=16)
        ax2d.legend(title='Payload Size')
        ax2d.grid(True, which='both', linestyle='--', linewidth=0.5)
        
        if output_dir:
            filename = os.path.join(output_dir, f'2d_concurrency_payload_curve_db_{db_size}.png')
            plt.savefig(filename, bbox_inches='tight')
            print(f"  - Chart saved to {filename}")
        plt.close(fig2d)

        print("  - Generating 3D surface plot")
        fig3d = plt.figure(figsize=(14, 10))
        ax3d = fig3d.add_subplot(111, projection='3d')

        x = np.array(sorted(list(set(r['concurrency'] for r in db_results))))
        y = np.array(sorted(list(set(r['payload_size_kb'] for r in db_results))))
        X, Y = np.meshgrid(x, y)
        
        Z = np.empty(X.shape)
        Z[:] = np.nan
        
        for i in range(len(y)):
            for j in range(len(x)):
                payload = y[i]
                concurrency = x[j]
                res = next((r['avg_response_time_ms'] for r in db_results if r['concurrency'] == concurrency and r['payload_size_kb'] == payload), None)
                if res is not None:
                    Z[i, j] = res

        if not np.all(np.isnan(Z)):
            ax3d.plot_surface(X, Y / 1024, Z, cmap='viridis', edgecolor='none')
            ax3d.set_xlabel('Concurrency', labelpad=10)
            ax3d.set_ylabel('Payload Size (MB)', labelpad=10)
            ax3d.set_zlabel('Response Time (ms)', labelpad=10)
            ax3d.set_title(f'3D Performance Surface\nDB Size: {db_size} records', fontsize=16)
            
            if output_dir:
                filename = os.path.join(output_dir, f'3d_performance_surface_db_{db_size}.png')
                plt.savefig(filename, bbox_inches='tight')
                print(f"  - Chart saved to {filename}")
        else:
            print("  - Could not generate 3D plot due to insufficient data grid.")
        plt.close(fig3d)

def main():
    parser = argparse.ArgumentParser(description="Run server performance benchmarks.")
    parser.add_argument("--output-dir", type=str, default="benchmark_graphs", help="Directory to save graph output files.")
    args = parser.parse_args()

    database_sizes = [10000, 50000, 100000]
    concurrency_levels = [5, 15, 30, 50]
    payload_sizes_kb = [1024, 5120, 10240, 20480]
    num_requests_per_test = 60

    all_results = []

    print("====== Starting Comprehensive Performance Benchmark ======")
    
    for db_size in database_sizes:
        cleanup_test_data()
        setup_test_data(db_size)
        print(f"\n--- Running tests for DB size: {db_size} ---")
        for payload in payload_sizes_kb:
            for concurrency in concurrency_levels:
                response_time, failed_requests = run_test(concurrency, payload, num_requests_per_test)
                if response_time is not None:
                    all_results.append({
                        "db_size": db_size, "concurrency": concurrency,
                        "payload_size_kb": payload, "avg_response_time_ms": response_time,
                        "failed_requests": failed_requests
                    })
                time.sleep(2)

    def format_time(ms_time, failed_requests):
        if ms_time is None: return "N/A"
        
        if ms_time < 0:
            return {
                -1.0: "**TIMEOUT**", -2.0: "**ABORTED**",
                -4.0: "**UNEXPECTED**"
            }.get(ms_time, "**ERROR**")

        time_str = f"{ms_time:,.2f}"
        if failed_requests > 0:
            time_str += " *" 
        return time_str

    print("\n\n====== Benchmark Results Summary Table ======")
    print("* next to a value indicates that some requests failed.")
    # Header
    header = f"| {'DB Size':<12} | {'Payload (KB)':<15} |" + "".join([f" C = {c:<10} |" for c in concurrency_levels])
    print(header)
    print(f"|--------------|-----------------|" + "|".join(["-"*14 for _ in concurrency_levels]) + "|")

    # Body
    for db_size in database_sizes:
        for i, payload in enumerate(payload_sizes_kb):
            db_str = str(db_size) if i == 0 else ""
            row = f"| {db_str:<12} | {payload:<15} |"
            for concurrency in concurrency_levels:
                res = next((r for r in all_results if r['db_size'] == db_size and r['concurrency'] == concurrency and r['payload_size_kb'] == payload), None)
                time_str = format_time(res['avg_response_time_ms'], res['failed_requests']) if res else "N/A"
                row += f" {time_str:<12} |"
            print(row)
        if db_size != database_sizes[-1]:
            print(f"|--------------|-----------------|" + "|".join(["-"*14 for _ in concurrency_levels]) + "|")

    draw_graphs(all_results, database_sizes, concurrency_levels, payload_sizes_kb, args.output_dir)

    print("\n====== Benchmark Finished ======")
    cleanup_test_data()

if __name__ == "__main__":
    main()
