from django.db import models
from common.behaviors import Timestampable


class AssetUniverse(Timestampable, models.Model):  #FTMR04
    class Meta:
        unique_together = ('year', 'quarter', 'code')
        managed = False

    year = models.CharField(max_length=4, help_text="기준년도")
    quarter = models.CharField(max_length=1, help_text="기준분기")
    code = models.CharField(max_length=12, help_text="중목코드")
    asset_name = models.CharField(max_length=128, help_text="종목명")
    description = models.TextField(help_text="종목설명")

    def __str__(self):
        return f"{self.year}/{self.quarter} AssetUniverse({self.code})"


class RoboAdvisorDesc(Timestampable, models.Model):  #FTMR06(전자적투자조언장치)
    class Meta:
        managed = False

    algorithm_name = models.CharField(max_length=32, help_text="알고리즘명(한글 포함)")
    year = models.CharField(max_length=4, help_text="기준년도")
    quarter = models.CharField(max_length=1, help_text="기준분기")
    strategy_code = models.CharField(max_length=2, help_text="전략구분")

    inception_date = models.DateTimeField(help_text="운용개시일")
    contract_quantity = models.IntegerField(help_text="분기말 기준 일임계약수")
    aum = models.BigIntegerField(help_text="분기말 기준 일임계약수")
    certified_record = models.CharField(max_length=32, help_text="주요경력 및 자격")
    phone = models.CharField(max_length=16, help_text="회사 전화번호")

    def __str__(self):
        return f"{self.year}/{self.quarter} RoboAdvisorDesc({self.algorithm_name})"


class ManagerDetail(Timestampable, models.Model):  #FTMR07(유지보수전문인력)
    class Meta:
        managed = False

    year = models.CharField(max_length=4, help_text="기준년도")
    quarter = models.CharField(max_length=1, help_text="기준분기")
    strategy_code = models.CharField(max_length=2, help_text="전략구분")
    name = models.CharField(max_length=30, help_text="이름(한글)")
    career = models.TextField(help_text="주요경력 및 자격(한글)")
    is_certified = models.CharField(max_length=16, help_text="유지보수 전문인력요건 충족여부(한글)")

    def __str__(self):
        return f"{self.year}/{self.quarter} ManagerDetail({self.name})"


class ManagementReportHeader(Timestampable, models.Model):  # FTMR02
    class Meta:
        unique_together = ('year', 'quarter', 'strategy_code')
        managed = False

    year = models.CharField(max_length=4, help_text="기준년도")
    quarter = models.CharField(max_length=1, help_text="기준분기")
    strategy_code = models.IntegerField(help_text="전략구분")
    strategy = models.TextField(help_text="시장상황 및 투자전략[FTMR02]")

    def __str__(self):
        return f"{self.year}/{self.quarter} ReportHeader({self.strategy_code})"

    def get_ra_desc(self):
        return RoboAdvisorDesc.objects.get(year=self.year, quarter=self.quarter, strategy_code=self.strategy_code)

    def get_manager_details(self):
        return ManagerDetail.objects.filter(year=self.year, quarter=self.quarter, strategy_code=self.strategy_code)

    def get_universe(self):
        return AssetUniverse.objects.filter(year=self.year, quarter=self.quarter)


class ManagementReport(Timestampable, models.Model):  # FTMR01 (분기별 계좌운용정보)
    class Meta:
        unique_together = ('year', 'quarter', 'account_alias_id', )
        managed = False

    year = models.CharField(max_length=4, help_text="기준년도")
    quarter = models.CharField(max_length=1, help_text="기준분기")
    strategy_code = models.IntegerField(help_text="전략구분")
    account_alias_id = models.CharField(max_length=128, blank=False, null=False, help_text="계좌대체번호")
    port_risk_type = models.IntegerField(help_text="포트폴리오 위험 유형")
    qtr_buy_amount = models.DecimalField(max_digits=20, decimal_places=5, help_text="해당 분기 매수금액 합계(원화기준)")
    qtr_sell_amount = models.DecimalField(max_digits=20, decimal_places=5, help_text="해당 분기 매도금액 합계(원화기준)")
    qtr_turnover = models.DecimalField(max_digits=20, decimal_places=5, help_text="해당 분기 매매회전율(원화기준)")
    cum_buy_amount = models.DecimalField(max_digits=20, decimal_places=5, help_text="누적기간 매수금액 합계(원화기준)")
    cum_sell_amount = models.DecimalField(max_digits=20, decimal_places=5, help_text="누적기간 매도금액 합계(원화기준)")
    cum_turnover = models.DecimalField(max_digits=20, decimal_places=5, help_text="누적기간 매매회원율(원화기준)")

    top_holdings_code_1 = models.CharField(null=True, max_length=12, help_text="투자일임재산 평가액 기준 1위 종목코드")
    top_holdings_code_2 = models.CharField(null=True, max_length=12, help_text="투자일임재산 평가액 기준 2위 종목코드")
    top_holdings_code_3 = models.CharField(null=True, max_length=12, help_text="투자일임재산 평가액 기준 3위 종목코드")

    return_3m = models.DecimalField(null=True, max_digits=22, decimal_places=12, help_text="3개월 수익률")
    return_6m = models.DecimalField(null=True, max_digits=22, decimal_places=12, help_text="6개월 수익률")
    return_9m = models.DecimalField(null=True, max_digits=22, decimal_places=12, help_text="9개월 수익률")
    return_12m = models.DecimalField(null=True, max_digits=22, decimal_places=12, help_text="12개월 수익률")
    return_cum = models.DecimalField(max_digits=22, decimal_places=12, help_text="누적 수익률")

    qtr_commission = models.DecimalField(max_digits=20, decimal_places=5, help_text="해당 분기 매매 수수료")
    qtr_tax = models.DecimalField(max_digits=20, decimal_places=5, help_text="해당분기 각종세금(제세금, 배당에 대한 해외 원천세 포함)")
    qtr_other_cost = models.DecimalField(max_digits=20, decimal_places=5, help_text="해당 분기 각종비용(제비용)")
    qtr_total_cost = models.DecimalField(max_digits=20, decimal_places=5, help_text="해당 분기 총비용")
    cum_commission = models.DecimalField(max_digits=20, decimal_places=5, help_text="누적기간 매매수수료")
    cum_tax = models.DecimalField(max_digits=20, decimal_places=5, help_text="누적기간 매매수수료(제세금, 배당에 대한 해외 원천세 포함)")
    cum_other_cost = models.DecimalField(max_digits=20, decimal_places=5, help_text="누적기간 각종비용(제비용)")
    cum_total_cost = models.DecimalField(max_digits=20, decimal_places=5, help_text="누적기간 총비용")
    baseline_date = models.DateTimeField(help_text="정보제공기준일 (default: 분기말, 운용중지: 운용중지 전일)")
    is_published = models.BooleanField(default=False, help_text="발간 여부")

    def get_header(self):
        try:
            strategy_code = 0
            if hasattr(self.account_alias_id, 'extra'):
                strategy_code = getattr(self.account_alias_id.extra, 'strategy_code') or strategy_code
            header = ManagementReportHeader.objects.get(year=self.year, quarter=self.quarter, strategy_code=strategy_code)
        except ManagementReportHeader.DoesNotExist:
            return {}
        return header


