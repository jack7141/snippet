import logging
from collections import deque

import numpy as np
import pandas as pd

from common.exceptions import PreconditionFailed

logger = logging.getLogger(__name__)


class OrderPriceEngine:
    @staticmethod
    def calc_prices(series, strategies, price_strategy="sell"):
        """
        전략적 매도/매수 금액 산정
        """
        percent = 1 + strategies.ticks[price_strategy + "_pct"]
        tick = strategies.ticks[price_strategy] * 0.01

        return series.apply(lambda x: np.floor(((x * percent) + tick) * 100) / 100)

    @staticmethod
    def calc_total_transaction_cost(
        new_shares: pd.Series, krw_price: pd.Series, transaction_cost_ratio=0.0025
    ):
        transaction_cost = (
            new_shares.abs() * krw_price.loc[new_shares.index]
        ) * transaction_cost_ratio
        return transaction_cost.sum()

    @staticmethod
    def calc_order_price(order_book_row: pd.Series, strategies):
        """
        전략적 매도/매수 금액 산정
        """

        price = order_book_row["market_price"]
        price_strategy = order_book_row["price_strategy"]

        percent = 1 + strategies.ticks[price_strategy + "_pct"]
        tick = strategies.ticks[price_strategy] * 0.01
        return np.floor(((price * percent) + tick) * 100) / 100

    @staticmethod
    def calc_optimal_shares(base: float, optimal_weight, universe_asset_price):
        if not (universe_asset_price > 0).all():
            raise PreconditionFailed(
                f"Price validation error price must be greater than 0, "
                f"{universe_asset_price[universe_asset_price <= 0]}"
            )
        optimal_shares = (optimal_weight * base) / universe_asset_price
        return optimal_shares.copy()

    @staticmethod
    def emphasis_optimized_deposit(
        universe_asset_price, optimal_shares, input_amount, **kwargs
    ):
        def calc_rest_if_buy(input, share, price):
            return input - (share * price)

        def cost_function(mp_shares, poss_shares):
            price_weighted_share_gaps = universe_asset_price * (mp_shares - poss_shares)
            return price_weighted_share_gaps.sum()

        if universe_asset_price.empty:
            raise PreconditionFailed("Price data is empty")

        universe_asset_price = universe_asset_price.loc[optimal_shares.index]
        order_poss_shares = optimal_shares.astype(int)
        queue = deque()
        queue.append(
            [
                0,
                [order_poss_shares[0]],
                calc_rest_if_buy(
                    input=input_amount,
                    share=order_poss_shares[0],
                    price=universe_asset_price[0],
                ),
            ]
        )
        queue.append(
            [
                0,
                [order_poss_shares[0] + 1],
                calc_rest_if_buy(
                    input=input_amount,
                    share=order_poss_shares[0] + 1,
                    price=universe_asset_price[0],
                ),
            ]
        )

        min_cost = input_amount
        opt_shares = order_poss_shares

        while queue:
            idx, _share, rest = queue.popleft()

            if rest < 0:
                pass

            elif len(_share) < len(order_poss_shares):
                queue.append(
                    [
                        idx + 1,
                        _share + [order_poss_shares[idx + 1]],
                        calc_rest_if_buy(
                            input=rest,
                            share=order_poss_shares[idx + 1],
                            price=universe_asset_price[idx + 1],
                        ),
                    ]
                )
                queue.append(
                    [
                        idx + 1,
                        _share + [order_poss_shares[idx + 1] + 1],
                        calc_rest_if_buy(
                            input=rest,
                            share=order_poss_shares[idx + 1] + 1,
                            price=universe_asset_price[idx + 1],
                        ),
                    ]
                )

            if len(_share) == len(order_poss_shares):
                _share = pd.Series(_share, index=optimal_shares.index)
                _cost = cost_function(mp_shares=optimal_shares, poss_shares=_share)

                if rest > 0 and _cost < min_cost:
                    min_cost = _cost
                    min_rest = rest
                    opt_shares = _share

        if (opt_shares < 0).any() or (opt_shares == 0).all():
            raise PreconditionFailed(
                f"unexpected calc shares: {opt_shares.to_string()}"
            )
        return opt_shares

    @staticmethod
    def emphasis_weight_first(
        model_portfolio, universe_asset_price, optimal_shares, input_amount, **kwargs
    ):
        # initialize variables, we will update s_qty to make ideal position
        s_qty = optimal_shares.astype(int)
        # shorten time when partial withdraw
        cheapest_asset_price = universe_asset_price[model_portfolio.index].min()
        if input_amount < cheapest_asset_price:
            return s_qty

        # mp floating point error defense logic
        s_mp = model_portfolio.weight
        s_mp = s_mp[s_mp > 0.0001]
        assert round(s_mp.sum(), 5) == 1
        s_mp = s_mp / s_mp.sum()

        # have negative value with astpye(int) when the INVEST_AMT is a very large numbe
        left_amt = input_amount - sum(s_qty * universe_asset_price[s_qty.index])
        if cheapest_asset_price > left_amt:
            return s_qty

        # prioritize items by score and weight difference
        df_priority = pd.DataFrame(
            {"wgt": s_mp, "px": universe_asset_price[s_mp.index]},
            index=s_mp.index,
            columns=["wgt", "px"],
        )
        df_priority = df_priority.sort_values(
            by=["wgt", "px"], ascending=[False, False]
        ).fillna(0)
        sorted_tickers = df_priority.index.tolist()

        # round up items following priority
        for ticker in sorted_tickers:
            if cheapest_asset_price > left_amt:
                break

            if left_amt - universe_asset_price[ticker] < 0:
                continue

            s_qty[ticker] += 1
            left_amt -= universe_asset_price[ticker]
        return s_qty.dropna()

    @staticmethod
    def emphasis_strict_ratio(
        model_portfolio, current_portfolio, input_amount, universe_asset_price, **kwargs
    ):
        """
        비중 우선 계산
        :param df: 포트폴리오(pd.DataFrame)
        :return: pd.DataFrame
        """
        portfolio_df = model_portfolio.copy()
        current_portfolio_map = current_portfolio.to_dict()
        krw_price_map = universe_asset_price.to_dict()

        for index, row in portfolio_df.iterrows():
            max_ord_price = np.floor(
                input_amount * row["weight"]
            ) - current_portfolio_map["buy_price"].get(index, 0)
            portfolio_df.loc[index, "new_shares"] = np.floor(
                max_ord_price / krw_price_map.get(index)
            )

            if max_ord_price < 0:
                portfolio_df.loc[index, "new_shares"] = -(
                    current_portfolio_map["shares"].get(
                        index, -portfolio_df.loc[index, "new_shares"]
                    )
                )

            portfolio_df.loc[index, "buy_price"] = current_portfolio_map[
                "buy_price"
            ].get(index, 0) + portfolio_df.loc[index, "new_shares"] * krw_price_map.get(
                index, 0
            )
            portfolio_df.loc[index, "shares"] = (
                current_portfolio_map["shares"].get(index, 0)
                + portfolio_df.loc[index, "new_shares"]
            )
        return portfolio_df["shares"]

    @staticmethod
    def emphasis_min_deposit(
        model_portfolio,
        current_portfolio,
        input_amount,
        universe_asset_price,
        allow_minus_gross=True,
        **kwargs,
    ):
        """
        예수금 최소화 우선 계산
        :param portfolio_df: 포트폴리오(pd.DataFrame)
        :return: pd.DataFrame
        """
        portfolio_df = model_portfolio.copy()
        rest = 0
        tot_buy_price = current_portfolio["buy_price"].sum()

        # TODO UPDATE flag to order_router sell & buy at once
        is_poss_ord = tot_buy_price < input_amount

        current_portfolio_map = current_portfolio.to_dict()
        krw_price_map = universe_asset_price.to_dict()
        for index, row in portfolio_df.iterrows():
            prev_buy_price = current_portfolio_map["buy_price"].get(index, 0)
            portfolio_df.loc[index, "shares"] = current_portfolio_map["shares"].get(
                index, 0
            )
            asset_krw_price = universe_asset_price[index]

            if row["weight"] == 0:
                portfolio_df.loc[index, "max_ord_price"] = -prev_buy_price
                portfolio_df.loc[index, "buy_price"] = prev_buy_price
                portfolio_df.loc[index, "new_shares"] = -portfolio_df.loc[
                    index, "shares"
                ]
                portfolio_df.loc[index, "shares"] = 0
                portfolio_df.loc[index, "ratio"] = 0
            elif is_poss_ord or allow_minus_gross:
                portfolio_df.loc[index, "org_max_ord_price"] = np.floor(
                    input_amount * row["weight"]
                )
                max_ord_price = (
                    np.floor(input_amount * row["weight"]) - prev_buy_price + rest
                )
                new_shares = np.floor(max_ord_price / krw_price_map.get(index))
                buy_price = prev_buy_price + (new_shares * asset_krw_price)

                portfolio_df.loc[index, "max_ord_price"] = max_ord_price
                portfolio_df.loc[index, "new_buy_price"] = new_shares * asset_krw_price
                portfolio_df.loc[index, "new_shares"] = new_shares
                portfolio_df.loc[index, "buy_price"] = buy_price
                portfolio_df.loc[index, "ratio"] = buy_price / input_amount
                portfolio_df.loc[index, "shares"] = (
                    portfolio_df.loc[index, "shares"] + new_shares
                )

                rest = max_ord_price - (new_shares * universe_asset_price[index])
                portfolio_df.loc[index, "rest"] = rest
            else:
                portfolio_df.loc[index, "max_ord_price"] = prev_buy_price
                portfolio_df.loc[index, "buy_price"] = prev_buy_price
                portfolio_df.loc[index, "new_shares"] = 0
                portfolio_df.loc[index, "shares"] = portfolio_df.loc[index, "shares"]
                portfolio_df.loc[index, "ratio"] = prev_buy_price / tot_buy_price
        return portfolio_df["shares"]
