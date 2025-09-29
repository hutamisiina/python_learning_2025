class Packet:
    def __init__(self, source, destination, payload):
        """
        ネットワーク内で送信されるパケットを表現するクラス

        param source:パケットの送信元ノードのアドレス
        paranm destination:パケットの宛先ノードのアドレス
        param payload:パケットに含まれるデータ
        """
    self.source = source
    self.destination = destination
    self.payload = payload

    def __str__(self):
        return f"パケット(送信元: {self.source}, 宛先: {self.destination}, ペイロード: {self.payload})"