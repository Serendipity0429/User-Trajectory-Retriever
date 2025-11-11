from django import forms
from .models import Post, Comment, Bulletin, Label, DiscussionSettings
from task_manager.models import ExtensionVersion
import re
from packaging.version import parse as parse_version

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={'class': 'form-control'}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

class PostForm(forms.ModelForm):
    labels = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., bug, feature-request, ui-ux'}),
        help_text='Enter labels separated by commas.'
    )
    attachments = MultipleFileField(required=False)
    pinned = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    is_private = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    class Meta:
        model = Post
        fields = ['title', 'content', 'category', 'pinned', 'is_private']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter title'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Enter content', 'style': 'height: 200px'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(PostForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial['content'] = self.instance.raw_content

        if not user or not user.is_staff:
            self.fields.pop('pinned', None)

        if not user:
            self.fields.pop('is_private', None)

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Add a comment', 'style': 'height: 100px'}),
        }

class BulletinForm(forms.ModelForm):
    attachments = MultipleFileField(required=False)
    is_extension_update = forms.BooleanField(required=False, label="Chrome Extension Update", widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    extension_version = forms.CharField(required=False, label="New Extension Version", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 3.1.1'}))

    class Meta:
        model = Bulletin
        fields = ['title', 'content', 'category', 'pinned', 'send_notification', 'expiry_date']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter title'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Enter content', 'style': 'height: 150px'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'pinned': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'send_notification': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'expiry_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        super(BulletinForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial['content'] = self.instance.raw_content

    def clean_extension_version(self):
        is_update = self.cleaned_data.get('is_extension_update')
        version_str = self.cleaned_data.get('extension_version')

        if not is_update:
            return None

        if not version_str:
            raise forms.ValidationError("This field is required for an extension update.")

        # Validate version format
        if not re.match(r'^\d{1,5}(\.\d{1,5}){0,3}$', version_str):
            raise forms.ValidationError("Invalid version format. Use 1-4 dot-separated integers (e.g., '3.1.1').")

        parts = [int(p) for p in version_str.split('.')]
        if any(p > 65536 for p in parts):
            raise forms.ValidationError("Each part of the version number cannot exceed 65536.")

        # Validate monotonic increase
        latest_version_obj = ExtensionVersion.objects.order_by('-id').first()
        if latest_version_obj:
            latest_version = parse_version(latest_version_obj.version)
            new_version = parse_version(version_str)
            if new_version <= latest_version:
                raise forms.ValidationError(f"New version ({new_version}) must be greater than the latest version ({latest_version}).")

        return version_str

class DiscussionSettingsForm(forms.ModelForm):
    class Meta:
        model = DiscussionSettings
        fields = ['post_limit_per_day']
        widgets = {
            'post_limit_per_day': forms.NumberInput(attrs={'class': 'form-control'}),
        }
