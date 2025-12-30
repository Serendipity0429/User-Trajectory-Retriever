import csv
import datetime
import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from django.core.management.base import BaseCommand
from django.db.models import Sum
from user_system.models import User
from task_manager.models import Task, TaskDataset

class Command(BaseCommand):
    help = "Calculates and plots the total effort time for each user who finished all 58 formal tasks, excluding outliers (>2h)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--save-csv',
            type=str,
            help='Save the statistics to a CSV file.',
            default='tempFiles/total_formal_task_time.csv',
        )
        parser.add_argument(
            '--save-plot',
            type=str,
            help='Save the distribution plot to a file.',
            default='tempFiles/total_formal_task_time_dist.png',
        )

    def handle(self, *args, **options):
        # 1. Identify the Formal Dataset
        try:
            dataset = TaskDataset.objects.get(name='nq_hard_questions')
        except TaskDataset.DoesNotExist:
            self.stdout.write(self.style.ERROR("Dataset 'nq_hard_questions' not found."))
            return

        # Get all 58 formal entry IDs
        formal_entry_ids = set(dataset.taskdatasetentry_set.values_list('id', flat=True))
        formal_count = len(formal_entry_ids)
        self.stdout.write(f"Found dataset '{dataset.name}' with {formal_count} entries.")

        if formal_count != 58:
            self.stdout.write(self.style.WARNING(f"Expected 58 tasks, found {formal_count}. Proceeding anyway."))

        valid_user_data = []

        # 2. Iterate through all users
        users = User.objects.all()
        for user in users:
            # Filter for finished tasks (active=False) belonging to the formal dataset
            user_tasks = Task.objects.filter(
                user=user,
                content__belong_dataset=dataset,
                active=False
            )

            # Check if user has covered all formal entries
            # We use a set of content_ids to verify coverage
            completed_content_ids = set(user_tasks.values_list('content_id', flat=True))

            if formal_entry_ids.issubset(completed_content_ids):
                # User has finished all formal tasks
                user_total_seconds = 0
                outlier_count = 0
                
                # Iterate through each specific formal entry to sum time
                # Using the entry IDs ensures we count exactly 58 tasks (handling potential duplicates by taking the latest)
                for entry_id in formal_entry_ids:
                    # Get the specific task for this entry
                    # If multiple exist, we take the most recently finished one
                    task = user_tasks.filter(content_id=entry_id).order_by('-end_timestamp').first()
                    
                    if task and task.start_timestamp and task.end_timestamp:
                        duration = (task.end_timestamp - task.start_timestamp).total_seconds()
                        
                        # 3. Handle Outliers: If single task > 2 hours (7200s), remove from statistics
                        if duration > 7200:
                            outlier_count += 1
                            continue # Skip adding this duration
                        
                        user_total_seconds += duration
                
                # Convert to minutes or hours for easier reading?
                # User asked for "total task time statistics". Let's store seconds and convert later.
                valid_user_data.append({
                    'username': user.username,
                    'total_seconds': user_total_seconds,
                    'total_hours': user_total_seconds / 3600.0,
                    'outliers_excluded': outlier_count
                })

        self.stdout.write(f"Found {len(valid_user_data)} users who completed all {formal_count} tasks.")

        if not valid_user_data:
            self.stdout.write(self.style.WARNING("No users found who completed all tasks."))
            return

        # 4. Statistics and Output
        df = pd.DataFrame(valid_user_data)
        
        print("\n--- Statistics (Total Time per User) ---")
        print(df['total_hours'].describe())
        
        # Save to CSV
        csv_path = options['save_csv']
        df.to_csv(csv_path, index=False)
        self.stdout.write(self.style.SUCCESS(f"Saved statistics to {csv_path}"))

        # 5. Plotting
        plot_path = options['save_plot']
        plt.figure(figsize=(10, 6))
        
        # Histogram
        plt.hist(df['total_hours'], bins=15, color='skyblue', edgecolor='black', alpha=0.7)
        plt.title(f'Distribution of Total Task Time per User (N={len(df)})')
        plt.xlabel('Total Time (Hours)')
        plt.ylabel('Number of Users')
        plt.grid(axis='y', alpha=0.5)
        
        # Add mean and median lines
        mean_val = df['total_hours'].mean()
        median_val = df['total_hours'].median()
        plt.axvline(mean_val, color='red', linestyle='dashed', linewidth=1, label=f'Mean: {mean_val:.2f}h')
        plt.axvline(median_val, color='green', linestyle='dashed', linewidth=1, label=f'Median: {median_val:.2f}h')
        plt.legend()

        plt.savefig(plot_path)
        plt.close()
        self.stdout.write(self.style.SUCCESS(f"Saved plot to {plot_path}"))