import io
import os
import base64
from collections import namedtuple
from datetime import datetime, date
from typing import List, Tuple
from PIL import Image
from PyPDF2 import PdfFileReader, PdfFileWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas


Point = namedtuple('Point', ['x', 'y'])
Size = namedtuple('Size', ['width', 'height'], defaults=(None, None))
BASE_PATH = os.path.dirname(__file__)
pdfmetrics.registerFont(TTFont("굴림", os.path.join(BASE_PATH, "gulim.ttf")))

CONTRACT_PATH_MAP = {
    'OEA': os.path.join(BASE_PATH, 'SEALED_OEA_CONTRACT_TEMPLATE.pdf'),
    'EA': os.path.join(BASE_PATH, 'SEALED_EA_CONTRACT_TEMPLATE.pdf'),
    'FA': os.path.join(BASE_PATH, 'SEALED_FA_CONTRACT_TEMPLATE.pdf'),
    'PA': os.path.join(BASE_PATH, 'SEALED_PA_CONTRACT_TEMPLATE.pdf'),
    'MOEA': os.path.join(BASE_PATH, 'SEALED_MOEA_CONTRACT_TEMPLATE.pdf')
}


CONTRACT_PAGE_INFO = {
        "FA": {
            0: {
                "name": Point(92, 698)
            },
            9: {
                "name": Point(174, 369.5),
                "signature": Point(204, 369.5),
                "birth_date": Point(239, 350.5),
                "start_date__year": Point(393, 408.5),
                "start_date__month": Point(457, 408.5),
                "start_date__day": Point(507, 408.5)
            },
            12: {
                "securities_company": Point(174, 682),
                "account_number": Point(158, 663),
                "name": Point(169, 644),
                "email": Point(300, 570),
            }
        },
        "PA": {
            0: {
                "name": Point(92, 698)
            },
            9: {
                "name": Point(174, 431.5),
                "signature": Point(204, 431.5),
                "birth_date": Point(239, 412),
                "start_date__year": Point(393, 470.5),
                "start_date__month": Point(457, 470.5),
                "start_date__day": Point(507, 470.5)
            },
            12: {
                "securities_company": Point(174, 597),
                "account_number": Point(158, 579),
                "name": Point(169, 559),
                "email": Point(300, 485),
            }
        },
        "EA": {
            0: {
                "name": Point(92, 698)
            },
            9: {
                "name": Point(174, 431.5),
                "signature": Point(204, 431.5),
                "birth_date": Point(239, 412),
                "start_date__year": Point(393, 470.5),
                "start_date__month": Point(457, 470.5),
                "start_date__day": Point(507, 470.5)
            },
            12: {
                "securities_company": Point(174, 682),
                "account_number": Point(158, 663),
                "name": Point(169, 644),
                "email": Point(300, 570),
            },
        },
        "OEA": {
            0: {
                "name": Point(92, 698)
            },
            13: {
                "name": Point(174, 451),
                "signature": Point(204, 451),
                "birth_date": Point(239, 432),
                "start_date__year": Point(394, 489.5),
                "start_date__month": Point(457, 489.5),
                "start_date__day": Point(507, 489.5)
            },
            16: {
                "securities_company": Point(174, 258),
                "account_number": Point(158, 239),
                "name": Point(169, 220),
                "email": Point(300, 146),
            }
        },
        "MOEA": {
            0: {
                "name": Point(92, 709)
            },
            10: {
                "name": Point(172, 677),
                "signature": Point(202, 667),
                "birth_date": Point(230, 661),
                "start_date__year": Point(414, 709.5),
                "start_date__month": Point(467, 709.5),
                "start_date__day": Point(509, 709.5)
            },
            13: {
                "securities_company": Point(172, 596.5),
                "account_number": Point(156, 580),
                "name": Point(167, 563),
                "email": Point(102, 480),
            }
        }
    }


