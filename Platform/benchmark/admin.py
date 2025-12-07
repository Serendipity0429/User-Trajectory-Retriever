from django.contrib import admin
from .models import (
    LLMSettings, 
    MultiTurnSessionGroup, 
    MultiTurnSession, 
    MultiTurnTrial, 
    VanillaLLMAdhocRun, 
    VanillaLLMAdhocResult,
    RagSettings,
    RagAdhocRun,
    RagAdhocResult
)

# Register your models here.
@admin.register(LLMSettings)
class LLMSettingsAdmin(admin.ModelAdmin):
    list_display = ('llm_base_url', 'llm_model', 'llm_api_key', 'max_retries')

@admin.register(RagSettings)
class RagSettingsAdmin(admin.ModelAdmin):
    list_display = ('prompt_template',)

@admin.register(MultiTurnSessionGroup)
class MultiTurnSessionGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)

class MultiTurnTrialInline(admin.TabularInline):
    model = MultiTurnTrial
    extra = 0
    readonly_fields = ('created_at',)

@admin.register(MultiTurnSession)
class MultiTurnSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'question', 'is_completed', 'created_at', 'pipeline_type', 'group')
    list_filter = ('is_completed', 'pipeline_type', 'group')
    search_fields = ('question',)
    inlines = [MultiTurnTrialInline]

@admin.register(MultiTurnTrial)
class MultiTurnTrialAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'trial_number', 'status', 'is_correct', 'created_at')
    list_filter = ('status', 'is_correct')
    search_fields = ('answer', 'feedback', 'session__question')

class VanillaLLMAdhocResultInline(admin.TabularInline):
    model = VanillaLLMAdhocResult
    extra = 0

@admin.register(VanillaLLMAdhocRun)
class VanillaLLMAdhocRunAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'total_questions', 'correct_answers', 'accuracy')
    search_fields = ('name',)
    inlines = [VanillaLLMAdhocResultInline]

class RagAdhocResultInline(admin.TabularInline):
    model = RagAdhocResult
    extra = 0

@admin.register(RagAdhocRun)
class RagAdhocRunAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'total_questions', 'correct_answers', 'accuracy')
    search_fields = ('name',)
    inlines = [RagAdhocResultInline]
