from django import forms
from .models import ExtensionVersion
import re
from packaging.version import parse as parse_version


class ExtensionVersionForm(forms.ModelForm):
    class Meta:
        model = ExtensionVersion
        fields = ["version", "update_link", "description"]
        widgets = {
            "version": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g., 3.1.1"}
            ),
            "update_link": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://example.com/update",
                }
            ),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def clean_version(self):
        version_str = self.cleaned_data.get("version")
        if not version_str:
            raise forms.ValidationError("This field is required.")

        # Validate version format
        if not re.match(r"^\d{1,5}(\.\d{1,5}){0,3}$", version_str):
            raise forms.ValidationError(
                "Invalid version format. Use 1-4 dot-separated integers (e.g., '3.1.1')."
            )

        parts = [int(p) for p in version_str.split(".")]
        if any(p > 65536 for p in parts):
            raise forms.ValidationError(
                "Each part of the version number cannot exceed 65536."
            )

        # Validate monotonic increase
        latest_version_obj = ExtensionVersion.objects.order_by("-id").first()
        if latest_version_obj:
            latest_version = parse_version(latest_version_obj.version)
            new_version = parse_version(version_str)
            if new_version <= latest_version:
                raise forms.ValidationError(
                    f"New version ({new_version}) must be greater than the latest version ({latest_version})."
                )

        return version_str
