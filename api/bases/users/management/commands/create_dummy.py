import datetime
import random
import string
import json
from dateutil.relativedelta import relativedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from api.bases.users.models import User
from api.bases.contracts.models import Contract, Term, Condition, ProvisionalContract, Rebalancing, ContractType, \
    AssetsDetail, Assets
from api.bases.orders.models import Order
from api.bases.authentications.models import Auth
from api.bases.contracts.mixins import RebalancingMixin
from api.bases.portfolios.models import PortfolioDaily
from api.versioned.v1.portfolios.serializers import PortfolioWrapSerializer


class Command(RebalancingMixin, BaseCommand):
    args = ''
    help = ('List registered dummy users.')

    @staticmethod
    def get_random_account_number():
        return str(random.randrange(1, 9)) + ''.join([str(random.randrange(0, 9)) for i in range(9)])

    @staticmethod
    def get_random_account_alias():
        return datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')

    @staticmethod
    def get_random_ci():
        return ''.join(random.choice(string.ascii_letters) for x in range(88))

    @staticmethod
    def turn_off_auto_now_add(ModelClass, field_name):
        field = ModelClass._meta.get_field(field_name)
        field.auto_now_add = False

    def add_arguments(self, parser):
        parser.add_argument('--start', '-s', dest='start', default=0, type=int, help='Start number of dummy user.')
        parser.add_argument('--end', '-e', dest='end', default=10, type=int, help='End number of dummy user.')
        parser.add_argument('--email-format', '-ef', dest='email_fmt', default='test{}@test.test', type=str)
        parser.add_argument('--name-format', '-nf', dest='name_fmt', default='tester{}', type=str)
        parser.add_argument('--default-password', '-dp', dest='password_fmt', default='password', type=str)

    def get_portfolio(self, contract, port_date):
        universe = None
        if contract.contract_type == 'FA':
            universe = 1003
        elif contract.contract_type == 'EA':
            universe = 2013
        elif contract.contract_type == 'PA':
            universe = 1051

        port = PortfolioDaily.objects.filter(port_type__universe_index__universe_index=universe, port_date=port_date)

        if port.exists():
            serializer = PortfolioWrapSerializer({
                'date': contract.created_at.date(),
                'universe_index': universe,
                'portfolios': port})

        else:
            port = PortfolioDaily.objects.filter(port_type__universe_index__universe_index=universe,
                                                 port_date__lte=port_date)

            serializer = PortfolioWrapSerializer({
                'date': port.first().port_date,
                'universe_index': universe,
                'portfolios': port})

        portfolio = serializer.data.get('portfolios')[contract.risk_type]

        return portfolio

    def create_dummy_assets(self, contract, port_date, end_date):
        base = 1000000
        base_amount = 1000000
        deposit = 0
        assets = []
        portfolio = self.get_portfolio(contract, port_date)

        target_date = port_date.replace(hour=15, minute=0, second=0, microsecond=0)
        init_detail = {}

        if Assets.objects.filter(account_alias_id=contract.account_alias).exists():
            last_asset = Assets.objects.filter(account_alias_id=contract.account_alias).latest('created_at')
            last_asset.prev_deposit = 1000000
            last_asset.save()

            base = last_asset.balance + last_asset.deposit + last_asset.prev_deposit
            base_amount = last_asset.base + last_asset.prev_deposit

        while target_date.date() < end_date.date():
            base_total = 0
            balance_total = 0
            asset_details = []
            for p in portfolio['port_data']:
                if p.get('asset_category') != 'LIQ':
                    code = p.get('code')

                    data = {
                        'code': code,
                        'account_alias_id': contract.account_alias,
                        'created_at': target_date
                    }
                    asset_detail = AssetsDetail(**data)
                    try:
                        nav = asset_detail.asset.trading.filter(date__lte=target_date.date()).last().nav / 1000
                    except Exception as e:
                        nav = 1

                    if not init_detail.get(code, None):
                        init_detail[code] = asset_detail
                        asset_detail.shares = int(base * p.get('weight') / float(nav))
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
                deposit = base - base_total

            assets.append(Assets(base=base_amount, deposit=deposit, prev_deposit=0,
                                 balance=balance_total, created_at=target_date,
                                 account_alias_id=contract.account_alias))

            target_date += relativedelta(days=1)

        if assets:
            Assets.objects.bulk_create(assets)

    def handle(self, *args, **kwargs):
        email_fmt = kwargs['email_fmt']
        name_fmt = kwargs['name_fmt']
        password_fmt = kwargs['password_fmt']
        start = kwargs['start']
        end = kwargs['end']

        term = Term.objects.get(is_default=True, is_publish=True)
        contract_types = ContractType.objects.all()

        self.turn_off_auto_now_add(Contract, 'created_at')
        self.turn_off_auto_now_add(Order, 'created_at')
        self.turn_off_auto_now_add(Rebalancing, 'created_at')
        self.turn_off_auto_now_add(Assets, 'created_at')
        self.turn_off_auto_now_add(AssetsDetail, 'created_at')

        default_created = timezone.now() - relativedelta(months=4)

        try:
            vendor = User.objects.get(is_vendor=True)
        except User.DoesNotExist:
            vendor = User.objects.create_user('vendor@vendor.vendor', password_fmt, is_active=True, is_vendor=True)
            vendor.profile.name = 'vendor'
            vendor.profile.save()

        for i in range(start, end + 1):
            try:
                user = User.objects.get(email=email_fmt.format(i), is_active=True)
                user.delete()
            except:
                pass

            try:
                user = User.objects.create_user(email_fmt.format(i), password_fmt, is_active=True,
                                                date_joined=default_created)
                user.profile.name = name_fmt.format(i)
                user.profile.risk_type = i % 5
                user.profile.save()

                for ctype in contract_types:
                    account_number = self.get_random_account_number()
                    account_alias = self.get_random_account_alias()

                    contract = Contract.objects.create(
                        contract_type=ctype,
                        account_number=account_number,
                        account_alias=account_alias,
                        user=user,
                        term=term,
                        risk_type=i % 5,
                        vendor=vendor,
                        status=1,
                        created_at=default_created
                    )

                    auth = Auth.objects.create(
                        user=user,
                        cert_type='3',
                        etc_1='0000000000',
                        etc_2=contract.id.hex,
                        is_verified=True
                    )

                    auth.generate_numeric_code(2)
                    auth.save()

                    contract.firm_agreement_at = auth.created_date
                    contract.save()

                    if random.randint(1, 100) > 90:
                        contract.is_canceled = True
                        contract.status = 0
                        contract.save()
                        continue

                    order = Order.objects.create(
                        order_item=contract,
                        order_rep=vendor,
                        status=Order.STATUS.processing,
                        user=user,
                        mode=Order.MODES.new_order,
                        created_at=default_created
                    )

                    order.status = Order.STATUS.completed
                    order.completed_at = default_created
                    order.save()

                    last_order = contract.orders.latest('created_at')
                    last_created_at = last_order.created_at
                    reb_interval = contract.get_reb_interval()

                    while last_created_at + reb_interval < timezone.now():
                        self.create_dummy_assets(contract, last_created_at, last_created_at+reb_interval)
                        last_created_at += reb_interval
                        contract.rebalancing = contract.is_available_reb
                        contract.save(update_fields=['rebalancing'])

                        next_mode = contract.get_next_order_mode()

                        if next_mode in [Order.MODES.rebalancing, Order.MODES.sell]:
                            reb_instance, reb_created = Rebalancing.objects.get_or_create(contract=contract,
                                                                                          sold_at__isnull=True,
                                                                                          created_at=last_created_at)
                        else:
                            reb_instance, reb_created = Rebalancing.objects.get_or_create(contract=contract,
                                                                                          bought_at__isnull=True,
                                                                                          created_at=last_created_at)

                        modes = [Order.MODES.rebalancing]
                        if ctype == 'EA':
                            modes = [Order.MODES.sell, Order.MODES.buy]

                        for mode in modes:
                            reb_order = Order.objects.create(
                                order_item=contract,
                                order_rep=vendor,
                                status=Order.STATUS.completed,
                                user=user,
                                mode=mode,
                                created_at=last_created_at + relativedelta(seconds=1) if mode == 'buy' else last_created_at,
                                completed_at=last_created_at + relativedelta(seconds=1) if mode == 'buy' else last_created_at
                            )

                            if mode == 'sell':
                                reb_instance.sold_at = reb_order.completed_at
                            elif mode == 'buy':
                                reb_instance.bought_at = reb_order.completed_at + relativedelta(seconds=1)
                            elif mode == 'rebalancing':
                                reb_instance.sold_at = reb_order.completed_at
                                reb_instance.bought_at = reb_order.completed_at
                            reb_instance.save()

                self.stdout.write('{} - generated.'.format(email_fmt.format(i)))
            except Exception as e:
                self.stderr.write(e)
