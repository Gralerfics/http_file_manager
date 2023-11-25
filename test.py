class Base:
    def __init__(self, CardClass):
        self.CardClass = CardClass
    
    def new_card(self):
        print(type(self))
        return self.CardClass(self)

class Card:
    def __init__(self, box):
        self.box = box
    
    def run_test_run(self):
        self.box.test_run()

class RealBox(Base):
    def __init__(self):
        super().__init__(Card)
    
    def test_run(self):
        print('haha')

realbox = RealBox()
card = realbox.new_card()
card.run_test_run()
