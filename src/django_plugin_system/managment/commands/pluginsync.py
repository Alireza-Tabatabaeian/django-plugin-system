from django.core.management.base import BaseCommand, CommandParser

from ...services import sync_registered_plugins_to_db


class Command(BaseCommand):
    help = "Synchronize registered plugin types/items into the database."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--mode",
            choices=["create", "update"],
            default="create",
            help='How to persist registry data. "create" = get_or_create (preserve admin edits). "update" = update_or_create.',
        )
        parser.add_argument(
            "--no-prune",
            action="store_true",
            help="Do not prune plugin types/items whose manager/module is no longer installed.",
        )

    def handle(self, *args, **options):
        mode = options["mode"]
        prune = not options["no_prune"]

        result = sync_registered_plugins_to_db(mode=mode, prune=prune)

        self.stdout.write(self.style.SUCCESS("Plugin registry sync completed"))
        self.stdout.write(f"- Types created: {result['types_created']}, found: {result['types_found']}")
        self.stdout.write(f"- Items created: {result['items_created']}, found: {result['items_found']}")
        if prune:
            self.stdout.write(f"- Pruned types: {result['pruned_types']}, pruned items: {result['pruned_items']}")
