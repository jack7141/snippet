from dataclasses import dataclass, field

from common.utils import DotDict
from common.exceptions import PreconditionFailed


@dataclass
class Answer:
    NO_SELECT = -1
    FOUNT_ANSWER = DotDict({
        'NO': 0,
        'YES': 1,
        'A': 0,
        'B': 1,
        'C': 2,
        'D': 3,
        'E': 4,
        'F': 5,
        'G': 6
    })
    SH_ANSWER = DotDict({
        'NO': 0,
        'YES': 1,
        'A': 1,
        'B': 2,
        'C': 3,
        'D': 4,
        'E': 5,
        'F': 6,
        'G': 7,
    })

    KB_ANSWER = DotDict({
        'YES': 0,
        'NO': 1,

        'A': 1,
        'B': 2,
        'C': 3,
        'D': 4,
        'E': 5,
        "FOR_0M": "0000",
        "FOR_6M": "0006",
        "FOR_1Y6M": "0106",
        "FOR_3Y": "0300"
    })

    no: int
    mapping: dict = field(default_factory=dict)
    desc: str = field(default='')
    data_type: type = field(default=str)

    def get_mapped_answer(self, idx, answer):
        if self.data_type is list:
            if answer == self.NO_SELECT:
                answer = []
            elif isinstance(answer, list):
                answer = [self.mapping.get(a) for a in answer]
            else:
                raise PreconditionFailed(f"Unsupported answer(idx={idx}, answer={answer})")
        else:
            mapped = self.mapping.get(answer)
            if mapped is not None:
                answer = mapped

        return answer


class TendencyMaps:
    INPUT_LENGTH = -1
    MAPPED_LENGTH = -1
    order_maps = {}

    @classmethod
    def do_mapping(cls, responses):
        mapped_responses = [Answer.NO_SELECT for _ in range(cls.MAPPED_LENGTH)]
        for vendor, _map in cls.order_maps.items():
            _source_answers = responses.get(vendor, [])

            for idx, _ans in enumerate(_source_answers, start=1):
                if idx in _map:
                    answer_instance = _map[idx]
                    tgt_idx = answer_instance.no - 1
                    mapped_responses[tgt_idx] = answer_instance.get_mapped_answer(idx=idx, answer=_ans)
        return mapped_responses


class KBTendencyMaps(TendencyMaps):
    INPUT_LENGTH = 9
    MAPPED_LENGTH = 15
    kb_default_answer_maps = {
        Answer.FOUNT_ANSWER.A: Answer.KB_ANSWER.A,
        Answer.FOUNT_ANSWER.B: Answer.KB_ANSWER.B,
        Answer.FOUNT_ANSWER.C: Answer.KB_ANSWER.C,
        Answer.FOUNT_ANSWER.D: Answer.KB_ANSWER.D,
        Answer.FOUNT_ANSWER.E: Answer.KB_ANSWER.E,
    }

    # IDX TO ORDERED ANSWER
    order_maps = {
        "fount": {
            5: Answer(no=1, desc='FT:5(나이)', mapping=kb_default_answer_maps),
            4: Answer(no=2, desc='FT:4(투자예정기간)', mapping=kb_default_answer_maps),
            6: Answer(no=4, desc='FT:6(재산상황/월소득)', mapping=kb_default_answer_maps),
            7: Answer(no=6, mapping={Answer.FOUNT_ANSWER.A: Answer.KB_ANSWER.A,
                                     Answer.FOUNT_ANSWER.B: Answer.KB_ANSWER.A,
                                     Answer.FOUNT_ANSWER.C: Answer.KB_ANSWER.B,
                                     Answer.FOUNT_ANSWER.D: Answer.KB_ANSWER.C,
                                     Answer.FOUNT_ANSWER.E: Answer.KB_ANSWER.E},
                      desc='FT:7(재산상황/총 자산대비 금융자산의 비중)'),
            2: Answer(no=11, mapping={Answer.FOUNT_ANSWER.A: Answer.KB_ANSWER.C,
                                      Answer.FOUNT_ANSWER.B: Answer.KB_ANSWER.B,
                                      Answer.FOUNT_ANSWER.C: Answer.KB_ANSWER.A},
                      desc='FT:2(투자목적)'),
            3: Answer(no=13, desc='FT:3(감내할 수 있는 손실 수준)', mapping=kb_default_answer_maps)
        },
        "kb": {
            7: Answer(no=3, desc='KB:7(소득상태)', mapping=kb_default_answer_maps),
            5: Answer(no=5, desc='KB:5(재산상황/여유자금)', mapping=kb_default_answer_maps),
            6: Answer(no=7, desc='KB:6(재산상황/금융자산 비중)', mapping=kb_default_answer_maps),
            3: Answer(no=8, desc='KB:3(투자경험/상품)', mapping=kb_default_answer_maps),
            4: Answer(no=9, desc='KB:4(투자경험/기간)', mapping=kb_default_answer_maps),
            2: Answer(no=10, mapping={
                Answer.FOUNT_ANSWER.A: Answer.KB_ANSWER.FOR_0M,
                Answer.FOUNT_ANSWER.B: Answer.KB_ANSWER.FOR_6M,
                Answer.FOUNT_ANSWER.C: Answer.KB_ANSWER.FOR_1Y6M,
                Answer.FOUNT_ANSWER.D: Answer.KB_ANSWER.FOR_3Y},
                      desc='KB:2(파생상품 투자기간)'),
            1: Answer(no=12, desc='KB:1(금융 지식 수준/이해도)', mapping=kb_default_answer_maps),
            8: Answer(no=14, desc='KB:8(취약 금융소비자 확인)', mapping={
                Answer.FOUNT_ANSWER.A: Answer.KB_ANSWER.YES,
                Answer.FOUNT_ANSWER.B: Answer.KB_ANSWER.NO,
            }),
            9: Answer(no=15, desc='KB:9(투자자정보 유효기간 설정 동의)', mapping={
                Answer.FOUNT_ANSWER.YES: Answer.KB_ANSWER.YES,
                Answer.FOUNT_ANSWER.NO: Answer.KB_ANSWER.NO,
            }),
        }
    }


