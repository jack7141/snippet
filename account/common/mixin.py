class AccountBasePostProcessMixin(object):
    @staticmethod
    def check_abnormal_status(trade):
        """비정상 거래 내역 검출 함수
        1. 거래 내역 에서 (대체 출고 AND 달러 거래) 시 체결 금액 누락 체크
        """
        if trade['j_name'] == '대체 출고' and trade['currency_name'] == 'USD':
            return 'export_stock_with_usd'

    def process_export_stock_with_usd(self, trades, executions):

        exec_won_price = 0

        for exec_item in executions:
            if exec_item['code_name'] in trades['stock_name']:
                exec_won_price += int(exec_item['exec_qty'] *
                                      exec_item['exec_price'] *
                                      round(exec_item['exchange_rate'], 4))

        return exec_won_price


class AccountBaseCalculateMixin(object):
    @staticmethod
    def get_solution_for_execution(trade, executions):
        if executions:
            return 'calculate_with_executions'

        if trade['currency_name'] == 'USD':
            return 'calculate_usd_with_empty_executions'

        return 'calculate_kr_with_empty_executions'

    def calculate_with_executions(self, trade, executions):
        exec_won_price = 0

        for exec_item in executions:
            price = int(exec_item['exec_qty'] *
                                  exec_item['exec_price'] *
                                  round(exec_item['exchange_rate'], 4))

            if '매수' in exec_item['trade_sec_name']:
                exec_won_price += price
            elif '매도' in exec_item['trade_sec_name']:
                exec_won_price -= price

        return exec_won_price

    def calculate_usd_with_empty_executions(self, trade, executions):
        return 0

    def calculate_kr_with_empty_executions(self, trade, executions):
        quantity = str(trade['quantity']).replace(',', '')
        if not quantity:
            return 0

        return round(float(quantity))
