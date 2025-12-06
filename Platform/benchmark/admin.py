from django.contrib import admin
from .models import (
    LLMSettings, 
    InteractiveSessionGroup, 
    InteractiveSession, 
    InteractiveTrial,
    AdhocRun,
    AdhocSessionResult,
    RagSettings,
    RagBenchmarkRun,
    RagBenchmarkResult
)

# Register your models here.
@admin.register(LLMSettings)
class LLMSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'llm_model', 'llm_base_url')

@admin.register(InteractiveSessionGroup)
class InteractiveSessionGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    ordering = ('-created_at',)

class InteractiveTrialInline(admin.TabularInline):
    model = InteractiveTrial
    extra = 0
    readonly_fields = ('created_at',)

@admin.register(InteractiveSession)
class InteractiveSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'group', 'question', 'is_completed', 'created_at')
    list_filter = ('is_completed', 'group')
    search_fields = ('question',)
    inlines = [InteractiveTrialInline]

@admin.register(InteractiveTrial)
class InteractiveTrialAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'trial_number', 'status', 'is_correct', 'created_at')
    list_filter = ('status', 'is_correct')

class AdhocSessionResultInline(admin.TabularInline):
    model = AdhocSessionResult
    extra = 0
    readonly_fields = ('question', 'answer', 'is_correct_rule', 'is_correct_llm')
    can_delete = False

@admin.register(AdhocRun)
class AdhocRunAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'total_questions', 'correct_answers', 'accuracy')
    ordering = ('-created_at',)
    inlines = [AdhocSessionResultInline]

@admin.register(RagSettings)
class RagSettingsAdmin(admin.ModelAdmin):
    list_display = ('id',)

class RagBenchmarkResultInline(admin.TabularInline):
    model = RagBenchmarkResult
    extra = 0
    readonly_fields = ('question', 'answer', 'is_correct_rule', 'is_correct_llm', 'num_docs_used')
    can_delete = False

@admin.register(RagBenchmarkRun)
class RagBenchmarkRunAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'total_questions', 'correct_answers', 'accuracy')
    ordering = ('-created_at',)
    inlines = [RagBenchmarkResultInline]