class Name:
    def __init__(self, name):
        self.name = name
    
    def __str__(self):
        return self.name
    
    def add_name(self):
        add_name = input("追加する名前を入力: ")
        self.name = add_name + self.name  # self.nameを更新
        return self.name  # 更新された名前を返す

n = Name("wanya")
print(n)  # 出力: wanya
n.add_name()  # 名前を更新
print(n)  # 更新された名前を出力
