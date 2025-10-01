class Node:
    def __init__(self, node_id, address=None):
        """
        ネットワーク内のノードを表すNodeクラス

        param node_id:ノードを一意に表すID
        param address:ノードの簡易アドレス
        param links:ノードに接続されているリンク
        """

        self.node_id = node_id
        self.address = address
        self.links = []
    # リンクを接続するメソッド追加予定

    def __str__(self):
        return f"ノード(ID: {self.node_id}, アドレス: {self.address})"

# make 2 node
node1 = Node(node_id=1, address="00:01")
node2 = Node(node_id=2, address="00:02")

print(node1)
print(node2)