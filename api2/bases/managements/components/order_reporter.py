from api.bases.managements.models import Queue, OrderReport


class OrderReporter:
    def __init__(
        self,
        queue: Queue,
        vendor_code,
        account_number,
        strategies=None,
        report_type=OrderReport.REPORT_TYPES.monitoring,
    ):
        self._report, is_created = OrderReport.objects.get_or_create(
            order=queue, report_type=report_type
        )
        if is_created:
            self._report.title = f"[{vendor_code}]{account_number} Order report"
            if strategies:
                self._report.config["strategies"] = strategies

    @property
    def report_type(self):
        return self._report.report_type

    @report_type.setter
    def report_type(self, report_type):
        if report_type in OrderReport.REPORT_TYPES:
            self._report.report_type = report_type

    def update_title(self, title):
        self._report.title = title

    def write_body(self, data, desc=""):
        self._report.write_body(data=data, desc=desc)

    def save(self):
        self._report.save()