class SHTendencyMaps(TendencyMaps):
    INPUT_LENGTH = 11
    MAPPED_LENGTH = 15  # Vendor 전달항목 수

    INVESTMENT_EXPERIENCE_FLAG_IDX = 8

    shinhan_default_answer_maps = {
        Answer.FOUNT_ANSWER.A: Answer.SH_ANSWER.A,
        Answer.FOUNT_ANSWER.B: Answer.SH_ANSWER.B,
        Answer.FOUNT_ANSWER.C: Answer.SH_ANSWER.C,
        Answer.FOUNT_ANSWER.D: Answer.SH_ANSWER.D,
        Answer.FOUNT_ANSWER.E: Answer.SH_ANSWER.E,
        Answer.FOUNT_ANSWER.F: Answer.SH_ANSWER.F,
        Answer.FOUNT_ANSWER.G: Answer.SH_ANSWER.G,
    }

    order_maps = {  # idx TO Answer
        "fount": {
            7: Answer(no=2, desc='FT:7(투자자금의 비중)', mapping=shinhan_default_answer_maps),
            2: Answer(no=10, desc='FT:2(투자 수익 및 위험에 대한 태도)', mapping=shinhan_default_answer_maps),
            3: Answer(no=11, desc='FT:3(기대수익률 및 손실감내도)', mapping=shinhan_default_answer_maps),
        },
        "shinhan": {
            9: Answer(no=1, mapping={
                Answer.FOUNT_ANSWER.A: Answer.SH_ANSWER.C,
                Answer.FOUNT_ANSWER.B: Answer.SH_ANSWER.B,
                Answer.FOUNT_ANSWER.C: Answer.SH_ANSWER.A,
            }, desc='SH:4(소득상태)'),
            2: Answer(no=3, mapping={
                Answer.FOUNT_ANSWER.B: Answer.SH_ANSWER.A,
                Answer.FOUNT_ANSWER.C: Answer.SH_ANSWER.B,
                Answer.FOUNT_ANSWER.D: Answer.SH_ANSWER.C,
                Answer.FOUNT_ANSWER.E: Answer.SH_ANSWER.D
            }, desc='SH:2-A-1(투자경험A-1)', data_type=list),
            3: Answer(no=4, desc='SH:2-A-2(투자경험A-2)', mapping=shinhan_default_answer_maps),
            4: Answer(no=5, mapping={
                Answer.FOUNT_ANSWER.B: Answer.SH_ANSWER.A,
                Answer.FOUNT_ANSWER.C: Answer.SH_ANSWER.B,
                Answer.FOUNT_ANSWER.D: Answer.SH_ANSWER.C,
                Answer.FOUNT_ANSWER.E: Answer.SH_ANSWER.D,
                Answer.FOUNT_ANSWER.F: Answer.SH_ANSWER.E,
                Answer.FOUNT_ANSWER.G: Answer.SH_ANSWER.F
            }, desc='SH:2-B-1(투자경험B-1)', data_type=list),
            5: Answer(no=6, desc='SH:2-B-2(투자경험B-2)', mapping=shinhan_default_answer_maps),
            6: Answer(no=7, mapping={
                Answer.FOUNT_ANSWER.B: Answer.SH_ANSWER.A,
                Answer.FOUNT_ANSWER.C: Answer.SH_ANSWER.B,
                Answer.FOUNT_ANSWER.D: Answer.SH_ANSWER.C}, desc='SH:S-C-1(투자경험C-1)', data_type=list),
            7: Answer(no=8, desc='SH:2-C-2(투자경험C-2)', mapping=shinhan_default_answer_maps),
            1: Answer(no=12, desc='SH:1(금융지식 수준/이해도)', mapping=shinhan_default_answer_maps),
            8: Answer(no=13, mapping={
                Answer.FOUNT_ANSWER.A: Answer.SH_ANSWER.A,
                Answer.FOUNT_ANSWER.B: Answer.SH_ANSWER.A,
                Answer.FOUNT_ANSWER.C: Answer.SH_ANSWER.B,
                Answer.FOUNT_ANSWER.D: Answer.SH_ANSWER.C
            }, desc='SH:3(파생상품 투자경험)'),
            10: Answer(no=14, desc='SH:5(취약 금융소비자 확인)', mapping=shinhan_default_answer_maps),
            11: Answer(no=15, desc='SH:6(투자자정보확인 유효기간 설정 동의)', mapping=shinhan_default_answer_maps)
        }
    }

    @classmethod
    def do_mapping(cls, responses):
        mapped_response = super().do_mapping(responses)
        mapped_response[cls.INVESTMENT_EXPERIENCE_FLAG_IDX] = 1
        return mapped_response
