import traceback


def format_error_traceback(error):
    return "".join(traceback.format_exception(type(error), error, error.__traceback__))