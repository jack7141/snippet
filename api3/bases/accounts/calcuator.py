import logging

import pandas as pd
import requests as req
from django.apps import apps
from django.conf import settings
from math import floor

from common.mixin import AccountBaseCalculateMixin

logger = logging.getLogger('django.server')


def str_to_number(str_num: str, type_cls=float):
    try:
        str_num = str(str_num).replace(',', '')
        if not str_num:
            return 0

        if type_cls != float:
            str_num = float(str_num)
        return type_cls(str_num)
    except ValueError as e:
        logger.warning(f"ValueError:{str(e)}")
        return 0


class BaseAmountCalculator(AccountBaseCalculateMixin):
    def __init__(self, trade_df, acct=None):
        self.acct = acct
        self.amount_func_map = {
            'INPUT': lambda x: str_to_number(x['trd_amt'], int),
            'OUTPUT': lambda x: str_to_number(x['trd_amt'], int),
            'INPUT_USD': lambda x: int(str_to_number(x['for_amt_r'], float) * str_to_number(x['ex_chg_rate'] or 0, float)),
            'OUTPUT_USD': lambda x: int(str_to_number(x['for_amt_r'], float) * str_to_number(x['ex_chg_rate'] or 0, float)),
            'IMPORT': lambda x: str_to_number(x['trd_p'], float) * str_to_number(x['quantity'], int) if x['trd_p'] else self.get_amount_from_execution(trade=x),
            'EXPORT': lambda x: str_to_number(x['trd_p'], float) * str_to_number(x['quantity'], int) if x['trd_p'] else self.get_amount_from_execution(trade=x),
            'DIVIDEND_INPUT': lambda x: str_to_number(x['for_amt_r'], float),
            'DIVIDEND_OUTPUT': lambda x: str_to_number(x['for_amt_r'], float),
            'OVERSEA_TAX': lambda x: str_to_number(x['for_amt_r'], float),
            'OVERSEA_TAX_REFUND': lambda x: str_to_number(x['for_amt_r'], float),
    }
        self.df = trade_df
        SumUp = apps.get_model(app_label='accounts', model_name='SumUp')
        self.j_name_map = SumUp.get_amount_func_types(SumUp.objects.exclude(amount_func_type__isnull=True))

    def resample(self, row, *args, **kwargs):
        if row.empty:
            return row
        pivoted = row.pivot(columns='category', values='amt')
        pivoted.name = 'amt'
        return pd.Series(pivoted.sum(axis=0).to_dict())

    def classify_category(self, row: pd.Series):
        _amt = 0
        for k, v in self.j_name_map.items():
            if row['j_name'] in v:
                if k in self.amount_func_map:
                    _amt = self.amount_func_map[k](row)
                return pd.Series({'category': k,
                                  'currency_name': row.get('currency_name', None) or 'KRW',
                                  'amt': _amt})
        return pd.Series({'category': None,
                          'currency_name': None,
                          'amt': _amt})

    def classify(self):
        if self.df.index.name != 'trd_date':
            classified = self.df.set_index('trd_date')
        else:
            classified = self.df.copy()
        classified = classified.apply(self.classify_category, axis=1)
        if classified.empty:
            classified = pd.DataFrame(columns=['amt', 'category'])
        classified.amt.fillna(0, inplace=True)
        classified.index = pd.to_datetime(classified.index)
        return classified

    def calculate(self):
        classified = self.df.apply(self.classify_category, axis=1)
        if classified.empty:
            classified = pd.DataFrame(columns=['amt', 'category'])
        classified.amt.fillna(0, inplace=True)
        summed_amount = classified.groupby(by=['category']).sum()['amt']
        summed_amount = summed_amount.dropna()

        base_dic = {
            'input_amt': int(summed_amount.get('INPUT', 0) or 0),  # deposit
            'output_amt': int(summed_amount.get('OUTPUT', 0) or 0),  # withdraw
            'input_usd_amt': int(summed_amount.get('INPUT_USD', 0) or 0),  # remit usd
            'output_usd_amt': int(summed_amount.get('OUTPUT_USD', 0) or 0),  # remit usd
            'dividend_input_amt': summed_amount.get('DIVIDEND_INPUT', 0) or 0,  # dividend input
            'oversea_tax_amt': summed_amount.get('OVERSEA_TAX', 0) or 0,  # dividend tax
            'dividend_output_amt': summed_amount.get('DIVIDEND_OUTPUT', 0) or 0,  # dividend input
            'oversea_tax_refund_amt': summed_amount.get('OVERSEA_TAX_REFUND', 0) or 0,  # dividend tax
            'stock_import_amt': summed_amount.get('IMPORT', 0),
            "stock_export_amt": summed_amount.get('EXPORT', 0),
            "stock_transfer_amt": 0,
            'base_changed': 0,
            'base': 0,
            'dividend': 0,
        }

        # INPUT = INPUT_KRW + INPUT_USD
        # OUTPUT = OUTPUT_KRW + OUTPUT_USD
        base_dic['input_amt'] += base_dic['input_usd_amt']
        base_dic['output_amt'] += base_dic['output_usd_amt']

        # TRANSFER_AMT = STOCK_IMPORT_AMT - STOCK_EXPORT_AMT
        base_dic['stock_transfer_amt'] = base_dic['stock_import_amt'] - base_dic['stock_export_amt']

        # BASE = INPUT - OUTPUT + TRANSFER_AMT
        base_dic['base'] = base_dic['input_amt'] - base_dic['output_amt'] + base_dic['stock_transfer_amt']
        base_dic['base_changed'] = base_dic['input_amt'] - base_dic['output_amt'] + base_dic['stock_transfer_amt']
        pretax_dividend = base_dic['dividend_input_amt'] - base_dic['dividend_output_amt']
        dividend_tax = base_dic['oversea_tax_amt'] - base_dic['oversea_tax_refund_amt']
        base_dic['dividend'] = pretax_dividend - dividend_tax

        for key, value in base_dic.items():
            base_dic[key] = round(value, 4)
        return base_dic

    def get_amount_from_execution(self, trade):
        # From DB
        filter_kwargs = {
            'code_name': trade['stock_name'],
            'order_status': '체결'
        }
        queryset = self.acct.execution_set.filter(**filter_kwargs)
        executions = list(queryset.values())

        solution = self.get_solution_for_execution(trade, executions)
        solution_func = getattr(self, solution)
        return int(solution_func(trade, executions))


    def asset_prev_calculate(self) -> dict:
        """타겟 계좌의 Trade 모델 적요를 이용하여, 전일자 예수금을 계산합니다.
        """
        EXCLUSION_LIST = ['DIVIDEND_INPUT', 'DIVIDEND_OUTPUT', 'OVERSEA_TAX', 'OVERSEA_TAX_REFUND']
        OUTPUT_LIST = ['OUTPUT', 'OUTPUT_USD', 'EXPORT']

        prev_dic = {row['trd_date']: 0 for row in self.df}

        for row in self.df:
            _amt = 0
            for key, values in self.j_name_map.items():
                if row['j_name'] not in values or \
                        key in EXCLUSION_LIST or \
                        key not in self.amount_func_map:
                    continue

                _amt = self.amount_func_map[key](row)

                if key in OUTPUT_LIST:
                    prev_dic[row['trd_date']] += -_amt
                else:
                    prev_dic[row['trd_date']] += _amt

        return prev_dic


