"""
Django management command to start the WebSocket server using Daphne.
"""

import os
import sys
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Start the WebSocket server using Daphne"

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            type=str,
            default="0.0.0.0",
            help="Host to bind the server to (default: 0.0.0.0)",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=8000,
            help="Port to bind the server to (default: 8000)",
        )

    def handle(self, *args, **options):
        host = options["host"]
        port = options["port"]

        self.stdout.write(
            self.style.SUCCESS(f"Starting WebSocket server on {host}:{port}")
        )
        self.stdout.write(f"WebSocket endpoint: ws://{host}:{port}/ws/audio/")
        self.stdout.write("Press CTRL+C to stop the server\n")

        try:
            # Import daphne here to avoid import errors if not installed
            from daphne.cli import CommandLineInterface

            # Set up the command line arguments for Daphne
            sys.argv = [
                "daphne",
                "-b",
                host,
                "-p",
                str(port),
                "main.asgi:application",
            ]

            # Run Daphne
            CommandLineInterface.entrypoint()

        except ImportError:
            self.stdout.write(
                self.style.ERROR(
                    "Daphne is not installed. Install it with: pip install daphne"
                )
            )
            sys.exit(1)
        except KeyboardInterrupt:
            self.stdout.write(self.style.SUCCESS("\nWebSocket server stopped"))
