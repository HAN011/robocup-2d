from lib.parser.parser_message_params import MessageParamsParser


class _PlayerParam:
    def __init__(self):
        self._raw = {}
        self._allow_mult_default_type = 0
        self._player_types = 18
        self._pt_max = 1
        self._subs_max = 3

    def parse(self, message: str):
        parser = MessageParamsParser()
        parser.parse(message.strip().strip("\x00"))
        data = parser.dic().get("player_param", {})
        self.set_data(data)

    def set_data(self, data: dict):
        self._raw = dict(data)
        self._allow_mult_default_type = int(data.get("allow_mult_default_type", self._allow_mult_default_type))
        self._player_types = int(data.get("player_types", self._player_types))
        self._pt_max = int(data.get("pt_max", self._pt_max))
        self._subs_max = int(data.get("subs_max", self._subs_max))

    def raw(self) -> dict:
        return dict(self._raw)

    def allow_mult_default_type(self) -> int:
        return self._allow_mult_default_type

    def player_types(self) -> int:
        return self._player_types

    def pt_max(self) -> int:
        return self._pt_max

    def subs_max(self) -> int:
        return self._subs_max


class PlayerParam:
    _i: _PlayerParam = _PlayerParam()

    @staticmethod
    def i() -> _PlayerParam:
        return PlayerParam._i
