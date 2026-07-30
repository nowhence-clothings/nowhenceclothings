from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

User = get_user_model()

class Command(BaseCommand):
    help = "Create an admin user if it doesn't already exist."

    def handle(self, *args, **kwargs):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "Owner")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "kollatibhanuprasad1515@gmail.com")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "Sanjan@123")

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.SUCCESS("Admin user already exists."))
            return

        User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )

        self.stdout.write(self.style.SUCCESS("Admin user created successfully."))