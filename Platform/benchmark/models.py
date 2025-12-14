from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
import os

# --- Abstract Base Classes ---

class SingletonModel(models.Model):
    """
    Abstract base class for singleton models.
    Ensures only one instance exists.
    """
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.pk and self.__class__.objects.exists():
            raise ValidationError(f"There can be only one {self.__class__.__name__} instance.")
        return super(SingletonModel, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

# --- Concrete Models ---

class BenchmarkDataset(models.Model):
    """
    Represents a dataset of questions for benchmarking.
    Expected format: JSONL where each line is a JSON object with 'question' and 'ground_truths' (or 'answer') keys.
    """
    name = models.CharField(max_length=255, unique=True, help_text="A unique name for this dataset.")
    description = models.TextField(blank=True, help_text="Optional description of the dataset.")
    file = models.FileField(upload_to='benchmark_datasets/', help_text="The JSONL file containing the questions.")
    question_count = models.IntegerField(default=0, help_text="Number of questions in the dataset.")
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

class SearchSettings(SingletonModel):
    """
    A singleton model to store Search-specific settings.
    """
    PROVIDER_CHOICES = [
        ('mcp', 'MCP Server'),
        ('serper', 'Serper API'),
    ]
    search_provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='serper', help_text="Select the search provider.")
    serper_api_key = models.CharField(max_length=255, blank=True, help_text="API Key for Serper.dev")
    search_limit = models.IntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(10)], help_text="Number of search results to retrieve (Top-K).")
    fetch_full_content = models.BooleanField(default=True, help_text="If enabled, fetches full page content for search results (Serper & MCP).")

    def __str__(self):
        return "Search Settings"

class LLMSettings(SingletonModel):
    """
    A singleton model to store LLM settings for the benchmark tool.
    This allows users to persist their LLM configuration in the database.
    """
    llm_base_url = models.CharField(max_length=255, blank=True, help_text="Optional: e.g., http://localhost:11434/v1")
    llm_model = models.CharField(max_length=100, blank=True, help_text="e.g., gpt-4o")
    llm_api_key = models.CharField(max_length=255, blank=True, help_text="Your API Key")
    max_retries = models.PositiveIntegerField(default=3, help_text="Maximum number of retries allowed for the LLM.")
    allow_reasoning = models.BooleanField(default=False, help_text="Allow the LLM to output its chain of thought reasoning before the final answer.")
    
    # Advanced Parameters
    temperature = models.FloatField(default=0.0, help_text="Sampling temperature (0.0 to 2.0).")
    top_p = models.FloatField(default=1.0, help_text="Nucleus sampling probability (0.0 to 1.0).")
    max_tokens = models.PositiveIntegerField(null=True, blank=True, help_text="Maximum number of tokens to generate.")

    def __str__(self):
        return "LLM Settings"

class RagSettings(SingletonModel):
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

    def __str__(self):
        return "RAG Settings"

class MultiTurnRun(models.Model):
    """
    Represents a group of benchmark sessions, typically from a single pipeline run.
    """
    name = models.CharField(max_length=255, default='Pipeline Run')
    created_at = models.DateTimeField(auto_now_add=True)
    settings_snapshot = models.JSONField(default=dict, blank=True, help_text="Snapshot of settings used for this run.")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"MultiTurn Run from {self.created_at.strftime('%Y-%m-%d %H:%M')}"

class MultiTurnSession(models.Model):
    """
    Represents a multi-turn conversation session.
    Unified model for both Vanilla LLM and RAG.
    """
    PIPELINE_TYPE_CHOICES = [
        ('vanilla', 'Vanilla LLM'),
        ('rag', 'RAG'),
    ]
    REFORMULATION_CHOICES = [
        ('no_reform', 'No Reformulation'),
        ('reform', 'Reformulation'),
    ]

    run = models.ForeignKey(MultiTurnRun, related_name='sessions', on_delete=models.CASCADE)
    question = models.TextField()
    ground_truths = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    is_completed = models.BooleanField(default=False)
    run_tag = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    
    pipeline_type = models.CharField(max_length=20, choices=PIPELINE_TYPE_CHOICES, default='vanilla')
    reformulation_strategy = models.CharField(max_length=20, choices=REFORMULATION_CHOICES, default='no_reform', help_text="Only used if pipeline_type is 'rag'")

    def __str__(self):
        return f"Session ({self.pipeline_type}) for: {self.question[:50]}..."

class MultiTurnTrial(models.Model):
    """
    Represents a single trial (turn) within a benchmark session.
    Unified model for both Vanilla LLM and RAG.
    """
    STATUS_CHOICES = [
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('error', 'Error'),
    ]
    session = models.ForeignKey(MultiTurnSession, related_name='trials', on_delete=models.CASCADE)
    trial_number = models.PositiveIntegerField()
    answer = models.TextField(blank=True, null=True)
    full_response = models.TextField(blank=True, null=True) # Full CoT
    feedback = models.TextField(blank=True, null=True)
    is_correct = models.BooleanField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processing')
    
    # RAG specific fields (nullable)
    search_query = models.TextField(blank=True, null=True)
    search_results = models.JSONField(default=list, blank=True, null=True)

    class Meta:
        unique_together = ('session', 'trial_number')
        ordering = ['trial_number']

    def __str__(self):
        return f"Trial {self.trial_number} for Session {self.session.id}"

class AdhocRun(models.Model):
    """
    Represents a single, complete run of an ad-hoc QA pipeline.
    Unified model for both Vanilla LLM and RAG.
    """
    RUN_TYPE_CHOICES = [
        ('vanilla', 'Vanilla LLM'),
        ('rag', 'RAG'),
    ]
    name = models.CharField(max_length=255, unique=True, help_text="A unique name for this benchmark run.")
    created_at = models.DateTimeField(auto_now_add=True)
    settings_snapshot = models.JSONField(default=dict, blank=True, help_text="Snapshot of settings used for this run.")
    
    run_type = models.CharField(max_length=20, choices=RUN_TYPE_CHOICES, default='vanilla')

    # Aggregate statistics
    total_questions = models.IntegerField(default=0)
    correct_answers = models.IntegerField(default=0)
    accuracy = models.FloatField(default=0.0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.run_type})"

class AdhocResult(models.Model):
    """
    Stores the result of a single question-answer session within a AdhocRun.
    Unified model for both Vanilla LLM and RAG.
    """
    run = models.ForeignKey(AdhocRun, related_name='results', on_delete=models.CASCADE)
    question = models.TextField()
    ground_truths = models.JSONField(default=list)
    answer = models.TextField() # Parsed Answer
    full_response = models.TextField(blank=True, null=True) # Full CoT
    is_correct_rule = models.BooleanField(default=False)
    is_correct_llm = models.BooleanField(null=True, default=None) # Allow null for errors/uncertainty
    
    # RAG specific fields
    num_docs_used = models.IntegerField(default=0)
    search_results = models.JSONField(default=list, blank=True, null=True)

    def __str__(self):
        return f"Result for '{self.question[:50]}...' in run {self.run.name}"
