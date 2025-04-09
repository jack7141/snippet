import pandas as pd
from typing import Dict

from django.conf import settings
from django.shortcuts import get_object_or_404
from common.utils import get_local_today

from api.bases.managements.components.data_stagers import TickerStager
from api.bases.managements.components.exchange.currencies import ForeignCurrency
from api.bases.managements.order_router.order_manager import OrderManagement
from services.portfolio import PortfolioService
from services.exceptions import PortfolioDoesNotExistError

TR_BACKEND = settings.TR_BACKEND
INFOMAX_BACKEND = settings.INFOMAX_BACKEND


class PortfolioMapMixin:
    PORT_TYPES = [
        # universe_index, strategy_code
        (1080, 0),
        (1080, 1),
        (1080, 2),
        (1080, 90),
        (1080, 91),
        (1080, 92),
        (1080, 93),
        (1080, 94),
    ]

    def get_port_seq_by_risk_type(
        self, universe_index: int, strategy_code: int, filter_date: str
    ) -> Dict[str, dict]:
        """Get portfolio sequences

        :param universe_index: Universe index
        :type port_type: int
          example: 1080
        :param strategy_code: Strategy code
        :type strategy_code: int
          example: 0 | 1
        :param filter_date: Date
        :type filter_date: str, YYYY-MM-DD
          example: 2021-07-01
        :return: Portfolio sequence by risk type
        :rtype: dict
          example:
            {'0':
             {'port_seq': 20210723108000002,
              'port_data':
               [
                {
                 'code': 'SCHP',
                 'weight': 0.51,
                 'asset_category': '채권'
                }
               ]
              }
            }
        """
        try:
            portfolio_seqs = PortfolioService.get(
                universe_index=universe_index,
                strategy_code=strategy_code,
                port_date=filter_date,
            )
        except PortfolioDoesNotExistError:
            return None

        df_latest_port_data = pd.DataFrame(portfolio_seqs["portfolios"])
        df_latest_port_data["port_seq"] = df_latest_port_data["port_seq"].astype(int)
        df_latest_port_data["risk_type"] = df_latest_port_data["risk_type"].astype(str)
        df_port_data_by_risk_type = df_latest_port_data.set_index("risk_type")[
            ["port_seq", "port_data"]
        ]
        return df_port_data_by_risk_type.T.to_dict()

    def get_portfolio_map(self, filter_date: str) -> Dict[str, dict]:
        """Get portfolio map by strategy code

        :param filter_date: Date
        :type filter_date: str, YYYY-MM-DD
          example: 2021-07-01
        :return: Portfolio map by strategy code
        :rtype: dict
          example:
            {'00':
             {'0':
              {'port_seq': 20210723108000002,
               'port_data':
                [
                 {
                  'code': 'SCHP',
                  'weight': 0.51,
                  'asset_category': '채권'
                 }
                ]
               }
             }
            }
        """

        portfolio_map = dict()

        for universe_index, strategy_code in self.PORT_TYPES:
            port_seq = self.get_port_seq_by_risk_type(
                universe_index, strategy_code, filter_date
            )
            if port_seq is None:
                continue

            portfolio_map[f"{strategy_code:02}"] = port_seq

        return portfolio_map


class RequiredOrderManagementMixin(PortfolioMapMixin):
    def init_order_management(self, mode):
        kst_today = get_local_today()
        account = self.get_object()
        # if risk_type is empty, default risk_type is 0
        accnt_risk_type = int(account.risk_type) if account.risk_type else 0
        tr_api_base = TR_BACKEND[str(account.vendor_code).upper()].HOST
        exchange_rate = ForeignCurrency.get_exchange_rate(api_base=tr_api_base)
        self.portfolio_map = self.get_portfolio_map(
            filter_date=kst_today.strftime("%Y-%m-%d")
        )
        portfolio = self.portfolio_map.get(
            int(accnt_risk_type)
        )  # TODO: strategy 별 처리 필요, 현재 상태에서 오류 발생.

        om = OrderManagement(
            account_alias=account,
            portfolio=portfolio["port_data"],
            data_stager=TickerStager(api_url=INFOMAX_BACKEND.API_HOST),
            exchange_rate=exchange_rate,
            vendor_code=account.vendor_code,
            mode=mode,
        )
        return om


class GetObjectByPkMixin:
    def get_object(self):
        queryset = self.get_queryset()

        # Perform the lookup filtering.
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field

        assert lookup_url_kwarg in self.kwargs, (
            "Expected view %s to be called with a URL keyword argument "
            'named "%s". Fix your URL conf, or set the `.lookup_field` '
            "attribute on the view correctly."
            % (self.__class__.__name__, lookup_url_kwarg)
        )

        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        obj = get_object_or_404(queryset, **filter_kwargs)

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)

        return obj
