class PortfolioServiceError(Exception):
    pass


class PortfolioServiceRetryableHTTPError(PortfolioServiceError):
    pass


class PortfolioDoesNotExistError(PortfolioServiceError):
    pass
