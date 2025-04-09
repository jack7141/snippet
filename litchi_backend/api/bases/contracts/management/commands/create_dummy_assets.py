from django.core.management.base import BaseCommand
from django.utils import timezone

from dateutil.relativedelta import relativedelta

from api.bases.contracts.models import Contract, AssetsDetail, Assets
from api.bases.portfolios.models import PortfolioDaily
from api.versioned.v1.portfolios.serializers import PortfolioWrapSerializer


class Command(BaseCommand):
    args = ''
    help = ("Create contract's dummy asset data.")

    def add_arguments(self, parser):
        parser.add_argument('--base', '-b', dest='base', default=1000000, type=int, help='Start default base amount.')

    def get_portfolio(self, contract):
        universe = None
        if contract.contract_type == 'FA':
            universe = 1003
        elif contract.contract_type == 'EA':
            universe = 2013
        elif contract.contract_type == 'PA':
            universe = 1051

        port = PortfolioDaily.objects.filter(port_type__universe_index__universe_index=universe,
                                             port_date=contract.created_at)

        if port.exists():
            serializer = PortfolioWrapSerializer({
                'date': contract.created_at.date(),
                'universe_index': universe,
                'portfolios': port})

        else:
            port = PortfolioDaily.objects.filter(port_type__universe_index__universe_index=universe,
                                                 port_date__lte=contract.created_at)

            serializer = PortfolioWrapSerializer({
                'date': port.first().port_date,
                'universe_index': universe,
                'portfolios': port})

        portfolio = serializer.data.get('portfolios')[contract.risk_type]

        return portfolio

    def clear_previous_data(self, contract):
        target_date = contract.created_at.replace(hour=15, minute=0, second=0, microsecond=0)

        AssetsDetail.objects.filter(created_at__gte=target_date,
                                    created_at__lte=timezone.now(),
                                    account_alias_id=contract.account_alias).delete()

        Assets.objects.filter(account_alias_id=contract.account_alias,
                              created_at__gte=target_date,
                              created_at__lte=timezone.now()).delete()

    @staticmethod
    def turn_off_auto_now_add(ModelClass, field_name):
        field = ModelClass._meta.get_field(field_name)
        field.auto_now_add = False

    def handle(self, *args, **kwargs):
        base_amount = kwargs['base']

        self.turn_off_auto_now_add(Assets, 'created_at')
        self.turn_off_auto_now_add(AssetsDetail, 'created_at')

        for item in Contract.objects.filter(status=1):
            print(item.contract_type, item.user.email, item.contract_number)

            deposit = 0
            assets = []
            portfolio = self.get_portfolio(item)

            self.clear_previous_data(item)

            target_date = item.created_at.replace(hour=15, minute=0, second=0, microsecond=0)
            init_detail = {}

            while target_date.date() < timezone.now().date():
                base_total = 0
                balance_total = 0
                asset_details = []
                for p in portfolio['port_data']:
                    if p.get('asset_category') != 'LIQ':
                        code = p.get('code')

                        data = {
                            'code': code,
                            'account_alias_id': item.account_alias,
                            'created_at': target_date
                        }
                        asset_detail = AssetsDetail(**data)
                        try:
                            nav = asset_detail.asset.trading.filter(date__lte=target_date.date()).last().nav / 1000
                        except Exception as e:
                            nav = 1

                        if not init_detail.get(code, None):
                            init_detail[code] = asset_detail
                            asset_detail.shares = int(kwargs['base'] * p.get('weight') / float(nav))
                            asset_detail.buy_price = round(asset_detail.shares * nav)
                        else:
                            asset_detail.shares = init_detail.get(code).shares
                            asset_detail.buy_price = init_detail.get(code).buy_price

                        asset_detail.balance = round(asset_detail.shares * nav)
                        asset_details.append(asset_detail)

                        base_total += asset_detail.buy_price
                        balance_total += asset_detail.balance

                if asset_details:
                    AssetsDetail.objects.bulk_create(asset_details)

                if not deposit:
                    deposit = base_amount - base_total

                assets.append(Assets(base=base_amount, deposit=deposit, prev_deposit=0,
                                     balance=balance_total, created_at=target_date,
                                     account_alias_id=item.account_alias))

                target_date += relativedelta(days=1)

            if assets:
                Assets.objects.bulk_create(assets)