class PdfRenderer:
    def __init__(self,
                 template_file_path,
                 font_name="굴림",
                 context=None,
                 font_size=12):
        if not os.path.exists(template_file_path):
            raise FileNotFoundError(f"Can't find template file path({template_file_path})")
        if context is None:
            context = {}

        self.context = context
        self.font_name = font_name
        self.font_size = font_size
        self.template_file_path = template_file_path
        self.template_contents_map = {}

    def register_template_contents(self, page_num, contents):
        self.template_contents_map[page_num] = contents

    def render(self, fb):
        contract_template = PdfFileReader(self.template_file_path)
        contract_campaign = PdfFileWriter()
        for _page_num in range(contract_template.getNumPages()):
            _target_page = contract_template.getPage(_page_num)
            _target_template_contents = self.template_contents_map.get(_page_num)
            if _target_template_contents:
                for _content in _target_template_contents:
                    _target_page.mergePage(_content)
            contract_campaign.addPage(_target_page)

        if 'password' in self.context:
            contract_campaign = self.encrypt(writer=contract_campaign, password=self.context['password'])
        contract_campaign.write(fb)

    def encrypt(self, writer: PdfFileWriter, password):
        writer.encrypt(password)
        return writer

    def draw_image(self, image_str: bytes, point: Point, size: Size):
        image_data = base64.b64decode(image_str)
        _image = Image.open(io.BytesIO(image_data))
        _image_reader = ImageReader(io.BytesIO(image_data))
        buffer = io.BytesIO()
        _canvas = Canvas(buffer)
        _canvas.drawImage(_image_reader, point.x, point.y, size.width, size.height, mask='auto')
        _canvas.save()
        buffer.seek(0)
        return PdfFileReader(buffer).getPage(0)

    def draw_textset(self, textset: List[Tuple]):
        buffer = io.BytesIO()
        _canvas = Canvas(buffer)
        _canvas.setFont(self.font_name, self.font_size)
        for _text, _point in textset:
            _canvas.drawString(_point.x, _point.y, text=str(_text))
        _canvas.save()
        buffer.seek(0)
        return PdfFileReader(buffer).getPage(0)

    def draw_text(self, text, point: Point):
        buffer = io.BytesIO()
        _canvas = Canvas(buffer)
        _canvas.setFont(self.font_name, self.font_size)
        _canvas.drawString(point.x, point.y, text=text)
        _canvas.save()
        buffer.seek(0)
        return PdfFileReader(buffer).getPage(0)

    def get_b64encode(self):
        buffer = io.BytesIO()
        self.render(buffer)
        return base64.b64encode(buffer.getvalue())


class ContractDocumentRenderer(PdfRenderer):
    IMAGE_SIZE_MAP = {
        'signature': Size(80, 40)
    }

    def __init__(self,
                 template_file_path,
                 render_info,
                 context,
                 *args, **kwargs):
        self.page_contents_map = {}
        super().__init__(template_file_path=template_file_path, context=context, *args, **kwargs)

        for page_num, contents in render_info.items():
            self.page_contents_map[page_num] = contents

    def render(self, fb):
        for page_num, points in self.page_contents_map.items():
            textset, images = [], []
            for key, p in points.items():
                v = self.get_context_value(key=key)
                if v and key in self.IMAGE_SIZE_MAP:
                    images.append(self.draw_image(v, point=p, size=self.IMAGE_SIZE_MAP[key]))
                elif type(v) in [str, int, float]:
                    textset.append((v, p))
                elif type(v) in [datetime, date]:
                    textset.append((v.strftime('%Y-%m-%d'), p))

            self.register_template_contents(
                page_num=page_num,
                contents=[self.draw_textset(textset)] + images)
        return super().render(fb)

    def get_context_value(self, key):
        key, *sub_key = key.split('__')
        v = self.context.get(key, '')
        if v and sub_key:
            for s in sub_key:
                v = getattr(v, s)
        return v


class ContractPDFRendererFactory:
    @classmethod
    def create(cls, contract_type, context) -> ContractDocumentRenderer:
        if contract_type not in CONTRACT_PAGE_INFO:
            raise KeyError(f"{contract_type} is not in render_info")

        return ContractDocumentRenderer(template_file_path=CONTRACT_PATH_MAP[contract_type],
                                        render_info=CONTRACT_PAGE_INFO[contract_type], context=context)

    @staticmethod
    def save(file_path, base64_image):
        with open(file_path, "wb") as f:
            f.write(base64.b64decode(base64_image))
