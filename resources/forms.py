from pathlib import Path

from django import forms

from courses.models import Course

from .models import Resource

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown", ".docx"}


class MinimalResourceUploadForm(forms.Form):
    """
    Minimal teacher upload: file + optional courses + optional resource type (blank = auto by extension).
    """

    uploaded_file = forms.FileField(
        widget=forms.FileInput(attrs={"class": "form-control"}),
    )
    courses = forms.ModelMultipleChoiceField(
        queryset=Course.objects.all().order_by("title"),
        required=False,
        widget=forms.CheckboxSelectMultiple(),
    )
    resource_type = forms.ChoiceField(
        required=False,
        choices=[
            ("", "Auto (PDF → book, text/Markdown/DOCX → notes)"),
            *Resource.ResourceType.choices,
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["courses"].required = False

    def clean_uploaded_file(self):
        f = self.cleaned_data.get("uploaded_file")
        if not f:
            raise forms.ValidationError("A file is required.")
        name = getattr(f, "name", "") or ""
        ext = Path(name).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise forms.ValidationError(
                f"Unsupported file type {ext or 'unknown'}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )
        return f


class ResourceEditForm(forms.ModelForm):
    """Full metadata editing (post-upload corrections)."""

    class Meta:
        model = Resource
        fields = (
            "title",
            "source_title",
            "description",
            "author",
            "edition",
            "publisher",
            "year",
            "number_of_pages",
            "isbn",
            "resource_type",
            "courses",
        )
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "source_title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "author": forms.TextInput(attrs={"class": "form-control"}),
            "edition": forms.TextInput(attrs={"class": "form-control"}),
            "publisher": forms.TextInput(attrs={"class": "form-control"}),
            "year": forms.NumberInput(attrs={"class": "form-control"}),
            "number_of_pages": forms.NumberInput(attrs={"class": "form-control"}),
            "isbn": forms.TextInput(attrs={"class": "form-control"}),
            "resource_type": forms.Select(attrs={"class": "form-select"}),
            "courses": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["courses"].queryset = Course.objects.all().order_by("title")
        self.fields["courses"].required = False
