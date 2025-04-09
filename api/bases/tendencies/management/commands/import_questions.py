import os
import json
from api.bases.tendencies.models import Type, Question, ScoreRange
from api.bases.tendencies.choices import QuestionChoices
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    args = ''
    help = ('Import tendency question.',)

    def is_valid_exists(self, parser, arg):
        if not os.path.exists(arg):
            parser.error("The file %s does not exist!" % arg)
        else:
            return arg

    def add_arguments(self, parser):
        parser.add_argument('--code', dest='code', default='code', type=str, help='type of code')
        parser.add_argument('--name', dest='name', default='name', type=str, help='type of name')
        parser.add_argument('--description', dest='description', default='description', type=str,
                            help='type of description')
        parser.add_argument('--sep', dest='sep', default='|', type=str, help='type of seperator')
        parser.add_argument('--file', dest='file', type=lambda x: self.is_valid_exists(parser, x), required=True,
                            help='import file path')

    def handle(self, *args, **kwargs):
        file = kwargs['file']

        with open(file, encoding='utf-8') as f:
            data = json.loads(f.read())

            questions = data.get('questions')
            score_ranges = data.get('score_ranges')

            code = kwargs['code']
            name = kwargs['name']
            description = kwargs['description']
            sep = kwargs['sep']

            try:
                instance = Type.objects.create(code=code, name=name, description=description)

                order = 0
                question_instances = []

                for item in questions:
                    text = item.get('question')
                    title = item.get('title', text)
                    options = item.get('options')
                    question_type = item.get('question_type', QuestionChoices.QUESTION_TYPES.select)

                    choices = f'{sep}'.join([option.get('answer') for option in options])
                    scores = f'{sep}'.join([str(option.get('score')) for option in options])

                    question_instances.append(
                        Question(order=order,
                                 title=title,
                                 text=text,
                                 question_type=question_type,
                                 separator_type=sep,
                                 choices=choices,
                                 scores=scores,
                                 type=instance)
                    )

                    order += 1

                ScoreRange.objects.bulk_create([ScoreRange(**item, type=instance) for item in score_ranges])
                Question.objects.bulk_create(question_instances)
            except Exception as e:
                if instance:
                    instance.delete()
