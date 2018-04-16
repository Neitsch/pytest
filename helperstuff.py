from test_in_prod import track_class

@track_class()
class HelperClass(object):
    def __init__(self, number=6):
        self.hello = []
        self.hello.append(number)

    def my_func(self, lst):
        lst.extend(self.hello)
        return lst
