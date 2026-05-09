from django import forms


class QuizTakeForm:
    """Factory for a per-quiz ModelForm-style form without a model."""

    @classmethod
    def for_questions(cls, questions):
        fields = {}
        for q in questions:
            choices = [(str(c.pk), c.answer_text) for c in q.choices.all()]
            fields[f"q_{q.pk}"] = forms.ChoiceField(
                label=q.question_text,
                choices=choices,
                widget=forms.RadioSelect,
                required=True,
            )
        return type("DynamicQuizTakeForm", (forms.Form,), fields)
