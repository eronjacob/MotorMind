from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("resources", "0002_resource_isbn_resource_metadata_lookup_error_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="resource",
            name="number_of_pages",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
