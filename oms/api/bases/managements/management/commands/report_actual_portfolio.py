import datetime
import logging

import pandas as pd

from django.core.management.base import BaseCommand, CommandError

from api.bases.managements.services.actual_portfolio_report import (
    ActualPortfolioReportService,
    MIN_DEPOSIT_RATIO_DEFAULT,
    DEPOSIT_BUFFER_RATIO_DEFAULT,
)

logging.disable(logging.DEBUG)


class Command(BaseCommand):
    help = "Report actual portfolio"

    def add_arguments(self, parser):
        parser.add_argument("universe_index", type=str)
        parser.add_argument("strategy_code", type=str)
        parser.add_argument("date", type=datetime.date.fromisoformat)
        parser.add_argument("base_amount", type=float)
        parser.add_argument("exchange_rate", type=float)
        parser.add_argument(
            "--min_deposit_ratio", type=float, default=MIN_DEPOSIT_RATIO_DEFAULT
        )
        parser.add_argument(
            "--deposit_buffer_ratio", type=float, default=DEPOSIT_BUFFER_RATIO_DEFAULT
        )

    def handle(self, *args, **options):
        pd.set_option("display.max_colwidth", None)
        pd.set_option("display.max_columns", None)

        try:
            service = ActualPortfolioReportService(
                options["universe_index"],
                options["strategy_code"],
                options["date"],
                options["base_amount"],
                options["exchange_rate"],
                options["min_deposit_ratio"],
                options["deposit_buffer_ratio"],
            )
            service.show()
        except Exception as e:
            raise CommandError(e)
