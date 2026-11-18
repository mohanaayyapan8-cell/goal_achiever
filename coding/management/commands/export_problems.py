import json

from django.core.management.base import BaseCommand

from coding.problems import PROBLEMS


class Command(BaseCommand):
    help = "Print all practice problems (with reference solutions) as JSON. Used by tests_js/ to check them inside Pyodide."

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(PROBLEMS))
