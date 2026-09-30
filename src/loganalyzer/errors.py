class LogAnalyzerError(Exception):
    pass


class EmptyLogError(LogAnalyzerError):
    pass


class ConfigurationError(LogAnalyzerError):
    pass
