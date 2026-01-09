from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import os
from decouple import config

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

class BenchmarkSettings(models.Model):
    """
    Unified settings model for LLM, Search, and Agent configurations.
    """
    is_template = models.BooleanField(default=False, help_text="If True, this is a global configuration template.")

    # LLM Settings
    llm_base_url = models.CharField(max_length=255, blank=True, help_text="Optional: e.g., http://localhost:11434/v1")
    llm_model = models.CharField(max_length=100, blank=True, help_text="e.g., gpt-4o")
    llm_api_key = models.CharField(max_length=255, blank=True, help_text="Your API Key")
    max_retries = models.PositiveIntegerField(default=5, help_text="Maximum number of retries allowed for the LLM.")
    allow_reasoning = models.BooleanField(default=True, help_text="Allow the LLM to output its chain of thought reasoning before the final answer.")

    # LLM Judge Settings (for LLM-as-a-judge evaluation)
    llm_judge_model = models.CharField(max_length=100, blank=True, help_text="Model for LLM-as-a-judge. If empty, uses LLM_JUDGE_MODEL env or falls back to llm_model.")

    # Embedding Model Settings (for long-term memory)
    embedding_model = models.CharField(max_length=100, blank=True, help_text="Embedding model for long-term memory. If empty, uses EMBEDDING_MODEL env or defaults to text-embedding-3-small.")
    
    # LLM Advanced Parameters
    temperature = models.FloatField(default=0.0, help_text="Sampling temperature (0.0 to 2.0).")
    top_p = models.FloatField(default=1.0, help_text="Nucleus sampling probability (0.0 to 1.0).")
    max_tokens = models.PositiveIntegerField(null=True, blank=True, help_text="Maximum number of tokens to generate.")

    # Search Settings
    PROVIDER_CHOICES = [
        ('mcp', 'MCP Server'),
        ('serper', 'Serper API'),
    ]
    search_provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='serper', help_text="Select the search provider.")
    serper_api_key = models.CharField(max_length=255, blank=True, help_text="API Key for Serper.dev")
    search_limit = models.IntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(10)], help_text="Number of search results to retrieve (Top-K).")
    fetch_full_content = models.BooleanField(default=True, help_text="If enabled, fetches full page content for search results (Serper & MCP).")

    # Agent Settings
    MEMORY_TYPE_CHOICES = [
        ('naive', 'Naive Memory'),
        ('mem0', 'Mem0 Memory'),
        ('reme', 'ReMe Memory'),
    ]
    memory_type = models.CharField(max_length=50, choices=MEMORY_TYPE_CHOICES, default='naive', help_text="Select the long-term memory mechanism.")

    def __str__(self):
        return f"Benchmark Settings ({'Template' if self.is_template else 'Run Instance'}) - {self.pk}"

    @classmethod
    def load(cls):
        # Prefer the template, or create one if none exists
        obj = cls.objects.filter(is_template=True).first()
        if not obj:
            # Create a new template without specifying pk to let PostgreSQL generate it
            obj = cls.objects.create(is_template=True)
        return obj

    @classmethod
    def get_effective_settings(cls):
        settings = cls.load()
        if not settings.llm_api_key:
            settings.llm_api_key = config("LLM_API_KEY", default="")
        if not settings.llm_model:
            settings.llm_model = config("LLM_MODEL", default="")
        if not settings.llm_base_url:
            settings.llm_base_url = config("LLM_BASE_URL", default="")
        if not settings.llm_judge_model:
            settings.llm_judge_model = config("LLM_JUDGE_MODEL", default="")
        if not settings.embedding_model:
            settings.embedding_model = config("EMBEDDING_MODEL", default="text-embedding-3-small")
        if not settings.serper_api_key:
            settings.serper_api_key = config("SERPER_API_KEY", default="")
        return settings

    def clone(self):
        """Creates a copy of the current settings."""
        new_settings = BenchmarkSettings(
            is_template=False,
            llm_base_url=self.llm_base_url,
            llm_model=self.llm_model,
            llm_api_key=self.llm_api_key,
            llm_judge_model=self.llm_judge_model,
            embedding_model=self.embedding_model,
            max_retries=self.max_retries,
            allow_reasoning=self.allow_reasoning,
            temperature=self.temperature,
            top_p=self.top_p,
            max_tokens=self.max_tokens,
            search_provider=self.search_provider,
            serper_api_key=self.serper_api_key,
            search_limit=self.search_limit,
            fetch_full_content=self.fetch_full_content,
            memory_type=self.memory_type
        )
        return new_settings

    def to_snapshot_dict(self):
        return {
            "llm": {
                "llm_base_url": self.llm_base_url,
                "llm_model": self.llm_model,
                "llm_judge_model": self.llm_judge_model,
                "embedding_model": self.embedding_model,
                "max_retries": self.max_retries,
                "allow_reasoning": self.allow_reasoning,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "max_tokens": self.max_tokens,
                "llm_api_key": self.llm_api_key,
            },
            "search": {
                "search_provider": self.search_provider,
                "search_limit": self.search_limit,
                "serper_fetch_full_content": self.fetch_full_content,
            },
            "agent": {
                "memory_type": self.memory_type
            }
        }

class MultiTurnRun(models.Model):
    """
    Represents a group of benchmark sessions, typically from a single pipeline run.
    """
    name = models.CharField(max_length=255, default='Pipeline Run')
    created_at = models.DateTimeField(auto_now_add=True)
    settings = models.ForeignKey(BenchmarkSettings, on_delete=models.CASCADE, null=True, blank=True)
    is_ad_hoc = models.BooleanField(default=False, help_text="True if this is a single ad-hoc session, False if it's a pipeline run.")

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
        ('vanilla_llm', 'Vanilla LLM'),
        ('rag', 'RAG'),
        ('vanilla_agent', 'Vanilla Agent'),
        ('browser_agent', 'Browser Agent'),
    ]

    run = models.ForeignKey(MultiTurnRun, related_name='sessions', on_delete=models.CASCADE)
    question = models.TextField()
    ground_truths = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    is_completed = models.BooleanField(default=False)
    run_tag = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    
    pipeline_type = models.CharField(max_length=50, choices=PIPELINE_TYPE_CHOICES, default='vanilla_llm')

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
    is_correct_llm = models.BooleanField(null=True, blank=True, help_text="Result of LLM-as-a-judge evaluation")
    is_correct_rule = models.BooleanField(null=True, blank=True, help_text="Result of rule-based evaluation")
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processing')
    log = models.JSONField(default=dict, blank=True, help_text="Structured log of the execution (e.g. prompts, search queries, results).")

    class Meta:
        unique_together = ('session', 'trial_number')
        ordering = ['trial_number']

    def __str__(self):
        return f"Trial {self.trial_number} for Session {self.session.id}"