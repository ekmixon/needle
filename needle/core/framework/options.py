

# ======================================================================================================================
# OPTIONS
# ======================================================================================================================
class Options(dict):
    def __init__(self, *args, **kwargs):
        self.required = {}
        self.description = {}
        super(Options, self).__init__(*args, **kwargs)

    def __setitem__(self, name, value):
        super(Options, self).__setitem__(name, self._autoconvert(value))

    def __delitem__(self, name):
        super(Options, self).__delitem__(name)
        if name in self.required:
            del self.required[name]
        if name in self.description:
            del self.description[name]

    def _boolify(self, value):
        return {'true': True, 'false': False}[value.lower()]

    def _autoconvert(self, value):
        if value in (None, True, False):
            return value
        elif (isinstance(value, basestring)) and value.lower() in ('none', "''", '""'):
            return None
        orig = value
        for fn in (self._boolify, int, float):
            try:
                value = fn(value)
                break
            except (ValueError, KeyError, AttributeError):
                pass
        return float(orig) if type(value) is int and '.' in str(orig) else value

    def init_option(self, name, value=None, required=False, description=''):
        self[name] = value
        self.required[name] = required
        self.description[name] = description

    def serialize(self):
        return {key: self[key] for key in self}
