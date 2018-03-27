class HelperClass(object):
    def __init__(self, number=6):
        self.hello = []
        self.hello.append(number)

    def my_func(self, lst):
        lst.extend(self.hello)
        return lst
