"""
Management command to broadcast TTS messages to WebSocket clients.

Usage:
    python manage.py broadcast_tts "Your message here"
    python manage.py broadcast_tts "Alert!" --group alerts
"""

import asyncio
from django.core.management.base import BaseCommand
from agents.services.websocket_tts_broadcaster import broadcast_tts_message


class Command(BaseCommand):
    help = "Broadcast a text-to-speech message to all connected WebSocket clients"

    def add_arguments(self, parser):
        parser.add_argument("text", type=str, help="Text message to broadcast")
        parser.add_argument(
            "--group",
            type=str,
            default="edge_devices",
            help="Channel layer group name (default: edge_devices)",
        )

    def handle(self, *args, **options):
        text = options["text"]
        group = options["group"]

        self.stdout.write(f"Broadcasting message to group '{group}'...")
        self.stdout.write(f"Text: {text}")

        # Run async broadcast
        asyncio.run(broadcast_tts_message(text, group_name=group))

        self.stdout.write(self.style.SUCCESS("✅ Message broadcast successfully!"))
