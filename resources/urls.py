from django.urls import path

from . import views

app_name = "resources"

urlpatterns = [
    path("", views.ResourceDashboardView.as_view(), name="dashboard"),
    path("upload/", views.ResourceUploadView.as_view(), name="upload"),
    path("<int:pk>/", views.ResourceDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.ResourceEditView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.ResourceDeleteView.as_view(), name="delete"),
    path("<int:pk>/reingest/", views.ResourceReingestView.as_view(), name="reingest"),
    path("<int:pk>/lookup-metadata/", views.ResourceMetadataLookupRetryView.as_view(), name="lookup_metadata"),
    path("jobs/<int:job_id>/progress/", views.IngestionJobProgressView.as_view(), name="job_progress"),
    path("test/", views.ResourceRetrievalTestView.as_view(), name="test_retrieval"),
]
