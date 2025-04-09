import  datetime


YEAR_REGEX = r'[0-9]{4}'
MONTH_REGEX = r'[0-1]{1}[0-9]{1}'
DAY_REGEX = r'[0-3]{1}[0-9]{1}'


class YearMonthDayConverter:
    regex = f'{YEAR_REGEX}{MONTH_REGEX}{DAY_REGEX}'

    def to_python(self, value):
        return datetime.datetime.strptime(value, '%Y%m%d')

    def to_url(self, value):
        return '%08d' % value
