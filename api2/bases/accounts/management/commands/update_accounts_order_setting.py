from django.core.management.base import BaseCommand, CommandError

from api.bases.accounts.models import Account
from api.bases.orders.models import OrderSetting


class Command(BaseCommand):
    help = "Update order setting of accounts"

    def add_arguments(self, parser):
        parser.add_argument("--account_alias", nargs="+", type=str)
        parser.add_argument("--order_setting_id", type=int)

    def handle(self, *args, **options):
        try:
            order_setting = OrderSetting.objects.get(id=options["order_setting_id"])
        except OrderSetting.DoesNotExist:
            raise CommandError(
                f"""OrderSetting({options["order_setting_id"]}) does not exist."""
            )

        accounts = Account.objects.filter(account_alias__in=options["account_alias"])
        account_aliases = accounts.values_list("account_alias", flat=True)

        missing_account_aliases = list(
            set(options["account_alias"]) - set(account_aliases)
        )
        if missing_account_aliases:
            raise CommandError(
                f"""Account({", ".join(missing_account_aliases)}) does not exist."""
            )

        accounts.update(order_setting=order_setting)

        self.stdout.write(
            self.style.SUCCESS(
                f"""Successfully updated Account({", ".join(account_aliases)}) """
                f"""with OrderSetting({options["order_setting_id"]})."""
            )
        )
