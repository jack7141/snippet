from django import forms


class NullBooleanSelect(forms.NullBooleanSelect):
    def format_value(self, value):
        try:
            return {True: '2', False: '3', '2': '2', '3': '3'}[value]
        except KeyError:
            return '1'

    def value_from_datadict(self, data, files, name):
        value = data.get(name)
        return {
            '1': True,
            'true': True,
            'True': True,
            True: True,
            '0': False,
            'false': False,
            'False': False,
            False: False,
        }.get(value)
