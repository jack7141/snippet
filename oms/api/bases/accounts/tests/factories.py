from factory.django import DjangoModelFactory

from api.bases.accounts.models import Account


class AccountFactory(DjangoModelFactory):
    class Meta:
        model = Account
        django_get_or_create = ["account_alias"]
