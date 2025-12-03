from django.db import models
from django.core.exceptions import ValidationError

class LLMSettings(models.Model):
    """
    A singleton model to store LLM settings for the benchmark tool.
    This allows users to persist their LLM configuration in the database.
    """
    llm_base_url = models.CharField(max_length=255, blank=True, help_text="Optional: e.g., http://localhost:11434/v1")
    llm_model = models.CharField(max_length=100, blank=True, help_text="e.g., gpt-4o")
    llm_api_key = models.CharField(max_length=255, blank=True, help_text="Your API Key")
    max_retries = models.PositiveIntegerField(default=3, help_text="Maximum number of retries allowed for the LLM.")

    def save(self, *args, **kwargs):
        if not self.pk and LLMSettings.objects.exists():
            raise ValidationError("There can be only one LLMSettings instance.")
        return super(LLMSettings, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        """
        Load the singleton instance of the settings, creating it if it doesn't exist.
        """
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "LLM Settings"

class InteractiveSessionGroup(models.Model):
    """
    Represents a group of benchmark sessions, typically from a single pipeline run.
    """
    name = models.CharField(max_length=255, default='Pipeline Run')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Session Group from {self.created_at.strftime('%Y-%m-%d %H:%M')}"

class InteractiveSession(models.Model):
    """
    Represents a multi-turn conversation session for benchmarking.
    """
    settings = models.ForeignKey(LLMSettings, on_delete=models.CASCADE)
    group = models.ForeignKey(InteractiveSessionGroup, related_name='sessions', on_delete=models.CASCADE, null=True, blank=True)
    question = models.TextField()
    ground_truths = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    is_completed = models.BooleanField(default=False)
    run_tag = models.CharField(max_length=255, blank=True, null=True, db_index=True)

    def __str__(self):
        return f"Session for: {self.question[:50]}..."

class InteractiveTrial(models.Model):
    """
    Represents a single trial (turn) within a benchmark session.
    """
    STATUS_CHOICES = [
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('error', 'Error'),
    ]
    session = models.ForeignKey(InteractiveSession, related_name='trials', on_delete=models.CASCADE)
    trial_number = models.PositiveIntegerField()
    answer = models.TextField(blank=True, null=True)
    feedback = models.TextField(blank=True, null=True)
    is_correct = models.BooleanField(null=True, blank=True) # Can be null if not yet evaluated
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processing')

    class Meta:
        unique_together = ('session', 'trial_number')
        ordering = ['trial_number']

    def __str__(self):
        return f"Trial {self.trial_number} for Session {self.session.id}"


class AdhocRun(models.Model):
    """
    Represents a single, complete run of the ad-hoc QA pipeline.
    """
    name = models.CharField(max_length=255, unique=True, help_text="A unique name for this benchmark run, e.g., 'gpt-4o-2025-12-02'")
    created_at = models.DateTimeField(auto_now_add=True)
    settings = models.ForeignKey(LLMSettings, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Aggregate statistics
    total_questions = models.IntegerField(default=0)
    correct_answers = models.IntegerField(default=0)
    accuracy = models.FloatField(default=0.0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

class AdhocSessionResult(models.Model):
    """
    Stores the result of a single question-answer session within an AdhocRun.
    """
    run = models.ForeignKey(AdhocRun, related_name='results', on_delete=models.CASCADE)
    question = models.TextField()
    ground_truths = models.JSONField(default=list)
    answer = models.TextField()
    is_correct_rule = models.BooleanField(default=False)
    is_correct_llm = models.BooleanField(default=False)

    def __str__(self):
        return f"Result for '{self.question[:50]}...' in run {self.run.name}"
