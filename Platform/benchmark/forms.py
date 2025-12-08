from django import forms
from .models import BenchmarkDataset

class BenchmarkDatasetForm(forms.ModelForm):
    class Meta:
        model = BenchmarkDataset
        fields = ['name', 'description', 'file']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
