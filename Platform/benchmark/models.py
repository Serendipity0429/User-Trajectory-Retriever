from django.db import models
from django.core.exceptions import ValidationError
import os

class BenchmarkDataset(models.Model):
    """
    Represents a dataset of questions for benchmarking.
    Expected format: JSONL where each line is a JSON object with 'question' and 'ground_truths' (or 'answer') keys.
    """
    name = models.CharField(max_length=255, unique=True, help_text="A unique name for this dataset.")
    description = models.TextField(blank=True, help_text="Optional description of the dataset.")
    file = models.FileField(upload_to='benchmark_datasets/', help_text="The JSONL file containing the questions.")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=False, help_text="Set this dataset as the default/active one.")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # If this object is set to be active, deactivate all others
        if self.is_active:
            BenchmarkDataset.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        return super(BenchmarkDataset, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Clean up the file from the filesystem when the object is deleted
        if self.file:
            if os.path.isfile(self.file.path):
                os.remove(self.file.path)
        super(BenchmarkDataset, self).delete(*args, **kwargs)

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

class MultiTurnSessionGroup(models.Model):
    """
    Represents a group of benchmark sessions, typically from a single pipeline run.
    """
    name = models.CharField(max_length=255, default='Pipeline Run')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Session Group from {self.created_at.strftime('%Y-%m-%d %H:%M')}"

class VanillaLLMMultiTurnSession(models.Model):
    """
    Represents a multi-turn conversation session for a Vanilla LLM.
    """
    llm_settings = models.ForeignKey(LLMSettings, on_delete=models.CASCADE)
    group = models.ForeignKey(MultiTurnSessionGroup, related_name='vanilla_sessions', on_delete=models.CASCADE, null=True, blank=True)
    question = models.TextField()
    ground_truths = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    is_completed = models.BooleanField(default=False)
    run_tag = models.CharField(max_length=255, blank=True, null=True, db_index=True)

    def __str__(self):
        return f"Vanilla LLM Session for: {self.question[:50]}..."

class VanillaLLMMultiTurnTrial(models.Model):
    """
    Represents a single trial (turn) within a Vanilla LLM session.
    """
    STATUS_CHOICES = [
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('error', 'Error'),
    ]
    session = models.ForeignKey(VanillaLLMMultiTurnSession, related_name='trials', on_delete=models.CASCADE)
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
        return f"Trial {self.trial_number} for Vanilla LLM Session {self.session.id}"

class RAGMultiTurnSession(models.Model):
    """
    Represents a multi-turn conversation session for a RAG pipeline.
    """
    llm_settings = models.ForeignKey(LLMSettings, on_delete=models.CASCADE)
    rag_settings = models.ForeignKey('RagSettings', on_delete=models.SET_NULL, null=True, blank=True)
    group = models.ForeignKey(MultiTurnSessionGroup, related_name='rag_sessions', on_delete=models.CASCADE, null=True, blank=True)
    question = models.TextField()
    ground_truths = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    is_completed = models.BooleanField(default=False)
    run_tag = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    
    REFORMULATION_CHOICES = [
        ('no_reform', 'No Reformulation'),
        ('reform', 'Reformulation'),
    ]
    reformulation_strategy = models.CharField(max_length=20, choices=REFORMULATION_CHOICES, default='no_reform')

    def __str__(self):
        return f"RAG Session for: {self.question[:50]}... ({self.reformulation_strategy})"

class RAGMultiTurnTrial(models.Model):
    """
    Represents a single trial (turn) within a RAG session.
    """
    STATUS_CHOICES = [
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('error', 'Error'),
    ]
    session = models.ForeignKey(RAGMultiTurnSession, related_name='trials', on_delete=models.CASCADE)
    trial_number = models.PositiveIntegerField()
    answer = models.TextField(blank=True, null=True)
    feedback = models.TextField(blank=True, null=True)
    is_correct = models.BooleanField(null=True, blank=True) # Can be null if not yet evaluated
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processing')
    search_query = models.TextField(blank=True, null=True)
    search_results = models.JSONField(default=list, blank=True)

    class Meta:
        unique_together = ('session', 'trial_number')
        ordering = ['trial_number']

    def __str__(self):
        return f"Trial {self.trial_number} for RAG Session {self.session.id}"


class VanillaLLMAdhocRun(models.Model):
    """
    Represents a single, complete run of the ad-hoc QA pipeline.
    """
    name = models.CharField(max_length=255, unique=True, help_text="A unique name for this benchmark run, e.g., 'gpt-4o-2025-12-02'")
    created_at = models.DateTimeField(auto_now_add=True)
    llm_settings = models.ForeignKey(LLMSettings, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Aggregate statistics
    total_questions = models.IntegerField(default=0)
    correct_answers = models.IntegerField(default=0)
    accuracy = models.FloatField(default=0.0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

class VanillaLLMAdhocResult(models.Model):
    """
    Stores the result of a single question-answer session within an VanillaLLMAdhocRun.
    """
    run = models.ForeignKey(VanillaLLMAdhocRun, related_name='results', on_delete=models.CASCADE)
    question = models.TextField()
    ground_truths = models.JSONField(default=list)
    answer = models.TextField()
    is_correct_rule = models.BooleanField(default=False)
    is_correct_llm = models.BooleanField(default=False)

    def __str__(self):
        return f"Result for '{self.question[:50]}...' in run {self.run.name}"

class RagSettings(models.Model):
    """
    A singleton model to store RAG-specific settings.
    """
    prompt_template = models.TextField(
        default="""Your task is to answer the following question based on the provided search results. Follow these rules strictly:
1. Your answer must be an exact match to the correct answer found in the search results.
2. Do not include any punctuation.
3. Do not include any extra words or sentences.

For example:
Question: What is the capital of France?
Correct Answer: Paris

Incorrect Answers:
- "The capital of France is Paris." (contains extra words)
- "Paris is the capital of France." (contains extra words)
- "Paris." (contains a period)

Now, answer the following question based on the provided search results:
Question: {question}

Search Results:
{search_results}

Answer:""",
        help_text="Template for the RAG prompt. Use {question} and {search_results} placeholders."
    )

    def save(self, *args, **kwargs):
        if not self.pk and RagSettings.objects.exists():
            raise ValidationError("There can be only one RagSettings instance.")
        return super(RagSettings, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "RAG Settings"

class RagAdhocRun(models.Model):
    """
    Represents a single, complete run of the RAG QA pipeline.
    """
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    llm_settings = models.ForeignKey(LLMSettings, on_delete=models.SET_NULL, null=True, blank=True)
    rag_settings = models.ForeignKey(RagSettings, on_delete=models.SET_NULL, null=True, blank=True)

    # Aggregate statistics
    total_questions = models.IntegerField(default=0)
    correct_answers = models.IntegerField(default=0)
    accuracy = models.FloatField(default=0.0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

class RagAdhocResult(models.Model):
    """
    Stores the result of a single question-answer session within a RagAdhocRun.
    """
    run = models.ForeignKey(RagAdhocRun, related_name='results', on_delete=models.CASCADE)
    question = models.TextField()
    ground_truths = models.JSONField(default=list)
    answer = models.TextField()
    is_correct_rule = models.BooleanField(default=False)
    is_correct_llm = models.BooleanField(null=True, default=None) # Allow null for errors/uncertainty
    num_docs_used = models.IntegerField(default=0)
    search_results = models.JSONField(default=list)

    def __str__(self):
        return f"RAG Result for '{self.question[:50]}...' in run {self.run.name}"

class SearchSettings(models.Model):
    """
    A singleton model to store Search-specific settings.
    """
    PROVIDER_CHOICES = [
        ('mcp', 'MCP Server'),
        ('serper', 'Serper API'),
    ]
    search_provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='mcp', help_text="Select the search provider.")
    serper_api_key = models.CharField(max_length=255, blank=True, help_text="API Key for Serper.dev")

    def save(self, *args, **kwargs):
        if not self.pk and SearchSettings.objects.exists():
            raise ValidationError("There can be only one SearchSettings instance.")
        return super(SearchSettings, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Search Settings"