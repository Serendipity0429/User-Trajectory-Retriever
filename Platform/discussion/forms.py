from django import forms
from .models import Post, Comment, Bulletin, Label

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

    class Meta:
        model = Post
        fields = ['title', 'content', 'category', 'pinned']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter title'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Enter content', 'style': 'height: 200px'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(PostForm, self).__init__(*args, **kwargs)
        if not user or not user.is_staff:
            self.fields.pop('pinned', None)

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Add a comment', 'style': 'height: 100px'}),
        }

class BulletinForm(forms.ModelForm):
    attachments = MultipleFileField(required=False)
    class Meta:
        model = Bulletin
        fields = ['title', 'content', 'category', 'pinned']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter title'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Enter content', 'style': 'height: 150px'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'pinned': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
