import os
import io


class Words:
    __folder = os.path.dirname(os.path.realpath(__file__))

    with io.open(os.path.join(__folder, 'words', 'kr.txt'), 'r', encoding="utf-8") as texts:
        WORDS = texts.read().split()

    with io.open(os.path.join(__folder, 'words', 'kr_prev.txt'), 'r', encoding="utf-8") as texts:
        WORDS_PREV = texts.read().split()


class AuthenticationChoices:
    AUTH_TYPES = (
        ('1', 'sms'),
        ('2', 'accounts'),
        ('3', 'ars'),
        ('4', 'owner')
    )