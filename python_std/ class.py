class Name:
    def __init__(self, name):
        self.name = name
    def __str__(self):
        return self.name
    def add_name(self):
        add_name = input()
        new_name = add_name + self.name
        return add_name

n = Name("wanya")
print(n)
n.add_name()

        
    
