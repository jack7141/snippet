import os
import json
from api.bases.tendencies.models import Type, Response, Answer
from api.bases.tendencies.utils import validate_score
from django.core.management.base import BaseCommand
import pandas as pd


# Note. 일회용 마이그레이션 코드
# Pandas version 1.0.1 이상 필요 (requirements 파일에는 미포함)
# xlrd or openpyxl 라이브러리 필요함

class Command(BaseCommand):
    args = ''
    help = ('Migrate tendency responses.',)

    def is_valid_exists(self, parser, arg):
        if not os.path.exists(arg):
            parser.error("The file %s does not exist!" % arg)
        else:
            return arg

    def add_arguments(self, parser):
        parser.add_argument('--code', dest='code', default='v3', type=str, help='type of code')
        parser.add_argument('--file', dest='file', type=lambda x: self.is_valid_exists(parser, x), required=True,
                            help='import file path')

    def handle(self, *args, **kwargs):
        code = kwargs['code']
        target_code = f'fount_{code}' if code != 'v3' else 'fount'
        type_instance = Type.objects.get(code=target_code)
        questions = type_instance.questions.all().order_by('order')
        file = kwargs['file']
        df = pd.read_excel(file)

        def function(row):
            try:
                version = row.version

                if version == 'v1':
                    score, result = validate_score(json.loads(row.result))
                elif version == 'v2':
                    result = json.loads(row.result)
                elif version == 'v3':
                    result = json.loads(row.result)

                return result
            except:
                return None

        df['new_result'] = df.apply(lambda x: function(x), axis=1)

        target_answers = df[df['version'] == code]

        def generator(x):
            answers = x['new_result']
            errors = []
            for item in questions:
                if not item.check_answer(answers[item.order], answer_type='index'):
                    errors.append({
                        'answer_no': int(item.order),
                        'question': item.text,
                        'available_choices': item.choices,
                        'answer': answers[item.order]
                    })

            if not errors:
                instance = Response.objects.create(user_id=x['user_id'], type=type_instance)
                try:
                    Answer.objects.bulk_create(
                        [Answer(
                            question=question,
                            answer=question.get_answer(answers[question.order], answer_type='index'),
                            score=question.get_score(answers[question.order], answer_type='index'),
                            response=instance) for question in
                            questions
                        ])
                    instance.update_score()
                    print(x['user_id'])

                    return True
                except Exception as e:
                    instance.delete()
                    print('Exception!!!', e)
                    return False

        target_answers['res'] = target_answers.apply(lambda x: generator(x), axis=1)