class CheckBaseAmountCalculator(AccountBaseCalculateMixin, BaseAmountCalculator):
    def __init__(self, acct, trade_df):
        super().__init__(trade_df)
        self.acct = acct
        self.amount_func_map = {
            'INPUT': lambda x: str_to_number(x['trd_amt'], int),
            'OUTPUT': lambda x: str_to_number(x['trd_amt'], int),
            'INPUT_USD': lambda x: int(str_to_number(x['for_amt_r'], float) * str_to_number(x['ex_chg_rate'] or 0, float)),
            'OUTPUT_USD': lambda x: int(str_to_number(x['for_amt_r'], float) * str_to_number(x['ex_chg_rate'] or 0, float)),
            'IMPORT': lambda x: str_to_number(x['trd_p'], float) * str_to_number(x['quantity'], int) if x['trd_p'] else self.get_amount_from_execution(trade=x),
            'EXPORT': lambda x: str_to_number(x['trd_p'], float) * str_to_number(x['quantity'], int) if x['trd_p'] else self.get_amount_from_execution(trade=x),
            'DIVIDEND_INPUT': lambda x: str_to_number(x['for_amt_r'], float),
            'DIVIDEND_OUTPUT': lambda x: str_to_number(x['for_amt_r'], float),
            'OVERSEA_TAX': lambda x: str_to_number(x['for_amt_r'], float),
            'OVERSEA_TAX_REFUND': lambda x: str_to_number(x['for_amt_r'], float),
        }


    def get_amount_from_execution(self, trade):
        # From DB
        filter_kwargs = {
            'code_name': trade['stock_name'],
            'order_status': '체결'
        }
        queryset = self.acct.execution_set.filter(**filter_kwargs)
        executions = list(queryset.values())

        solution = self.get_solution_for_execution(trade, executions)
        solution_func = getattr(self, solution)
        return int(solution_func(trade, executions))
