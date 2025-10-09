class Name:
    def __init__(self, name):
        self.name = name
    def __str__(self):
        return self.name
class Add_Name(Name):
    def add_name(self):
        add_name = input()
        return self.name
        
    
