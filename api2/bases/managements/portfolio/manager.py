import pandas as pd


class PortfolioManager:
    def __init__(self, price_engine, portfolio):
        if isinstance(portfolio, list):
            self._portfolio = pd.DataFrame(portfolio).sort_values(
                by="weight", ascending=False
            )
        elif isinstance(portfolio, pd.DataFrame):
            self._portfolio = portfolio.sort_values(by="weight", ascending=False)
        else:
            raise TypeError("Unsupported portfolio type")
        self._price_engine = price_engine

    @property
    def model_portfolio(self):
        return self._portfolio.set_index("code")

    @model_portfolio.setter
    def model_portfolio(self, portfolio: pd.DataFrame):
        self._portfolio = portfolio

    @staticmethod
    def calc_slippage(optimal_portfolio: pd.DataFrame, current_portfolio: pd.DataFrame):
        portfolio_slippage = pd.DataFrame(
            {"weight": 0}, index=optimal_portfolio.index.union(current_portfolio.index)
        )
        portfolio_slippage.loc[
            optimal_portfolio.index, "weight"
        ] += optimal_portfolio.weight
        portfolio_slippage.loc[
            current_portfolio.index, "weight"
        ] -= current_portfolio.weight
        return portfolio_slippage

    def is_rebalancing_condition_met(
        self, current_portfolio, rebalancing_portfolio, slippage_threshold=0.05
    ) -> bool:
        """
        |RP - CP| > a

        :param
        current_portfolio: Current portfolio in Account
        rebalancing_portfolio: Orderable Portfolio
        slippage_threshold:

        :return: bool
        """
        portfolio_slippage = self.calc_slippage(
            optimal_portfolio=rebalancing_portfolio, current_portfolio=current_portfolio
        )
        reb_deposit_ratio = 1 - rebalancing_portfolio.weight.sum()
        cur_deposit_ratio = 1 - current_portfolio.weight.sum()
        deposit_ratio_gap = abs(reb_deposit_ratio - cur_deposit_ratio)
        is_asset_disparate = (
            portfolio_slippage.weight.abs() > slippage_threshold
        ).any()
        is_deposit_disparate = deposit_ratio_gap > slippage_threshold
        return is_deposit_disparate or is_asset_disparate

    def calc_rebalancing_portfolio(
        self, max_ord_base, asset_prices, emphasis="optimized_deposit"
    ):
        optimal_portfolio = self.model_portfolio[self.model_portfolio.weight > 0].copy()
        krw_asset_price = asset_prices.krw_price
        universe_asset_krw_price = krw_asset_price.loc[
            krw_asset_price.index.intersection(optimal_portfolio.index)
        ]

        optimal_shares = self._price_engine.calc_optimal_shares(
            base=max_ord_base,
            optimal_weight=optimal_portfolio.weight,
            universe_asset_price=universe_asset_krw_price,
        )
        optimal_portfolio.loc[:, "shares"] = optimal_shares

        rebalancing_portfolio = pd.DataFrame(
            columns=["weight", "shares"], index=optimal_portfolio.index
        )
        emphasis_func = getattr(self._price_engine, f"emphasis_{emphasis}")

        rebalancing_portfolio.loc[:, "shares"] = emphasis_func(
            model_portfolio=self.model_portfolio,
            universe_asset_price=universe_asset_krw_price,
            optimal_shares=optimal_shares,
            input_amount=max_ord_base,
        )
        rebalancing_portfolio.loc[:, "weight"] = (
            krw_asset_price[rebalancing_portfolio.index]
            * rebalancing_portfolio.loc[:, "shares"]
            / max_ord_base
        )
        return rebalancing_portfolio

    @staticmethod
    def get_summary(
        model_portfolio, rebalancing_portfolio, current_portfolio
    ) -> pd.DataFrame:
        summary_index = current_portfolio.index.union(
            model_portfolio.index.union(rebalancing_portfolio.index)
        )
        summary = pd.DataFrame(
            {
                "current_weight": 0,
                "reb_weight": 0,
                "mp_weight": 0,
                "target_shares": 0,
                "CP-RP": 0,
                "CP-MP": 0,
            },
            index=summary_index,
        )
        summary.loc[
            current_portfolio.index, "current_weight"
        ] = current_portfolio.weight
        summary.loc[
            rebalancing_portfolio.index, "reb_weight"
        ] = rebalancing_portfolio.weight
        summary.loc[model_portfolio.index, "mp_weight"] = model_portfolio.weight
        summary.loc[
            rebalancing_portfolio.index, "target_shares"
        ] = rebalancing_portfolio.shares
        summary.loc[:, "CP-RP"] = summary.current_weight - summary.reb_weight
        summary.loc[:, "CP-MP"] = summary.current_weight - summary.mp_weight
        return summary
