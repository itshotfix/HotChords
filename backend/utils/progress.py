_progress = {'msg': 'Waiting...', 'pct': 0}

def upd(msg, pct):
    global _progress
    _progress['msg'] = msg
    _progress['pct'] = pct
    print(f'  [{pct:3d}%] {msg}')

def get_progress():
    return _progress

def reset_progress():
    global _progress
    _progress = {'msg': 'Waiting...', 'pct': 0}
