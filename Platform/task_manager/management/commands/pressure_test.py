from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from task_manager.models import Task, TaskDataset, TaskDatasetEntry
from rest_framework_simplejwt.tokens import RefreshToken
import json
import zlib
import base64
import time
import random
import string
import subprocess
import os
import tempfile
from urllib.parse import quote_plus
import requests
import concurrent.futures


class Command(BaseCommand):
    help = "Runs an end-to-end pressure test on the /task/data endpoint."

    def add_arguments(self, parser):
        parser.add_argument(
            "--cleanup",
            action="store_true",
            help="Deletes the user and data created for the test.",
        )
        parser.add_argument(
            "--no-cleanup",
            action="store_true",
            help="Do not automatically clean up user and data after the test.",
        )
        parser.add_argument(
            "--user-only",
            action="store_true",
            help="Only creates the test user without running the test.",
        )
        parser.add_argument(
            "--populate",
            type=int,
            metavar="N",
            help="Populates the database with N dummy Webpage records for the test user.",
        )
        parser.add_argument(
            "-n",
            "--requests",
            type=int,
            default=100,
            help="Number of requests to perform for the test.",
        )
        parser.add_argument(
            "-c",
            "--concurrency",
            type=int,
            default=10,
            help="Number of multiple requests to make at a time.",
        )
        parser.add_argument(
            "--payload-size",
            type=int,
            default=1024,  # Default to 1MB
            help="The size of the rrweb_record payload in Kilobytes (KB).",
        )
        parser.add_argument(
            "--url",
            type=str,
            default="http://127.0.0.1:8000/task/data/",
            help="The target URL for the pressure test.",
        )
        parser.add_argument(
            "--token",
            type=str,
            help="Pre-generated JWT token to use for authentication (skips user creation).",
        )
        parser.add_argument(
            "--multi-user-file",
            type=str,
            help="Path to a JSON file containing a list of access tokens for concurrent user simulation.",
        )

    def _generate_pseudo_data(self, payload_size_kb):
        """Generates a dictionary of pseudo-data with a large rrweb_record."""
        random.seed(42)  # Seed for reproducibility
        start_time = time.time()
        dwell_time = random.randint(5000, 60000)  # 5 seconds to 1 minute
        end_time = start_time + (dwell_time / 1000)
        domain = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
        path = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        url = f"http://www.{domain}.com/{path}"
        referrer = "http://google.com"

        # 1. Generate a large rrweb_record
        event_payload = '{"type": 2, "timestamp": 1234567890, "data": {"text": "a sample event to pad the data"}}'
        event_size = len(event_payload.encode("utf-8"))
        target_size_bytes = payload_size_kb * 1024
        num_repetitions = max(1, int(target_size_bytes / (event_size + 1)))
        events = [event_payload] * num_repetitions
        rrweb_record_string = f"[{','.join(events)}]"

        # 2. Generate a realistic event_list
        event_list = []
        num_events = int(dwell_time / 1000)  # Roughly one event per second
        event_types = ["click", "scroll", "input", "focus", "blur"]
        for i in range(num_events):
            event_list.append(
                {
                    "is_active": True,
                    "type": random.choice(event_types),
                    "timestamp": int((start_time + (i * 1000)) * 1000),
                    "screenX": random.randint(0, 1920),
                    "screenY": random.randint(0, 1080),
                    "clientX": random.randint(0, 1920),
                    "clientY": random.randint(0, 1080),
                    "tag": "DIV",
                    "content": "Some content",
                    "hierachy": "BODY/DIV/DIV",
                    "related_info": {},
                }
            )

        # 3. Generate a realistic mouse_moves list
        mouse_moves = []
        num_mouse_moves = int(dwell_time / 50)  # A mouse move every 50ms
        for i in range(num_mouse_moves):
            mouse_moves.append(
                {
                    "x": random.randint(0, 1920),
                    "y": random.randint(0, 1080),
                    "time": int((start_time + (i * 50)) * 1000),
                    "type": "move",
                }
            )

        return {
            "url": url,
            "title": "Test Page - "
            + "".join(random.choices(string.ascii_uppercase + string.digits, k=6)),
            "referrer": referrer,
            "start_timestamp": int(start_time * 1000),
            "end_timestamp": int(end_time * 1000),
            "dwell_time": dwell_time,
            "rrweb_record": rrweb_record_string,
            "event_list": json.dumps(event_list),
            "mouse_moves": json.dumps(mouse_moves),
            "page_switch_record": "[]",
            "sent_when_active": random.choice([True, False]),
            "is_routine_update": False,
        }

    def handle(self, *args, **options):
        if options["multi_user_file"]:
            self.run_multi_user_test(options)
            return

        User = get_user_model()
        username = "pressure_test_user"
        password = "password"

        if options.get("cleanup"):
            self.cleanup(User, username)
            return

        if options["populate"]:
            self.populate_db(User, username, password, options["populate"])
            return

        if options["user_only"]:
            self.create_user(User, username, password)
            return

        self.setup_and_run_test(User, username, password, options)
        if not options["no_cleanup"] and not options.get("token"):
            self.cleanup(User, username)

    def create_user(self, User, username, password):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = User.objects.create_user(username=username, password=password)
            self.stdout.write(
                self.style.SUCCESS(f"Successfully created user: {username}")
            )
        return user

    def populate_db(self, User, username, password, count):
        from task_manager.models import Webpage
        from django.utils import timezone

        self.stdout.write(
            self.style.SUCCESS(f"Populating database with {count} records...")
        )
        user = self.create_user(User, username, password)
        dataset, _ = TaskDataset.objects.get_or_create(name="pressure_test_dataset")
        entry, _ = TaskDatasetEntry.objects.get_or_create(
            belong_dataset=dataset,
            question="Pressure Test",
            answer=json.dumps(["Done"]),
        )
        task, _ = Task.objects.update_or_create(
            user=user, active=True, defaults={"content": entry}
        )

        webpages_to_create = []
        for i in range(count):
            webpages_to_create.append(
                Webpage(
                    user=user,
                    belong_task=task,
                    url=f"http://example.com/page_{i}",
                    title=f"Populated Page {i}",
                    start_timestamp=timezone.now(),
                    end_timestamp=timezone.now(),
                    rrweb_record="[]",
                    event_list="[]",
                    mouse_moves="[]",
                    page_switch_record="[]",
                    dwell_time=0,
                    referrer="",
                )
            )

        Webpage.objects.bulk_create(webpages_to_create)
        self.stdout.write(
            self.style.SUCCESS(f"Successfully populated database for user {username}.")
        )

    def setup_and_run_test(self, User, username, password, options):
        if options.get("token"):
            access_token = options["token"]
        else:
            # 1. Setup User and Task
            user = self.create_user(User, username, password)
            dataset, _ = TaskDataset.objects.get_or_create(name="pressure_test_dataset")
            entry, _ = TaskDatasetEntry.objects.get_or_create(
                belong_dataset=dataset,
                question="Pressure Test",
                answer=json.dumps(["Done"]),
            )
            Task.objects.update_or_create(
                user=user, active=True, defaults={"content": entry}
            )

            # 2. Generate Token and Data
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

        sample_data = self._generate_pseudo_data(options["payload_size"])

        json_data_string = json.dumps(sample_data)
        compressed_data = zlib.compress(json_data_string.encode("utf-8"))
        base64_encoded_data = base64.b64encode(compressed_data).decode("utf-8")
        url_encoded_data = quote_plus(base64_encoded_data)

        # 3. Create a temporary file for the POST data
        tmpfile = tempfile.NamedTemporaryFile(mode="w+", delete=False)
        try:
            tmpfile.write(f"message={url_encoded_data}")
            tmpfile.close()  # Close the file so 'ab' can access it on all OSes

            # 4. Run the pressure test
            self.stdout.write(self.style.SUCCESS("=" * 50))
            self.stdout.write(
                f"Running End-to-End Pressure Test with {options['payload_size']}KB payload..."
            )
            self.stdout.write(f"Target URL: {options['url']}")
            self.stdout.write(self.style.SUCCESS("=" * 50))

            num_requests = options["requests"]
            concurrency = options["concurrency"]
            command = [
                "ab",
                "-n",
                str(num_requests),
                "-c",
                str(concurrency),
                "-p",
                tmpfile.name,  # Use the temporary file's name
                "-T",
                "application/x-www-form-urlencoded",
                "-H",
                f"Authorization: Bearer {access_token}",
                options["url"],
            ]

            try:
                result = subprocess.run(
                    command, capture_output=True, text=True, check=True, timeout=600
                )
                self.stdout.write(result.stdout)
                if result.stderr:
                    self.stdout.write(self.style.WARNING("Logs from ab:"))
                    self.stdout.write(result.stderr)
                self.stdout.write(
                    self.style.SUCCESS("Pressure test completed successfully.")
                )
            except FileNotFoundError:
                self.stdout.write(
                    self.style.ERROR(
                        "Error: 'ab' command not found. Please install Apache Bench."
                    )
                )
            except subprocess.CalledProcessError as e:
                self.stdout.write(self.style.ERROR(f"Error executing 'ab': {e}"))
                self.stdout.write(e.stdout)
                self.stdout.write(e.stderr)
        finally:
            os.remove(tmpfile.name)  # Manually clean up the temporary file

        self.stdout.write(self.style.SUCCESS("=" * 50))

    def cleanup(self, User, username):
        try:
            user = User.objects.get(username=username)
            # Explicitly delete all related data to be absolutely certain
            from task_manager.models import Webpage, Task

            Webpage.objects.filter(user=user).delete()
            Task.objects.filter(user=user).delete()

            # This will cascade delete related tasks, webpages, etc.
            user.delete()

            # Also clean up the dataset if it exists
            dataset = TaskDataset.objects.filter(name="pressure_test_dataset")
            if dataset.exists():
                TaskDatasetEntry.objects.filter(belong_dataset=dataset.first()).delete()
                dataset.delete()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully and explicitly cleaned up user and all related data for {username}"
                )
            )
        except User.DoesNotExist:
            self.stdout.write(
                self.style.WARNING(f"User {username} not found, nothing to clean up.")
            )

    def run_multi_user_test(self, options):
        token_file = options["multi_user_file"]
        url = options["url"]
        requests_per_user = options["requests"]
        
        # We ignore 'concurrency' option here because concurrency is determined by the number of tokens/users
        # provided in the file, assuming we want to simulate ALL of them active at once.
        # However, we can use a ThreadPoolExecutor to limit actual thread concurrency if needed,
        # but the goal is typically to simulate N users.
        
        try:
            with open(token_file, 'r') as f:
                tokens = json.load(f)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to read token file: {e}"))
            return

        num_users = len(tokens)
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write(f"Starting Multi-User Pressure Test")
        self.stdout.write(f"Target URL: {url}")
        self.stdout.write(f"Users (Tokens): {num_users}")
        self.stdout.write(f"Requests per user: {requests_per_user}")
        self.stdout.write(f"Total Requests: {num_users * requests_per_user}")
        self.stdout.write(self.style.SUCCESS("=" * 50))

        # Generate payload once
        sample_data = self._generate_pseudo_data(options["payload_size"])
        json_data_string = json.dumps(sample_data)
        compressed_data = zlib.compress(json_data_string.encode("utf-8"))
        base64_encoded_data = base64.b64encode(compressed_data).decode("utf-8")
        # requests library handles url encoding, so we send the raw base64 in the dict if using data=...
        # But our API expects 'message=...' form encoded.
        payload = {"message": base64_encoded_data}

        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_users) as executor:
            futures = [
                executor.submit(self._single_user_worker, token, url, payload, requests_per_user)
                for token in tokens
            ]
            
            results = []
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

        total_time = time.time() - start_time
        
        # Aggregate Results
        total_requests = sum(r['success'] + r['fail'] for r in results)
        total_failed = sum(r['fail'] for r in results)
        avg_latency = sum(r['avg_latency'] for r in results) / len(results) if results else 0
        
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 50))
        self.stdout.write("Test Completed.")
        self.stdout.write(f"Total Time: {total_time:.2f}s")
        self.stdout.write(f"Total Requests: {total_requests}")
        self.stdout.write(f"Failed Requests: {total_failed}")
        self.stdout.write(f"Avg Latency per User-Session: {avg_latency:.2f}s (Total time for N requests)")
        self.stdout.write(f"Throughput: {total_requests / total_time:.2f} req/s")
        self.stdout.write(self.style.SUCCESS("=" * 50))

    def _single_user_worker(self, token, url, payload, num_requests):
        headers = {"Authorization": f"Bearer {token}"}
        success = 0
        fail = 0
        start = time.time()
        
        for _ in range(num_requests):
            try:
                # Using a session for keep-alive if desired, or plain requests
                resp = requests.post(url, data=payload, headers=headers)
                if resp.status_code == 200:
                    success += 1
                else:
                    fail += 1
            except Exception:
                fail += 1
        
        duration = time.time() - start
        return {
            "success": success,
            "fail": fail,
            "avg_latency": duration # Total duration for this user's batch
        }