class TradingDetail(Timestampable, models.Model):  #FTMR03 (운용내역)
    class Meta:
        managed = False

    year = models.CharField(max_length=4, help_text="기준년도")
    quarter = models.CharField(max_length=1, help_text="기준분기")
    account_alias_id = models.CharField(max_length=128, blank=False, null=False, help_text="계좌대체번호")
    trade_type = models.CharField(max_length=4, help_text="매매구분")
    asset_name = models.CharField(max_length=128, help_text="종목명")
    trade_date = models.DateTimeField(help_text="매매일자")
    shares = models.FloatField(help_text="종목수량")
    trade_price = models.DecimalField(max_digits=20, decimal_places=5, help_text="")
    trade_amount = models.DecimalField(max_digits=20, decimal_places=5, help_text="")
    trade_commission = models.DecimalField(max_digits=20, decimal_places=5, help_text="")
    trade_tax = models.DecimalField(max_digits=20, decimal_places=5, help_text="")


class HoldingDetail(Timestampable, models.Model):  #FTMR05
    class Meta:
        managed = False

    year = models.CharField(max_length=4, help_text="기준년도")
    quarter = models.CharField(max_length=1, help_text="기준분기")
    account_alias_id = models.CharField(max_length=128, blank=False, null=False, help_text="계좌대체번호")
    code = models.CharField(max_length=12, help_text="중목코드")
    asset_name = models.CharField(max_length=128, help_text="종목명")
    shares = models.FloatField(null=True, help_text="종목수량")
    acquisition_price = models.DecimalField(null=True, max_digits=20, decimal_places=5, help_text="취득단가")
    market_price = models.DecimalField(null=True, max_digits=20, decimal_places=5, help_text="시장가격")
    balance = models.DecimalField(max_digits=20, decimal_places=5, help_text="보유잔액")
    weight = models.DecimalField(null=True, max_digits=5, decimal_places=4, help_text="보유비중")
    asset_class_name = models.CharField(max_length=128, help_text="자산군명칭")


class Performance(Timestampable, models.Model):
    class Meta:
        unique_together = ('year', 'quarter', 'account_alias_id')
        managed = False

    year = models.CharField(max_length=4, help_text="기준년도")
    quarter = models.CharField(max_length=1, help_text="기준분기")
    account_alias_id = models.CharField(max_length=128, blank=False, null=False, help_text="계좌대체번호")
    base_amount = models.IntegerField(help_text="투자원금")
    evaluation_amount = models.IntegerField(help_text="평가금액")
    acc_input_amount = models.IntegerField(help_text="누적입금액")
    acc_output_amount = models.IntegerField(help_text="누적출금액")
    acc_gross_loss = models.IntegerField(help_text="누적수익금")
    acc_return = models.DecimalField(help_text="누적수익률", max_digits=8, decimal_places=4)
    period_input_amount = models.IntegerField(help_text="기간출금액")
    period_output_amount = models.IntegerField(help_text="기간출금액")
    period_gross_loss = models.IntegerField(help_text="기간수익")
    period_return = models.DecimalField(help_text="기간수익률", max_digits=8, decimal_places=4)
    annualized_return = models.DecimalField(help_text="연환산수익률", max_digits=8, decimal_places=4, null=True)
    investment_days = models.IntegerField(help_text="투자기간")
    from_date = models.DateTimeField(help_text="조회 시작일")
    to_date = models.DateTimeField(help_text="조회 종료일")
    effective_date = models.DateTimeField(help_text="첫주문 시작일(계약 발효일)")
