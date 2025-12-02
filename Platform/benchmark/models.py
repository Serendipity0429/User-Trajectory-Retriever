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
