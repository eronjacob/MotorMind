from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import DetailView, FormView

from .forms import QuizTakeForm
from .models import AnswerChoice, Question, Quiz, QuizAttempt


class QuizTakeView(LoginRequiredMixin, FormView):
    template_name = "quizzes/quiz_take.html"

    def dispatch(self, request, *args, **kwargs):
        self.quiz = get_object_or_404(
            Quiz.objects.select_related("course"),
            pk=kwargs["quiz_id"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_class(self):
        questions = list(
            Question.objects.filter(quiz=self.quiz)
            .prefetch_related("choices")
            .order_by("order", "pk")
        )
        return QuizTakeForm.for_questions(questions)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["quiz"] = self.quiz
        ctx["questions"] = (
            Question.objects.filter(quiz=self.quiz)
            .prefetch_related("choices")
            .order_by("order", "pk")
        )
        return ctx

    def form_valid(self, form):
        questions = list(
            Question.objects.filter(quiz=self.quiz)
            .prefetch_related("choices")
            .order_by("order", "pk")
        )
        total = len(questions)
        if total == 0:
            messages.warning(self.request, "This quiz has no questions yet.")
            return redirect("courses:course_detail", pk=self.quiz.course_id)

        correct = 0
        for q in questions:
            field = f"q_{q.pk}"
            selected_id = form.cleaned_data.get(field)
            if not selected_id:
                continue
            choice = AnswerChoice.objects.filter(
                pk=selected_id, question=q
            ).first()
            if choice and choice.is_correct:
                correct += 1
        score = int(round(100 * correct / total))
        passed = score >= self.quiz.pass_mark
        QuizAttempt.objects.create(
            quiz=self.quiz,
            student=self.request.user,
            score=score,
            passed=passed,
        )
        return redirect("quizzes:quiz_result", quiz_id=self.quiz.pk)


class QuizResultView(LoginRequiredMixin, DetailView):
    model = Quiz
    template_name = "quizzes/quiz_result.html"
    context_object_name = "quiz"
    pk_url_kwarg = "quiz_id"

    def get_queryset(self):
        return Quiz.objects.select_related("course")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        attempt = (
            QuizAttempt.objects.filter(quiz=self.object, student=self.request.user)
            .order_by("-created_at")
            .first()
        )
        ctx["last_attempt"] = attempt
        ctx["score"] = attempt.score if attempt else None
        ctx["passed"] = attempt.passed if attempt else None
        return ctx
