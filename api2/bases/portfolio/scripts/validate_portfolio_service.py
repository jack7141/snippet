import logging

import pandas as pd

from django.db.models import Max

from api.bases.portfolio.models import Portfolio
from services.portfolio import PortfolioService
from services.exceptions import PortfolioDoesNotExistError

logger = logging.getLogger(__name__)


def get_from_df(universe_index, strategy_code, port_date):
    port_type = f"{universe_index}{strategy_code:02}"

    latest_port_seq = (
        Portfolio.objects.filter(port_date__lte=port_date)
        .values("port_type")
        .annotate(latest_port_seq=Max("port_seq"))
        .order_by("port_type")
        .filter(port_type__startswith=port_type)
    )
    if not latest_port_seq:
        return None

    lastest_port_data = Portfolio.objects.filter(
        port_seq__in=latest_port_seq.values("latest_port_seq")
    ).order_by("port_seq")
    df_latest_port_data = pd.DataFrame(lastest_port_data.values())
    df_latest_port_data["risk_type"] = (
        df_latest_port_data["port_type"].astype(str).str[-1].astype(str)
    )
    return df_latest_port_data.set_index("risk_type")[["port_seq", "port_data"]]


def get_from_api(universe_index, strategy_code, port_date):
    try:
        result = PortfolioService.get(
            universe_index=universe_index,
            strategy_code=strategy_code,
            port_date=port_date,
        )
    except PortfolioDoesNotExistError:
        return None

    lastest_port_data = result["portfolios"]
    df_latest_port_data = pd.DataFrame(lastest_port_data)
    df_latest_port_data["port_seq"] = df_latest_port_data["port_seq"].astype(int)
    df_latest_port_data["risk_type"] = df_latest_port_data["risk_type"].astype(str)
    return df_latest_port_data.set_index("risk_type")[["port_seq", "port_data"]]


def run(universe_index, strategy_code, port_date):
    # example: ./manage.py runscript validate_port_service --script-args 1080 0 2021-07-02

    universe_index = int(universe_index)
    strategy_code = int(strategy_code)

    df_result = get_from_df(universe_index, strategy_code, port_date)
    logger.info(df_result)

    api_result = get_from_api(universe_index, strategy_code, port_date)
    logger.info(api_result)

    assert df_result.T.to_dict() == api_result.T.to_dict()
