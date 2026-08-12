_result = {'ready': False, 'data': None, 'error': None}
_analyzing = False

def set_result(data=None, error=None):
    global _result, _analyzing
    _result = {'ready': True, 'data': data, 'error': error}
    _analyzing = False

def get_result():
    return _result

def set_analyzing(status: bool):
    global _analyzing, _result
    _analyzing = status
    if status:
        _result = {'ready': False, 'data': None, 'error': None}

def is_analyzing():
    return _analyzing
